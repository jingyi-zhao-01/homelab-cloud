from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from core.config import Config, WatchTarget
from core.state import StateStore
from functions.diagnoser import Diagnoser
from functions.discord import send_discord
from functions.github_actions import GitHubActionsClient, extract_failure_excerpt, match_runs
from functions.kubernetes_triage import KubernetesTriage

logger = logging.getLogger(__name__)


class TriageService:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._github = GitHubActionsClient(token=config.github_token, max_log_bytes=config.max_log_bytes)
        self._state = StateStore(config.state_dir)
        self._diagnoser = Diagnoser(config)
        self._k8s = KubernetesTriage()
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
        if not self._config.watch_targets:
            logger.warning("No WATCH_TARGETS_JSON configured; agent will idle")
        while True:
            try:
                logger.info("Starting poll cycle")
                self.poll_once()
                logger.info("Completed poll cycle")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Poll loop failed: %s", exc)
            time.sleep(self._config.poll_interval_seconds)

    def poll_once(self) -> None:
        grouped: dict[str, list[WatchTarget]] = {}
        for target in self._config.watch_targets:
            grouped.setdefault(target.repository, []).append(target)

        for repository, targets in grouped.items():
            logger.info("Polling repository=%s target_count=%s", repository, len(targets))
            runs = self._github.list_recent_runs(repository=repository, per_page=self._config.max_runs_per_repo)
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
                    logger.info("Triaging failed run %s for %s", run_id, repository)
                    incident = self._build_incident(repository, target, run)
                    diagnosis = self._diagnoser.diagnose(incident)
                    message = self._render_message(incident, diagnosis)
                    send_discord(self._config.discord_webhook_url, message)
                    self._state.mark_seen(run_id)
                    logger.info("Completed triage for run_id=%s repository=%s", run_id, repository)

    def _build_incident(self, repository: str, target: WatchTarget, run: dict) -> dict:
        run_id = int(run["id"])
        logger.info(
            "Building incident run_id=%s repository=%s workflow=%s namespace=%s",
            run_id,
            repository,
            run.get("name"),
            target.namespace,
        )
        jobs = self._github.list_jobs(repository=repository, run_id=run_id)
        logs = self._github.download_run_logs(repository=repository, run_id=run_id)
        snapshot = self._k8s.collect_namespace_snapshot(target.namespace) if target.namespace else None
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

    def _render_message(self, incident: dict, diagnosis: str) -> str:
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
