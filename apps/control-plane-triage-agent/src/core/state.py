from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StateStore:
    def __init__(self, root: Path) -> None:
        self._path = root / "state.json"
        self._data = self._load()
        logger.info("Initialized state store path=%s seen_run_ids=%s", self._path, len(self._data.get("seen_run_ids", [])))

    def _load(self) -> dict[str, list[int]]:
        if not self._path.exists():
            logger.info("State file does not exist yet path=%s", self._path)
            return {"seen_run_ids": []}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        logger.info("Loaded state file path=%s seen_run_ids=%s", self._path, len(data.get("seen_run_ids", [])))
        return data

    def has_seen(self, run_id: int) -> bool:
        return run_id in self._data.get("seen_run_ids", [])

    def mark_seen(self, run_id: int) -> None:
        seen = self._data.setdefault("seen_run_ids", [])
        if run_id not in seen:
            seen.append(run_id)
            seen[:] = seen[-500:]
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            logger.info("Recorded triaged run_id=%s total_seen=%s path=%s", run_id, len(seen), self._path)
