from __future__ import annotations

"""Diagnosis functions for failed workflow incidents.

This module provides the semantic "explain what likely happened" layer. It
prefers OpenHands when credentials are available, and falls back to a small
heuristic summary when the LLM path is disabled or fails.
"""

import json
import logging
import re
from datetime import UTC, datetime

from core.config import Config

logger = logging.getLogger(__name__)


class Diagnoser:
    """Choose and run the diagnosis strategy for one incident."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def diagnose(self, incident: dict) -> str:
        """Return a diagnosis string using OpenHands or heuristic fallback."""

        run_id = incident["run"]["id"]
        if self._config.openhands_enabled and self._config.openhands_api_key:
            try:
                logger.info("Running OpenHands diagnosis run_id=%s model=%s", run_id, self._config.openhands_model)
                return self._run_openhands(incident)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenHands diagnosis failed: %s", exc)
        logger.info("Using heuristic diagnosis run_id=%s", run_id)
        return self._heuristic_summary(incident)

    def _heuristic_summary(self, incident: dict) -> str:
        """Generate a cheap, deterministic summary without LLM usage."""

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

    def answer_operator_prompt(self, conversation_key: str, prompt: str, status_snapshot: str) -> str:
        """Answer a Discord operator prompt strictly through the LLM path."""

        if not self._config.openhands_enabled:
            logger.warning("Operator prompt rejected because OpenHands is disabled")
            return "LLM conversation is currently disabled because OPENHANDS_ENABLED is false."
        if not self._config.openhands_api_key:
            logger.warning("Operator prompt rejected because OPENHANDS_LLM_API_KEY is missing")
            return "LLM conversation is currently unavailable because OPENHANDS_LLM_API_KEY is missing."
        try:
            logger.info(
                "Running OpenHands operator reply chars=%s model=%s conversation_key=%s",
                len(prompt),
                self._config.openhands_model,
                conversation_key,
            )
            return self._run_openhands_operator_prompt(conversation_key, prompt, status_snapshot)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenHands operator reply failed: %s", exc)
            return "LLM conversation is currently unavailable because the OpenHands reply path failed. Check the agent logs."

    def _run_openhands(self, incident: dict) -> str:
        """Run OpenHands against a workspace containing the incident bundle."""

        from openhands.sdk import Agent, Conversation, LLM
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.task_tracker import TaskTrackerTool
        from openhands.tools.terminal import TerminalTool

        workspace = self._config.state_dir / f"incident-{incident['run']['id']}"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "incident.json").write_text(json.dumps(incident, indent=2), encoding="utf-8")
        logger.info("Prepared OpenHands workspace run_id=%s workspace=%s", incident["run"]["id"], workspace)
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
        logger.info(
            "Completed OpenHands conversation run_id=%s max_iterations=%s",
            incident["run"]["id"],
            self._config.openhands_max_iterations,
        )

        diagnosis_path = workspace / "DIAGNOSIS.md"
        if diagnosis_path.exists():
            logger.info("Read OpenHands diagnosis run_id=%s path=%s", incident["run"]["id"], diagnosis_path)
            return diagnosis_path.read_text(encoding="utf-8")[:4000]
        logger.warning("OpenHands diagnosis file missing run_id=%s path=%s", incident["run"]["id"], diagnosis_path)
        return self._heuristic_summary(incident)

    def _run_openhands_operator_prompt(self, conversation_key: str, prompt: str, status_snapshot: str) -> str:
        """Run a thread-scoped OpenHands conversation for an operator's Discord question."""

        from openhands.sdk import Agent, Conversation, LLM
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.task_tracker import TaskTrackerTool
        from openhands.tools.terminal import TerminalTool

        workspace = self._operator_workspace(conversation_key)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "STATUS.md").write_text(status_snapshot, encoding="utf-8")
        self._append_operator_event(workspace, "user", prompt)
        operator_prompt = (
            "You are a concise control-plane triage assistant responding inside Discord. "
            "Use STATUS.md as runtime context. "
            "Use HISTORY.md as the running conversation history for this Discord thread or channel. "
            "Answer the operator's message directly, briefly, and practically. "
            "If you are unsure, say what you can observe and what to check next. "
            "Write the final answer to REPLY.md.\n\n"
            f"Operator message:\n{prompt}\n"
        )

        llm = LLM(model=self._config.openhands_model, api_key=self._config.openhands_api_key)
        agent = Agent(llm=llm, tools=[FileEditorTool(), TaskTrackerTool(), TerminalTool()])
        conversation = Conversation(
            agent=agent,
            workspace=str(workspace),
            max_iteration_per_run=min(self._config.openhands_max_iterations, 8),
        )
        conversation.send_message(operator_prompt)
        conversation.run()

        reply_path = workspace / "REPLY.md"
        if reply_path.exists():
            reply = reply_path.read_text(encoding="utf-8")[:2000]
            self._append_operator_event(workspace, "assistant", reply)
            return reply
        return "I could not produce a reply file, but I am online and still processing operator prompts."

    def _operator_workspace(self, conversation_key: str):
        """Resolve a stable workspace path for one Discord thread/channel conversation."""

        safe_key = re.sub(r"[^a-zA-Z0-9._-]+", "-", conversation_key).strip("-") or "default"
        return self._config.state_dir / "discord-operator-chat" / safe_key

    def _append_operator_event(self, workspace, role: str, content: str) -> None:
        """Persist a lightweight event log so OpenHands can reuse thread history."""

        history_path = workspace / "HISTORY.md"
        timestamp = datetime.now(UTC).isoformat()
        with history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(f"\n## {timestamp} {role}\n\n{content.strip()}\n")
