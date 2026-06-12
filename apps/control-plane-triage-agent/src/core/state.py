from __future__ import annotations

"""Persistent state for deduplicating triaged workflow runs.

The agent polls repeatedly, so it needs a tiny persistent memory to avoid
re-processing the same failed GitHub Actions run on every loop. This module owns
that durable state file and keeps the API intentionally small.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StateStore:
    """File-backed store of workflow run IDs that have already been triaged."""

    def __init__(self, root: Path) -> None:
        self._path = root / "state.json"
        self._data = self._load()
        logger.info("Initialized state store path=%s seen_run_ids=%s", self._path, len(self._data.get("seen_run_ids", [])))

    def _load(self) -> dict[str, list[int]]:
        """Load existing state from disk, or initialize an empty state shape."""

        if not self._path.exists():
            logger.info("State file does not exist yet path=%s", self._path)
            return {"seen_run_ids": []}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        logger.info("Loaded state file path=%s seen_run_ids=%s", self._path, len(data.get("seen_run_ids", [])))
        return data

    def has_seen(self, run_id: int) -> bool:
        """Return whether a GitHub Actions run has already been triaged."""

        return run_id in self._data.get("seen_run_ids", [])

    def mark_seen(self, run_id: int) -> None:
        """Persist a run ID after successful triage and notification."""

        seen = self._data.setdefault("seen_run_ids", [])
        if run_id not in seen:
            seen.append(run_id)
            seen[:] = seen[-500:]
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            logger.info("Recorded triaged run_id=%s total_seen=%s path=%s", run_id, len(seen), self._path)
