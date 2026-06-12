from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from config import Config, WatchTarget, load_config
from diagnoser import Diagnoser
from discord import send_discord
from github_actions import GitHubActionsClient, extract_failure_excerpt, match_runs
from kubernetes_triage import KubernetesTriage
from state import StateStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class TriageService:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._github = GitHubActionsClient(token=config.github_token, max_log_bytes=config.max_log_bytes)
        self._state = StateStore(config.state_dir)
        self._diagnoser = Diagnoser(config)
        self._k8s = KubernetesTriage()

    def run_forever(self) -> None:
        if not self._config.watch_targets:
            logger.warning("No WATCH_TARGETS_JSON configured; agent will idle")
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Poll loop failed: %s", exc)
            time.sleep(self._config.poll_interval_seconds)

    def poll_once(self) -> None:
        grouped: dict[str, list[WatchTarget]] = {}
        for target in self._config.watch_targets:
            grouped.setdefault(target.repository, []).append(target)

        for repository, targets in grouped.items():
            runs = self._github.list_recent_runs(repository=repository, per_page=self._config.max_runs_per_repo)
            for target in targets:
                for run in match_runs(runs, target, self._config.lookback_minutes):
                    run_id = int(run["id"])
                    if self._state.has_seen(run_id):
                        continue
                    logger.info("Triaging failed run %s for %s", run_id, repository)
                    incident = self._build_incident(repository, target, run)
                    diagnosis = self._diagnoser.diagnose(incident)
                    message = self._render_message(incident, diagnosis)
                    send_discord(self._config.discord_webhook_url, message)
                    self._state.mark_seen(run_id)

    def _build_incident(self, repository: str, target: WatchTarget, run: dict) -> dict:
        jobs = self._github.list_jobs(repository=repository, run_id=int(run["id"]))
        logs = self._github.download_run_logs(repository=repository, run_id=int(run["id"]))
        snapshot = self._k8s.collect_namespace_snapshot(target.namespace) if target.namespace else None
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
            "log_excerpt": extract_failure_excerpt(logs),
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
        return content[: self._config.max_discord_chars]


def main() -> None:
    config = load_config()
    TriageService(config).run_forever()
