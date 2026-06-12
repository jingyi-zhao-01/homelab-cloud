from __future__ import annotations

"""Core runtime adapter for executing OpenHands workspaces and conversations.

This module owns:
- SDK object construction
- workspace path resolution
- lightweight conversation history persistence
- REPLY/DIAGNOSIS file collection

Higher-level features should pass prompts and consume outputs, without knowing
how OpenHands is wired underneath.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openhands.sdk import Agent, Conversation, LLM
from openhands.tools.file_editor import (
    FileEditorAction,
    FileEditorObservation,
    FileEditorTool,
)
from openhands.tools.task_tracker import (
    TaskTrackerAction,
    TaskTrackerObservation,
    TaskTrackerTool,
)
from openhands.tools.terminal import (
    TerminalAction,
    TerminalObservation,
    TerminalTool,
)

from core.config import Config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenHandsRunResult:
    """Result of one OpenHands execution within a workspace."""

    workspace: Path
    output_text: str | None


class OpenHandsRuntime:
    """Small runtime facade around the OpenHands SDK."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def run_incident_diagnosis(self, incident: dict) -> OpenHandsRunResult:
        """Execute diagnosis for one failed workflow incident."""

        run_id = incident["run"]["id"]
        workspace = self._config.state_dir / f"incident-{run_id}"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "incident.json").write_text(
            json.dumps(incident, indent=2), encoding="utf-8"
        )
        logger.info(
            "Prepared OpenHands incident workspace run_id=%s workspace=%s",
            run_id,
            workspace,
        )

        prompt = (
            "You are diagnosing a failed GitHub Actions deployment pipeline. "
            "Read incident.json, identify the most likely root cause, the fastest next checks, "
            "and the safest remediation. Write the result to DIAGNOSIS.md as concise markdown."
        )
        self._run_conversation(
            workspace=workspace,
            prompt=prompt,
            output_filename="DIAGNOSIS.md",
            max_iterations=self._config.openhands_max_iterations,
        )
        return OpenHandsRunResult(
            workspace=workspace,
            output_text=self._read_output(workspace / "DIAGNOSIS.md", limit=4000),
        )

    def run_operator_reply(
        self, conversation_key: str, prompt: str, status_snapshot: str
    ) -> OpenHandsRunResult:
        """Execute one thread-scoped operator reply conversation."""

        workspace = self.operator_workspace(conversation_key)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "STATUS.md").write_text(status_snapshot, encoding="utf-8")
        self.append_history_event(workspace, "user", prompt)

        operator_prompt = (
            "You are a concise control-plane triage assistant responding inside Discord. "
            "Use STATUS.md as runtime context. "
            "Use HISTORY.md as the running conversation history for this Discord thread or channel. "
            "Answer the operator's message directly, briefly, and practically. "
            "If you are unsure, say what you can observe and what to check next. "
            "Write the final answer to REPLY.md.\n\n"
            f"Operator message:\n{prompt}\n"
        )
        self._run_conversation(
            workspace=workspace,
            prompt=operator_prompt,
            output_filename="REPLY.md",
            max_iterations=min(self._config.openhands_max_iterations, 8),
        )
        reply = self._read_output(workspace / "REPLY.md", limit=2000)
        if reply:
            self.append_history_event(workspace, "assistant", reply)
        return OpenHandsRunResult(workspace=workspace, output_text=reply)

    def operator_workspace(self, conversation_key: str) -> Path:
        """Resolve a stable workspace path for one Discord conversation."""

        safe_key = (
            re.sub(r"[^a-zA-Z0-9._-]+", "-", conversation_key).strip("-") or "default"
        )
        return self._config.state_dir / "discord-operator-chat" / safe_key

    def append_history_event(self, workspace: Path, role: str, content: str) -> None:
        """Persist a lightweight markdown event log alongside the workspace."""

        history_path = workspace / "HISTORY.md"
        timestamp = datetime.now(UTC).isoformat()
        with history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(f"\n## {timestamp} {role}\n\n{content.strip()}\n")

    def _run_conversation(
        self,
        *,
        workspace: Path,
        prompt: str,
        output_filename: str,
        max_iterations: int,
    ) -> None:
        """Construct SDK objects and execute one OpenHands run."""

        from openhands.sdk import Agent, Conversation, LLM
        from openhands.tools.file_editor import (
            FileEditorAction,
            FileEditorObservation,
            FileEditorTool,
        )
        from openhands.tools.task_tracker import (
            TaskTrackerAction,
            TaskTrackerObservation,
            TaskTrackerTool,
        )
        from openhands.tools.terminal import (
            TerminalAction,
            TerminalObservation,
            TerminalTool,
        )

        llm = LLM(
            model=self._config.openhands_model, api_key=self._config.openhands_api_key
        )
        tools = [
            FileEditorTool(
                description="Read and edit files inside the OpenHands workspace.",
                action_type=FileEditorAction,
                observation_type=FileEditorObservation,
            ),
            TaskTrackerTool(
                description="Track intermediate tasks and execution progress.",
                action_type=TaskTrackerAction,
                observation_type=TaskTrackerObservation,
            ),
            TerminalTool(
                description="Run terminal commands inside the OpenHands workspace.",
                action_type=TerminalAction,
                observation_type=TerminalObservation,
            ),
        ]
        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(
            agent=agent,
            workspace=str(workspace),
            max_iteration_per_run=max_iterations,
        )
        conversation.send_message(prompt)
        conversation.run()
        logger.info(
            "Completed OpenHands conversation workspace=%s output_filename=%s max_iterations=%s",
            workspace,
            output_filename,
            max_iterations,
        )

    @staticmethod
    def _read_output(path: Path, *, limit: int) -> str | None:
        """Read one generated output file if it exists."""

        if not path.exists():
            logger.warning("OpenHands output file missing path=%s", path)
            return None
        return path.read_text(encoding="utf-8")[:limit]
