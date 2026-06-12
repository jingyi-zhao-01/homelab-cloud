from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import requests

from core.config import WatchTarget
from core.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class GitHubActionsClient:
    def __init__(self, token: str, max_log_bytes: int) -> None:
        self._max_log_bytes = max_log_bytes
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "control-plane-triage-agent",
        }

    async def list_recent_runs(self, repository: str, per_page: int) -> list[dict]:
        with tracer.start_as_current_span("github.list_recent_runs") as span:
            span.set_attribute("github.repository", repository)
            span.set_attribute("github.per_page", per_page)
            logger.info("Fetching GitHub Actions runs repository=%s per_page=%s", repository, per_page)
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{repository}/actions/runs",
                    params={"per_page": per_page},
                )
                response.raise_for_status()
                runs = response.json().get("workflow_runs", [])
            span.set_attribute("github.run_count", len(runs))
            logger.info("Fetched GitHub Actions runs repository=%s count=%s", repository, len(runs))
            return runs

    async def list_jobs(self, repository: str, run_id: int) -> list[dict]:
        with tracer.start_as_current_span("github.list_jobs") as span:
            span.set_attribute("github.repository", repository)
            span.set_attribute("github.run_id", run_id)
            logger.info("Fetching GitHub Actions jobs repository=%s run_id=%s", repository, run_id)
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs",
                    params={"per_page": 100},
                )
                response.raise_for_status()
                jobs = response.json().get("jobs", [])
            span.set_attribute("github.job_count", len(jobs))
            logger.info("Fetched GitHub Actions jobs repository=%s run_id=%s count=%s", repository, run_id, len(jobs))
            return jobs

    async def download_run_logs(self, repository: str, run_id: int) -> dict[str, str]:
        with tracer.start_as_current_span("github.download_run_logs") as span:
            span.set_attribute("github.repository", repository)
            span.set_attribute("github.run_id", run_id)
            logger.info("Downloading GitHub Actions logs repository=%s run_id=%s", repository, run_id)
            async with httpx.AsyncClient(headers=self._headers, timeout=60, follow_redirects=True) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/logs",
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
            span.set_attribute("github.log_file_count", len(collected))
            logger.info(
                "Downloaded GitHub Actions logs repository=%s run_id=%s files=%s bytes_collected=%s bytes_remaining=%s",
                repository,
                run_id,
                len(collected),
                sum(len(text.encode("utf-8", errors="ignore")) for text in collected.values()),
                remaining,
            )
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
    logger.info(
        "Matched runs namespace=%s workflow_names=%s workflow_ids=%s branch=%s lookback_minutes=%s matched=%s",
        target.namespace,
        list(target.workflow_names),
        list(target.workflow_ids),
        target.branch,
        lookback_minutes,
        len(matched),
    )
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
                logger.info("No explicit failure lines found; using raw snippet file=%s chars=%s", filename, len(snippet))
                return f"[{filename}]\n{snippet}"
    excerpt = "\n".join(interesting_lines)[:limit]
    logger.info("Extracted failure excerpt lines=%s chars=%s", len(interesting_lines), len(excerpt))
    return excerpt
