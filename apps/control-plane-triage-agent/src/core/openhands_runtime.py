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
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.config import Config
from core.tracing import get_tracer

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from openhands.sdk import Agent, Conversation, LLM
from openhands.tools import get_default_tools

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


@dataclass(frozen=True)
class OpenHandsRunResult:
    """Result of one OpenHands execution within a workspace."""

    workspace: Path
    output_text: str | None


class OpenHandsFlowError(RuntimeError):
    """Raised when an OpenHands-backed flow fails with a user-facing explanation."""

    def __init__(self, user_message: str, detail: str) -> None:
        super().__init__(detail)
        self.user_message = user_message
        self.detail = detail


class OpenHandsRuntime:
    """Small runtime facade around the OpenHands SDK."""

    def __init__(self, config: Config) -> None:
        if not config.openhands_enabled:
            raise RuntimeError("OpenHandsRuntime requires OPENHANDS_ENABLED=true")
        if not config.openhands_api_key:
            raise RuntimeError(
                "OpenHandsRuntime requires OPENHANDS_LLM_API_KEY to be configured"
            )
        self._config = config

    def run_incident_diagnosis(self, incident: dict) -> OpenHandsRunResult:
        """Execute diagnosis for one failed workflow incident."""

        run_id = incident["run"]["id"]
        with tracer.start_as_current_span("openhands.run_incident_diagnosis") as span:
            span.set_attribute("github.run_id", run_id)
            workspace = self._config.state_dir / f"incident-{run_id}"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "incident.json").write_text(
                json.dumps(incident, indent=2), encoding="utf-8"
            )
            span.set_attribute("triage.workspace", str(workspace))
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

        with tracer.start_as_current_span("openhands.run_operator_reply") as span:
            span.set_attribute("triage.conversation_key", conversation_key)
            workspace = self.operator_workspace(conversation_key)
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "STATUS.md").write_text(status_snapshot, encoding="utf-8")
            self.append_history_event(workspace, "user", prompt)
            span.set_attribute("triage.workspace", str(workspace))

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

        with tracer.start_as_current_span("openhands.run_conversation") as span:
            span.set_attribute("triage.workspace", str(workspace))
            span.set_attribute("llm.model", self._config.openhands_model)
            span.set_attribute("llm.prompt_chars", len(prompt))
            span.set_attribute("openhands.output_filename", output_filename)
            span.set_attribute("openhands.max_iterations", max_iterations)
            llm = LLM(
                model=self._config.openhands_model, api_key=self._config.openhands_api_key
            )
            tools = get_default_tools(enable_browser=False, enable_sub_agents=False)
            span.set_attribute("openhands.tool_count", len(tools))
            try:
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
            except Exception as exc:  # noqa: BLE001
                span.record_exception(exc)
                raise self._wrap_conversation_error(exc) from exc

    @staticmethod
    def _read_output(path: Path, *, limit: int) -> str | None:
        """Read one generated output file if it exists."""

        if not path.exists():
            logger.warning("OpenHands output file missing path=%s", path)
            return None
        return path.read_text(encoding="utf-8")[:limit]

    @staticmethod
    def _wrap_conversation_error(exc: Exception) -> OpenHandsFlowError:
        """Convert raw SDK/provider failures into actionable agent errors."""

        detail = str(exc).strip() or exc.__class__.__name__
        lower_detail = detail.lower()
        if "provider not provided" in lower_detail:
            return OpenHandsFlowError(
                user_message=(
                    "OpenHands model configuration is invalid. "
                    "The configured model needs an explicit provider prefix, for example `openrouter/...`."
                ),
                detail=detail,
            )
        if "api key" in lower_detail or "authentication" in lower_detail or "unauthorized" in lower_detail:
            return OpenHandsFlowError(
                user_message="OpenHands authentication failed. Check the OpenHands/OpenRouter API key configuration.",
                detail=detail,
            )
        if "rate limit" in lower_detail or "too many requests" in lower_detail:
            return OpenHandsFlowError(
                user_message="OpenHands is being rate limited right now. Please retry shortly.",
                detail=detail,
            )
        return OpenHandsFlowError(
            user_message="OpenHands failed while processing this request. Check the agent logs for the full trace.",
            detail=detail,
        )
