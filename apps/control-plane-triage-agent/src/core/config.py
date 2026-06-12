from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WatchTarget:
    repository: str
    workflow_names: tuple[str, ...] = ()
    workflow_ids: tuple[int, ...] = ()
    namespace: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class Config:
    github_token: str
    discord_webhook_url: str
    poll_interval_seconds: int
    lookback_minutes: int
    max_runs_per_repo: int
    max_log_bytes: int
    max_discord_chars: int
    state_dir: Path
    openhands_enabled: bool
    openhands_model: str
    openhands_api_key: str | None
    openhands_max_iterations: int
    watch_targets: tuple[WatchTarget, ...]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_targets(raw: str | None) -> tuple[WatchTarget, ...]:
    if not raw:
        return ()

    data = json.loads(raw)
    targets: list[WatchTarget] = []
    for entry in data:
        targets.append(
            WatchTarget(
                repository=entry["repository"],
                workflow_names=tuple(entry.get("workflow_names", [])),
                workflow_ids=tuple(int(value) for value in entry.get("workflow_ids", [])),
                namespace=entry.get("namespace"),
                branch=entry.get("branch"),
            )
        )
    return tuple(targets)


def load_config() -> Config:
    github_token = os.environ["GITHUB_TOKEN"]
    discord_webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    state_dir = Path(os.environ.get("STATE_DIR", "/var/lib/control-plane-triage-agent"))
    state_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        github_token=github_token,
        discord_webhook_url=discord_webhook_url,
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "120")),
        lookback_minutes=int(os.environ.get("LOOKBACK_MINUTES", "120")),
        max_runs_per_repo=int(os.environ.get("MAX_RUNS_PER_REPO", "20")),
        max_log_bytes=int(os.environ.get("MAX_LOG_BYTES", str(512 * 1024))),
        max_discord_chars=int(os.environ.get("MAX_DISCORD_CHARS", "1800")),
        state_dir=state_dir,
        openhands_enabled=_parse_bool(os.environ.get("OPENHANDS_ENABLED"), True),
        openhands_model=os.environ.get("OPENHANDS_MODEL", "openhands/claude-sonnet-4-5-20250929"),
        openhands_api_key=os.environ.get("OPENHANDS_LLM_API_KEY"),
        openhands_max_iterations=int(os.environ.get("OPENHANDS_MAX_ITERATIONS", "30")),
        watch_targets=_parse_targets(os.environ.get("WATCH_TARGETS_JSON")),
    )
