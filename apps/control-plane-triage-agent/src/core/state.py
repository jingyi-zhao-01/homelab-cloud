from __future__ import annotations

"""Persistent state for deduplicating and bounding triaged workflow runs.

The agent polls repeatedly, so it needs a tiny persistent memory to avoid
re-processing the same failed GitHub Actions run on every loop. This module owns
that durable state file and keeps the API intentionally small.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from time import time

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunRetryDecision:
    """Decision about whether a workflow run should be processed right now."""

    should_process: bool
    reason: str
    attempt_count: int
    next_retry_at: float | None = None
    status: str | None = None


@dataclass(frozen=True)
class FailedAttemptOutcome:
    """Result of recording one failed triage attempt."""

    attempt_count: int
    terminal: bool
    status: str
    next_retry_at: float | None
    last_error: str


class StateStore:
    """File-backed store of workflow runs, retries, and terminal outcomes."""

    def __init__(self, root: Path) -> None:
        self._path = root / "state.json"
        self._data = self._load()
        logger.info(
            "Initialized state store path=%s seen_run_ids=%s run_states=%s",
            self._path,
            len(self._data.get("seen_run_ids", [])),
            len(self._data.get("run_states", {})),
        )

    def _load(self) -> dict[str, list[int] | dict[str, dict[str, object]]]:
        """Load existing state from disk, or initialize an empty state shape."""

        if not self._path.exists():
            logger.info("State file does not exist yet path=%s", self._path)
            return self._empty_state()

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        seen_run_ids = [int(value) for value in raw.get("seen_run_ids", [])]
        normalized_run_states: dict[str, dict[str, object]] = {}
        for run_id_raw, state in raw.get("run_states", {}).items():
            if not isinstance(state, dict):
                continue
            run_id = str(int(run_id_raw))
            normalized_run_states[run_id] = {
                "status": str(state.get("status", "unknown")),
                "attempt_count": int(state.get("attempt_count", 0)),
                "next_retry_at": self._coerce_optional_float(state.get("next_retry_at")),
                "last_attempted_at": self._coerce_optional_float(state.get("last_attempted_at")),
                "last_error": str(state.get("last_error", "")),
            }

        data = {
            "seen_run_ids": seen_run_ids,
            "run_states": normalized_run_states,
        }
        logger.info(
            "Loaded state file path=%s seen_run_ids=%s run_states=%s",
            self._path,
            len(seen_run_ids),
            len(normalized_run_states),
        )
        return data

    def _empty_state(self) -> dict[str, list[int] | dict[str, dict[str, object]]]:
        return {"seen_run_ids": [], "run_states": {}}

    def _coerce_optional_float(self, value: object) -> float | None:
        if value is None:
            return None
        return float(value)

    def _run_key(self, run_id: int) -> str:
        return str(run_id)

    def _get_run_state(self, run_id: int) -> dict[str, object] | None:
        run_states = self._data.setdefault("run_states", {})
        assert isinstance(run_states, dict)
        return run_states.get(self._run_key(run_id))

    def _set_run_state(self, run_id: int, state: dict[str, object]) -> None:
        run_states = self._data.setdefault("run_states", {})
        assert isinstance(run_states, dict)
        run_states[self._run_key(run_id)] = state

    def _write(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")

    def has_seen(self, run_id: int) -> bool:
        """Return whether a GitHub Actions run has already been triaged."""

        return run_id in self._data.get("seen_run_ids", [])

    def get_retry_decision(self, run_id: int, *, now: float | None = None) -> RunRetryDecision:
        """Return whether a run should be processed now or skipped."""

        current_time = now if now is not None else time()
        if self.has_seen(run_id):
            run_state = self._get_run_state(run_id)
            return RunRetryDecision(
                should_process=False,
                reason="seen",
                attempt_count=int((run_state or {}).get("attempt_count", 0)),
                next_retry_at=self._coerce_optional_float((run_state or {}).get("next_retry_at")),
                status=str((run_state or {}).get("status", "success")),
            )

        run_state = self._get_run_state(run_id)
        if run_state is None:
            return RunRetryDecision(should_process=True, reason="new", attempt_count=0)

        attempt_count = int(run_state.get("attempt_count", 0))
        next_retry_at = self._coerce_optional_float(run_state.get("next_retry_at"))
        status = str(run_state.get("status", "unknown"))
        if status == "retry_scheduled" and next_retry_at is not None and current_time < next_retry_at:
            return RunRetryDecision(
                should_process=False,
                reason="backoff",
                attempt_count=attempt_count,
                next_retry_at=next_retry_at,
                status=status,
            )

        return RunRetryDecision(
            should_process=True,
            reason="retry_due" if attempt_count else "new",
            attempt_count=attempt_count,
            next_retry_at=next_retry_at,
            status=status,
        )

    def record_failed_attempt(
        self,
        run_id: int,
        *,
        error_message: str,
        max_attempts: int,
        initial_backoff_seconds: int,
        max_backoff_seconds: int,
        now: float | None = None,
    ) -> FailedAttemptOutcome:
        """Persist a failed triage attempt and compute its next retry state."""

        current_time = now if now is not None else time()
        run_state = self._get_run_state(run_id) or {}
        attempt_count = int(run_state.get("attempt_count", 0)) + 1
        terminal = attempt_count >= max_attempts
        next_retry_at = None
        status = "seen_with_failure" if terminal else "retry_scheduled"
        if not terminal:
            backoff_seconds = min(
                max_backoff_seconds,
                initial_backoff_seconds * (2 ** max(attempt_count - 1, 0)),
            )
            next_retry_at = current_time + backoff_seconds

        next_state = {
            "status": status,
            "attempt_count": attempt_count,
            "next_retry_at": next_retry_at,
            "last_attempted_at": current_time,
            "last_error": error_message,
        }
        self._set_run_state(run_id, next_state)

        if terminal:
            seen = self._data.setdefault("seen_run_ids", [])
            assert isinstance(seen, list)
            if run_id not in seen:
                seen.append(run_id)
                seen[:] = seen[-500:]

        self._write()
        logger.info(
            "Recorded failed triage attempt run_id=%s attempt_count=%s terminal=%s status=%s next_retry_at=%s",
            run_id,
            attempt_count,
            terminal,
            status,
            next_retry_at,
        )
        return FailedAttemptOutcome(
            attempt_count=attempt_count,
            terminal=terminal,
            status=status,
            next_retry_at=next_retry_at,
            last_error=error_message,
        )

    def mark_seen(self, run_id: int) -> None:
        """Persist a run ID after successful triage and notification."""

        seen = self._data.setdefault("seen_run_ids", [])
        assert isinstance(seen, list)
        if run_id not in seen:
            seen.append(run_id)
            seen[:] = seen[-500:]
        self._set_run_state(
            run_id,
            {
                "status": "success",
                "attempt_count": int((self._get_run_state(run_id) or {}).get("attempt_count", 0)),
                "next_retry_at": None,
                "last_attempted_at": time(),
                "last_error": "",
            },
        )
        self._write()
        logger.info("Recorded triaged run_id=%s total_seen=%s path=%s", run_id, len(seen), self._path)

    def get_status_counts(self, *, now: float | None = None) -> dict[str, int]:
        """Return coarse state counts for operator-facing status and logs."""

        current_time = now if now is not None else time()
        run_states = self._data.get("run_states", {})
        assert isinstance(run_states, dict)
        retry_scheduled = 0
        seen_with_failure = 0
        for state in run_states.values():
            if not isinstance(state, dict):
                continue
            status = str(state.get("status", "unknown"))
            if status == "seen_with_failure":
                seen_with_failure += 1
            elif status == "retry_scheduled":
                next_retry_at = self._coerce_optional_float(state.get("next_retry_at"))
                if next_retry_at is None or next_retry_at >= current_time:
                    retry_scheduled += 1
        return {
            "seen": len(self._data.get("seen_run_ids", [])),
            "retry_scheduled": retry_scheduled,
            "seen_with_failure": seen_with_failure,
        }
