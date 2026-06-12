from __future__ import annotations

"""Long-running orchestration loop for the triage agent.

This module wires together:
- GitHub run polling
- deduplication state
- event publication
- operator-facing status/chat entrypoints

It should contain the high-level control flow and event publication, while
side-effecting reactions live in dedicated event handlers under `run_time/`.
"""

import asyncio
import logging
import time

from core.config import Config, WatchTarget
from core.event_bus import AsyncEventBus
from core.events import IncidentAssembled, IncidentDiagnosed, WorkflowRunDetected
from core.state import StateStore
from functions.diagnoser import Diagnoser
from functions.discord import DiscordNotifier
from functions.github_actions import GitHubActionsClient, match_runs
from functions.kubernetes_triage import KubernetesTriage
from run_time.event_handlers import (
    IncidentDiagnosisEventHandler,
    IncidentNotificationEventHandler,
    WorkflowRunEventHandler,
)

logger = logging.getLogger(__name__)


class TriageService:
    """Own the poll/triage/notify lifecycle for watched workflow failures."""

    def __init__(self, config: Config, notifier: DiscordNotifier | None = None) -> None:
        self._config = config
        self._notifier = notifier
        self._github = GitHubActionsClient(token=config.github_token, max_log_bytes=config.max_log_bytes)
        self._state = StateStore(config.state_dir)
        self._diagnoser = Diagnoser(config)
        self._k8s = KubernetesTriage()
        self._event_bus = AsyncEventBus()
        self._workflow_handler = WorkflowRunEventHandler(
            state=self._state,
            github=self._github,
            kubernetes_triage=self._k8s,
            event_bus=self._event_bus,
        )
        self._diagnosis_handler = IncidentDiagnosisEventHandler(
            diagnoser=self._diagnoser,
            event_bus=self._event_bus,
        )
        self._notification_handler = IncidentNotificationEventHandler(
            config=self._config,
            state=self._state,
            notifier=notifier,
        )
        self._attach_default_handlers()
        logger.info(
            "Initialized triage service poll_interval_seconds=%s lookback_minutes=%s max_runs_per_repo=%s "
            "watch_targets=%s openhands_enabled=%s state_dir=%s",
            config.poll_interval_seconds,
            config.lookback_minutes,
            config.max_runs_per_repo,
            len(config.watch_targets),
            config.openhands_enabled and bool(config.openhands_api_key),
            config.state_dir,
        )

    def run_forever(self) -> None:
        """Run the infinite polling loop used by the deployed agent pod."""

        if not self._config.watch_targets:
            logger.warning("No WATCH_TARGETS_JSON configured; agent will idle")
        while True:
            try:
                logger.info("Starting poll cycle")
                asyncio.run(self.poll_once())
                logger.info("Completed poll cycle")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Poll loop failed: %s", exc)
            time.sleep(self._config.poll_interval_seconds)

    async def poll_once(self) -> None:
        """Execute one full polling pass across all configured repositories."""

        grouped: dict[str, list[WatchTarget]] = {}
        for target in self._config.watch_targets:
            grouped.setdefault(target.repository, []).append(target)

        for repository, targets in grouped.items():
            logger.info("Polling repository=%s target_count=%s", repository, len(targets))
            runs = await self._github.list_recent_runs(repository=repository, per_page=self._config.max_runs_per_repo)
            logger.info("Fetched repository=%s recent_runs=%s", repository, len(runs))
            for target in targets:
                matched_runs = match_runs(runs, target, self._config.lookback_minutes)
                logger.info(
                    "Matched repository=%s namespace=%s workflow_names=%s workflow_ids=%s branch=%s matched_runs=%s",
                    repository,
                    target.namespace,
                    list(target.workflow_names),
                    list(target.workflow_ids),
                    target.branch,
                    len(matched_runs),
                )
                for run in matched_runs:
                    run_id = int(run["id"])
                    if self._state.has_seen(run_id):
                        logger.info("Skipping previously triaged run_id=%s repository=%s", run_id, repository)
                        continue
                    logger.info("Publishing workflow event run_id=%s repository=%s", run_id, repository)
                    await self._event_bus.publish(
                        WorkflowRunDetected(
                            repository=repository,
                            target=target,
                            run=run,
                        )
                    )

    def render_status(self) -> str:
        """Render a short operator-facing status snapshot for Discord mentions."""

        return (
            "control-plane-triage-agent is online.\n"
            f"- watch targets: {len(self._config.watch_targets)}\n"
            f"- seen failed runs: {len(self._state._data.get('seen_run_ids', []))}\n"
            f"- poll interval seconds: {self._config.poll_interval_seconds}"
        )

    def answer_operator_prompt(self, conversation_key: str, prompt: str) -> str:
        """Answer a Discord mention using a compact runtime summary plus LLM fallback."""

        return self._diagnoser.answer_operator_prompt(conversation_key, prompt, self.render_status())

    def set_notifier(self, notifier: DiscordNotifier) -> None:
        """Attach the Discord notifier after service construction when needed."""

        self._notifier = notifier
        self._notification_handler.set_notifier(notifier)

    def _attach_default_handlers(self) -> None:
        """Bind the default workflow triage handler to the in-process event bus."""

        self._event_bus.subscribe(
            WorkflowRunDetected,
            self._workflow_handler.handle_workflow_run_detected,
        )
        self._event_bus.subscribe(
            IncidentAssembled,
            self._diagnosis_handler.handle_incident_assembled,
        )
        self._event_bus.subscribe(
            IncidentDiagnosed,
            self._notification_handler.handle_incident_diagnosed,
        )
