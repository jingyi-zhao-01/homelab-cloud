from __future__ import annotations

import json
import logging
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


class Diagnoser:
    def __init__(self, config: Config) -> None:
        self._config = config

    def diagnose(self, incident: dict) -> str:
        if self._config.openhands_enabled and self._config.openhands_api_key:
            try:
                return self._run_openhands(incident)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenHands diagnosis failed: %s", exc)
        return self._heuristic_summary(incident)

    def _heuristic_summary(self, incident: dict) -> str:
        jobs = incident.get("jobs", [])
        first_failed_job = next((job for job in jobs if job.get("conclusion") == "failure"), None)
        lines = [
            "Fallback diagnosis:",
            f"- workflow: {incident['run']['name']}",
            f"- conclusion: {incident['run'].get('conclusion')}",
        ]
        if first_failed_job:
            lines.append(f"- first failed job: {first_failed_job.get('name')}")
            failed_steps = [step.get("name") for step in first_failed_job.get("steps", []) if step.get("conclusion") == "failure"]
            if failed_steps:
                lines.append(f"- failed steps: {', '.join(failed_steps[:5])}")
        excerpt = incident.get("log_excerpt")
        if excerpt:
            lines.append("- likely signal: log excerpt contains the first actionable error/exception lines")
        namespace_snapshot = incident.get("namespace_snapshot")
        if namespace_snapshot:
            lines.append(f"- namespace triaged: {namespace_snapshot.get('namespace')}")
        return "\n".join(lines)

    def _run_openhands(self, incident: dict) -> str:
        from openhands.sdk import Agent, Conversation, LLM
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.task_tracker import TaskTrackerTool
        from openhands.tools.terminal import TerminalTool

        workspace = self._config.state_dir / f"incident-{incident['run']['id']}"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "incident.json").write_text(json.dumps(incident, indent=2), encoding="utf-8")
        prompt = (
            "You are diagnosing a failed GitHub Actions deployment pipeline. "
            "Read incident.json, identify the most likely root cause, the fastest next checks, "
            "and the safest remediation. Write the result to DIAGNOSIS.md as concise markdown."
        )

        llm = LLM(model=self._config.openhands_model, api_key=self._config.openhands_api_key)
        agent = Agent(llm=llm, tools=[FileEditorTool(), TaskTrackerTool(), TerminalTool()])
        conversation = Conversation(
            agent=agent,
            workspace=str(workspace),
            max_iteration_per_run=self._config.openhands_max_iterations,
        )
        conversation.send_message(prompt)
        conversation.run()

        diagnosis_path = workspace / "DIAGNOSIS.md"
        if diagnosis_path.exists():
            return diagnosis_path.read_text(encoding="utf-8")[:4000]
        return self._heuristic_summary(incident)
