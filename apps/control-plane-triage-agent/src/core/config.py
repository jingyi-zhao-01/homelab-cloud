from __future__ import annotations

"""Core configuration model for the triage agent.

This module is intentionally small and dependency-light:
- define the immutable runtime config shape
- parse environment variables into typed fields
- parse WATCH_TARGETS_JSON into semantic watch targets

Higher-level orchestration should depend on this module, not on raw os.environ.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

_SUPPORTED_OPENHANDS_MODEL_PROVIDERS = {
    "anthropic",
    "azure",
    "bedrock",
    "deepseek",
    "gemini",
    "google",
    "groq",
    "huggingface",
    "mistral",
    "ollama",
    "openai",
    "openrouter",
    "together_ai",
    "vertex_ai",
    "xai",
}


@dataclass(frozen=True)
class WatchTarget:
    """One workflow subscription target watched by the polling loop."""

    repository: str
    workflow_names: tuple[str, ...] = ()
    workflow_ids: tuple[int, ...] = ()
    namespace: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class Config:
    """Fully parsed runtime configuration for the agent process."""

    github_token: str
    discord_webhook_url: str | None
    discord_bot_token: str | None
    discord_channel_id: int | None
    poll_interval_seconds: int
    lookback_minutes: int
    max_runs_per_repo: int
    max_log_bytes: int
    max_discord_chars: int
    state_dir: Path
    triage_max_attempts: int
    triage_retry_initial_backoff_seconds: int
    triage_retry_max_backoff_seconds: int
    openhands_enabled: bool
    openhands_model: str
    openhands_api_key: str | None
    openhands_max_iterations: int
    incident_retention_max_count: int
    incident_retention_max_age_days: int
    operator_history_max_bytes: int
    watch_targets: tuple[WatchTarget, ...]


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse common truthy env-var forms while preserving a default."""

    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_targets(raw: str | None) -> tuple[WatchTarget, ...]:
    """Decode WATCH_TARGETS_JSON into strongly typed watch target entries."""

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


def _validate_openhands_model(model: str) -> str:
    """Require a provider-qualified OpenHands model name."""

    provider, _, _ = model.partition("/")
    if not provider or provider not in _SUPPORTED_OPENHANDS_MODEL_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_OPENHANDS_MODEL_PROVIDERS))
        raise ValueError(
            "OpenHands model configuration is invalid. "
            "The configured model needs an explicit provider prefix, for example "
            "`openhands/claude-sonnet-4-5-20250929`. "
            f"Configured model: `{model}`. Supported provider prefixes: {supported}"
        )
    return model


def load_config() -> Config:
    """Load process configuration from environment variables.

    This is the single entrypoint for translating deployment-time env vars into
    the typed Config object consumed by the rest of the service.
    """

    github_token = os.environ["GITHUB_TOKEN"]
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    discord_bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    discord_channel_id_raw = os.environ.get("DISCORD_CHANNEL_ID")
    discord_channel_id = int(discord_channel_id_raw) if discord_channel_id_raw else None
    state_dir = Path(os.environ.get("STATE_DIR", "/var/lib/control-plane-triage-agent"))
    state_dir.mkdir(parents=True, exist_ok=True)

    if not discord_bot_token and not discord_webhook_url:
        raise ValueError("One of DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL must be configured")
    if discord_bot_token and discord_channel_id is None:
        raise ValueError("DISCORD_CHANNEL_ID must be configured when DISCORD_BOT_TOKEN is set")

    openhands_enabled = _parse_bool(os.environ.get("OPENHANDS_ENABLED"), True)
    openhands_api_key = os.environ.get("OPENHANDS_LLM_API_KEY")
    if not openhands_enabled:
        raise ValueError(
            "OPENHANDS_ENABLED must remain true because this service requires OpenHands for all flows"
        )
    if not openhands_api_key:
        raise ValueError(
            "OPENHANDS_LLM_API_KEY must be configured because this service requires OpenHands for all flows"
        )
    openhands_model = _validate_openhands_model(
        os.environ.get("OPENHANDS_MODEL", "openhands/claude-sonnet-4-5-20250929")
    )

    return Config(
        github_token=github_token,
        discord_webhook_url=discord_webhook_url,
        discord_bot_token=discord_bot_token,
        discord_channel_id=discord_channel_id,
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "120")),
        lookback_minutes=int(os.environ.get("LOOKBACK_MINUTES", "120")),
        max_runs_per_repo=int(os.environ.get("MAX_RUNS_PER_REPO", "20")),
        max_log_bytes=int(os.environ.get("MAX_LOG_BYTES", str(512 * 1024))),
        max_discord_chars=int(os.environ.get("MAX_DISCORD_CHARS", "1800")),
        state_dir=state_dir,
        triage_max_attempts=int(os.environ.get("TRIAGE_MAX_ATTEMPTS", "3")),
        triage_retry_initial_backoff_seconds=int(
            os.environ.get("TRIAGE_RETRY_INITIAL_BACKOFF_SECONDS", "300")
        ),
        triage_retry_max_backoff_seconds=int(
            os.environ.get("TRIAGE_RETRY_MAX_BACKOFF_SECONDS", "3600")
        ),
        openhands_enabled=openhands_enabled,
        openhands_model=openhands_model,
        openhands_api_key=openhands_api_key,
        openhands_max_iterations=int(os.environ.get("OPENHANDS_MAX_ITERATIONS", "30")),
        incident_retention_max_count=int(os.environ.get("INCIDENT_RETENTION_MAX_COUNT", "25")),
        incident_retention_max_age_days=int(os.environ.get("INCIDENT_RETENTION_MAX_AGE_DAYS", "7")),
        operator_history_max_bytes=int(os.environ.get("OPERATOR_HISTORY_MAX_BYTES", str(128 * 1024))),
        watch_targets=_parse_targets(os.environ.get("WATCH_TARGETS_JSON")),
    )
