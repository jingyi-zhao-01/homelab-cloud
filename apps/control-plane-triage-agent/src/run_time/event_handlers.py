from __future__ import annotations

"""Event handlers that perform side effects for triage domain events."""

import asyncio
import logging
from datetime import datetime, timezone

from core.config import Config, WatchTarget
from core.event_bus import AsyncEventBus
from core.events import IncidentAssembled, IncidentDiagnosed, WorkflowRunDetected
from core.state import StateStore
from functions.diagnoser import Diagnoser
from functions.discord import DiscordNotifier
from functions.github_actions import GitHubActionsClient, extract_failure_excerpt
from functions.kubernetes_triage import KubernetesTriage

logger = logging.getLogger(__name__)


class WorkflowRunEventHandler:
    """Collect incident evidence, then publish the next domain event."""

    def __init__(
        self,
        *,
        state: StateStore,
        github: GitHubActionsClient,
        kubernetes_triage: KubernetesTriage,
        event_bus: AsyncEventBus,
    ) -> None:
        self._state = state
        self._github = github
        self._k8s = kubernetes_triage
        self._event_bus = event_bus

    async def handle_workflow_run_detected(self, event: WorkflowRunDetected) -> None:
        """React to a newly detected failed workflow run."""

        run_id = int(event.run["id"])
        if self._state.has_seen(run_id):
            logger.info("Skipping already-triaged run_id=%s repository=%s during handler", run_id, event.repository)
            return

        logger.info("Handling workflow event run_id=%s repository=%s", run_id, event.repository)
        incident = await self._build_incident(event.repository, event.target, event.run)
        await self._event_bus.publish(
            IncidentAssembled(
                repository=event.repository,
                target=event.target,
                run=event.run,
                incident=incident,
            )
        )
        logger.info("Published IncidentAssembled run_id=%s repository=%s", run_id, event.repository)

    async def _build_incident(self, repository: str, target: WatchTarget, run: dict) -> dict:
        """Assemble the incident payload consumed by diagnosers and notifiers."""

        run_id = int(run["id"])
        logger.info(
            "Building incident run_id=%s repository=%s workflow=%s namespace=%s",
            run_id,
            repository,
            run.get("name"),
            target.namespace,
        )
        jobs, logs = await asyncio.gather(
            self._github.list_jobs(repository=repository, run_id=run_id),
            self._github.download_run_logs(repository=repository, run_id=run_id),
        )
        snapshot = (
            await asyncio.to_thread(self._k8s.collect_namespace_snapshot, target.namespace)
            if target.namespace
            else None
        )
        log_excerpt = extract_failure_excerpt(logs)
        logger.info(
            "Built incident run_id=%s repository=%s jobs=%s log_files=%s namespace_snapshot=%s excerpt_chars=%s",
            run_id,
            repository,
            len(jobs),
            len(logs),
            bool(snapshot),
            len(log_excerpt),
        )
        return {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "repository": repository,
            "target": {
                "namespace": target.namespace,
                "branch": target.branch,
                "workflow_names": list(target.workflow_names),
                "workflow_ids": list(target.workflow_ids),
            },
            "run": run,
            "jobs": jobs,
            "log_excerpt": log_excerpt,
            "namespace_snapshot": snapshot,
        }


class IncidentDiagnosisEventHandler:
    """Transform assembled incident evidence into a diagnosis event."""

    def __init__(self, *, diagnoser: Diagnoser, event_bus: AsyncEventBus) -> None:
        self._diagnoser = diagnoser
        self._event_bus = event_bus

    async def handle_incident_assembled(self, event: IncidentAssembled) -> None:
        """Run the diagnoser and publish the diagnosis as a new event."""

        run_id = int(event.run["id"])
        logger.info("Diagnosing incident run_id=%s repository=%s", run_id, event.repository)
        diagnosis = await asyncio.to_thread(self._diagnoser.diagnose, event.incident)
        await self._event_bus.publish(
            IncidentDiagnosed(
                repository=event.repository,
                target=event.target,
                run=event.run,
                incident=event.incident,
                diagnosis=diagnosis,
            )
        )
        logger.info("Published IncidentDiagnosed run_id=%s repository=%s", run_id, event.repository)


class IncidentNotificationEventHandler:
    """Deliver operator-facing notifications and commit triage state."""

    def __init__(
        self,
        *,
        config: Config,
        state: StateStore,
        notifier: DiscordNotifier | None,
    ) -> None:
        self._config = config
        self._state = state
        self._notifier = notifier

    def set_notifier(self, notifier: DiscordNotifier | None) -> None:
        """Swap the active notifier without rebuilding the event pipeline."""

        self._notifier = notifier

    async def handle_incident_diagnosed(self, event: IncidentDiagnosed) -> None:
        """Notify operators and mark the run as triaged once delivery completes."""

        run_id = int(event.run["id"])
        logger.info("Notifying diagnosis run_id=%s repository=%s", run_id, event.repository)
        if self._notifier is not None:
            message = self._render_message(event.incident, event.diagnosis)
            await asyncio.to_thread(self._notifier.send, message)
        else:
            logger.warning("No notifier configured for run_id=%s repository=%s", run_id, event.repository)
        await asyncio.to_thread(self._state.mark_seen, run_id)
        logger.info("Completed event handling run_id=%s repository=%s", run_id, event.repository)

    def _render_message(self, incident: dict, diagnosis: str) -> str:
        """Render the final Discord message payload for one triaged incident."""

        run = incident["run"]
        lines = [
            "❌ control-plane-triage-agent detected a failed pipeline",
            f"repo: `{incident['repository']}`",
            f"workflow: `{run.get('name')}`",
            f"run id: `{run.get('id')}`",
            f"branch: `{run.get('head_branch')}`",
            f"conclusion: `{run.get('conclusion')}`",
            f"url: {run.get('html_url')}",
        ]
        if incident.get("target", {}).get("namespace"):
            lines.append(f"namespace: `{incident['target']['namespace']}`")
        excerpt = incident.get("log_excerpt")
        if excerpt:
            lines.append("log excerpt:")
            lines.append("```text")
            lines.append(excerpt[:700])
            lines.append("```")
        if diagnosis:
            lines.append("diagnosis:")
            lines.append("```markdown")
            lines.append(diagnosis[:900])
            lines.append("```")
        content = "\n".join(lines)
        logger.info(
            "Rendered Discord message run_id=%s repository=%s chars=%s diagnosis_chars=%s",
            run.get("id"),
            incident["repository"],
            len(content),
            len(diagnosis),
        )
        return content[: self._config.max_discord_chars]
