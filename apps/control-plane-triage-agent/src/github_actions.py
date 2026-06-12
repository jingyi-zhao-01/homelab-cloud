from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone

import requests

from config import WatchTarget


class GitHubActionsClient:
    def __init__(self, token: str, max_log_bytes: int) -> None:
        self._max_log_bytes = max_log_bytes
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "control-plane-triage-agent",
            }
        )

    def list_recent_runs(self, repository: str, per_page: int) -> list[dict]:
        response = self._session.get(
            f"https://api.github.com/repos/{repository}/actions/runs",
            params={"per_page": per_page},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("workflow_runs", [])

    def list_jobs(self, repository: str, run_id: int) -> list[dict]:
        response = self._session.get(
            f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs",
            params={"per_page": 100},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("jobs", [])

    def download_run_logs(self, repository: str, run_id: int) -> dict[str, str]:
        response = self._session.get(
            f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/logs",
            timeout=60,
            allow_redirects=True,
        )
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        collected: dict[str, str] = {}
        remaining = self._max_log_bytes
        for name in archive.namelist():
            if remaining <= 0:
                break
            data = archive.read(name)[:remaining]
            remaining -= len(data)
            collected[name] = data.decode("utf-8", errors="replace")
        return collected


def match_runs(runs: list[dict], target: WatchTarget, lookback_minutes: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    matched: list[dict] = []
    for run in runs:
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") in {"success", "skipped"}:
            continue
        created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created_at < cutoff:
            continue
        if target.branch and run.get("head_branch") != target.branch:
            continue
        if target.workflow_names and run.get("name") not in target.workflow_names:
            continue
        if target.workflow_ids and int(run.get("workflow_id", 0)) not in target.workflow_ids:
            continue
        matched.append(run)
    return matched


def extract_failure_excerpt(logs: dict[str, str], limit: int = 4000) -> str:
    interesting_lines: list[str] = []
    for filename, text in logs.items():
        for line in text.splitlines():
            lower = line.lower()
            if any(token in lower for token in ["error", "exception", "failed", "traceback", "panic", "timeout"]):
                interesting_lines.append(f"[{filename}] {line}")
                if sum(len(entry) for entry in interesting_lines) >= limit:
                    break
        if sum(len(entry) for entry in interesting_lines) >= limit:
            break
    if not interesting_lines:
        for filename, text in logs.items():
            snippet = text[:limit]
            if snippet:
                return f"[{filename}]\n{snippet}"
    return "\n".join(interesting_lines)[:limit]
