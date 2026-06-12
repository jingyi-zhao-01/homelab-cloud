from __future__ import annotations

"""Diagnosis functions for failed workflow incidents.

This module delegates all diagnosis and operator conversations to the required
OpenHands runtime. There is no heuristic fallback path.
"""

import logging

from core.config import Config
from core.openhands_runtime import OpenHandsRuntime

logger = logging.getLogger(__name__)


class Diagnoser:
    """Choose and run the diagnosis strategy for one incident."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._openhands_runtime = OpenHandsRuntime(config)

    def diagnose(self, incident: dict) -> str:
        """Return a diagnosis string using the required OpenHands runtime."""

        run_id = incident["run"]["id"]
        logger.info(
            "Running OpenHands diagnosis run_id=%s model=%s",
            run_id,
            self._config.openhands_model,
        )
        return self._run_openhands(incident)

    def answer_operator_prompt(self, conversation_key: str, prompt: str, status_snapshot: str) -> str:
        """Answer a Discord operator prompt through the required LLM path."""

        logger.info(
            "Running OpenHands operator reply chars=%s model=%s conversation_key=%s",
            len(prompt),
            self._config.openhands_model,
            conversation_key,
        )
        return self._run_openhands_operator_prompt(
            conversation_key,
            prompt,
            status_snapshot,
        )

    def _run_openhands(self, incident: dict) -> str:
        """Run OpenHands against a workspace containing the incident bundle."""
        result = self._openhands_runtime.run_incident_diagnosis(incident)
        if result.output_text:
            logger.info(
                "Read OpenHands diagnosis run_id=%s workspace=%s",
                incident["run"]["id"],
                result.workspace,
            )
            return result.output_text
        raise RuntimeError(
            "OpenHands diagnosis completed without producing DIAGNOSIS.md "
            f"for run_id={incident['run']['id']} workspace={result.workspace}"
        )

    def _run_openhands_operator_prompt(self, conversation_key: str, prompt: str, status_snapshot: str) -> str:
        """Run a thread-scoped OpenHands conversation for an operator's Discord question."""
        result = self._openhands_runtime.run_operator_reply(conversation_key, prompt, status_snapshot)
        if result.output_text:
            return result.output_text
        raise RuntimeError(
            "OpenHands operator reply completed without producing REPLY.md "
            f"for conversation_key={conversation_key} workspace={result.workspace}"
        )
