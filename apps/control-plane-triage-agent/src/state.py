from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, root: Path) -> None:
        self._path = root / "state.json"
        self._data = self._load()

    def _load(self) -> dict[str, list[int]]:
        if not self._path.exists():
            return {"seen_run_ids": []}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def has_seen(self, run_id: int) -> bool:
        return run_id in self._data.get("seen_run_ids", [])

    def mark_seen(self, run_id: int) -> None:
        seen = self._data.setdefault("seen_run_ids", [])
        if run_id not in seen:
            seen.append(run_id)
            seen[:] = seen[-500:]
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
