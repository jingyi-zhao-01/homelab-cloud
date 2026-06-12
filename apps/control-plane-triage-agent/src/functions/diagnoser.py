from __future__ import annotations

"""Diagnosis functions for failed workflow incidents.

This module provides the semantic "explain what likely happened" layer. It
prefers OpenHands when credentials are available, and falls back to a small
heuristic summary when the LLM path is disabled or fails.
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
        result = self._openhands_runtime.run_incident_diagnosis(incident)
        if result.output_text:
            logger.info("Read OpenHands diagnosis run_id=%s workspace=%s", incident["run"]["id"], result.workspace)
            return result.output_text
        logger.warning("OpenHands diagnosis file missing run_id=%s workspace=%s", incident["run"]["id"], result.workspace)
        return self._heuristic_summary(incident)

    def _run_openhands_operator_prompt(self, conversation_key: str, prompt: str, status_snapshot: str) -> str:
        """Run a thread-scoped OpenHands conversation for an operator's Discord question."""
        result = self._openhands_runtime.run_operator_reply(conversation_key, prompt, status_snapshot)
        if result.output_text:
            return result.output_text
        return "I could not produce a reply file, but I am online and still processing operator prompts."
