#!/usr/bin/env python3
"""
Observability Agent using OpenHands SDK.

This agent monitors GitHub Actions workflows for perf test failures and:
- Uses Grafana to analyze issues when tests fail
- Creates PRs to fix issues (if within codebase)
- Points out external integration issues (not in codebase)

Hosted as a constant runner on the control plane node.
All secrets are sourced from AWS SSM Parameter Store.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Structured JSON logging – stdout for containers / systemd / k8s
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload)


_handler = logging.StreamHandler(sys.stdout)
if LOG_FORMAT == "json":
    _handler.setFormatter(JsonFormatter())
else:
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

logger = logging.getLogger("observability-agent")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.addHandler(_handler)
logger.propagate = False

# ---------------------------------------------------------------------------
# Optional OpenHands SDK
# ---------------------------------------------------------------------------
try:
    from openhands.sdk import Agent, LLM, Conversation, Tool
    from openhands.sdk.tools import TerminalTool, FileEditorTool, TaskTrackerTool

    OPENHANDS_AVAILABLE = True
except ImportError:
    OPENHANDS_AVAILABLE = False
    logger.warning("OpenHands SDK not available – running in basic mode")


# ---------------------------------------------------------------------------
# Configuration – no hardcoded defaults for critical values
# ---------------------------------------------------------------------------
def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logger.fatal("Missing required environment variable: %s", name)
        sys.exit(1)
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


# These MUST be set in every deployment.
GITHUB_OWNER = _require_env("GITHUB_OWNER")
GITHUB_REPO = _require_env("GITHUB_REPO")
GITHUB_TOKEN = _require_env("GITHUB_TOKEN")
AWS_REGION = _require_env("AWS_REGION")
GRAFANA_URL = _require_env("GRAFANA_URL")

# SSM paths for secrets – keep them configurable.
GRAFANA_TOKEN_SSM_PATH = _optional_env(
    "GRAFANA_TOKEN_SSM_PATH", "/codex/grafana-service-account-token"
)
LLM_API_KEY_SSM_PATH = _optional_env(
    "LLM_API_KEY_SSM_PATH", "/flashsales/prod/llm-api-key"
)

# Agent behaviour
WORKFLOW_NAME = _optional_env(
    "WORKFLOW_NAME", "flashsales-perf-concurrency-suite.yml"
)
CHECK_INTERVAL = int(_optional_env("CHECK_INTERVAL", "300"))

# LLM / OpenRouter settings – non-secret values
LLM_MODEL = _optional_env("LLM_MODEL", "")
LLM_BASE_URL = _optional_env("LLM_BASE_URL", "")

# Analytics window – how far back to look for failed runs (hours)
LOOKBACK_HOURS = int(_optional_env("LOOKBACK_HOURS", "12"))


# ---------------------------------------------------------------------------
# SSM helpers
# ---------------------------------------------------------------------------
def _fetch_ssm_parameter(path: str) -> Optional[str]:
    """Return decrypted SSM SecureString value or None on failure."""
    try:
        import boto3

        client = boto3.client("ssm", region_name=AWS_REGION)
        resp = client.get_parameter(Name=path, WithDecryption=True)
        value = resp["Parameter"]["Value"]
        logger.debug("Fetched SSM parameter %s (len=%d)", path, len(value))
        return value
    except Exception:
        logger.exception("Failed to fetch SSM parameter %s", path)
        return None


def get_grafana_token() -> Optional[str]:
    return _fetch_ssm_parameter(GRAFANA_TOKEN_SSM_PATH)


def get_llm_api_key() -> Optional[str]:
    return _fetch_ssm_parameter(LLM_API_KEY_SSM_PATH)


# ---------------------------------------------------------------------------
# Grafana queries
# ---------------------------------------------------------------------------
def _grafana_query(
    expr: str, grafana_token: str, lookback_minutes: int = 60
) -> dict:
    """Run a Prometheus-style query against Grafana's data-source proxy."""
    headers = {
        "Authorization": f"Bearer {grafana_token}",
        "Content-Type": "application/json",
    }
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (lookback_minutes * 60 * 1000)

    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "expr": expr,
                "range": True,
                "start": start_ms,
                "end": end_ms,
                "step": 300,
            }
        ],
        "from": str(start_ms),
        "to": str(end_ms),
    }

    try:
        resp = requests.post(
            f"{GRAFANA_URL}/api/ds/query",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("Grafana query failed for expr=%s", expr)
        return {"error": str(sys.exc_info()[1])}


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------
_GITHUB_API = "https://api.github.com"


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def get_failed_workflow_runs() -> list[dict]:
    """Return recent failed runs for the configured workflow."""
    url = (
        f"{_GITHUB_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/{WORKFLOW_NAME}/runs"
    )
    since = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    params = {"status": "failure", "per_page": 10, "created": f">{since}"}

    try:
        resp = requests.get(url, headers=_github_headers(), params=params, timeout=30)
        resp.raise_for_status()
        runs: list[dict] = resp.json().get("workflow_runs", [])
        logger.info("Fetched %d failed workflow run(s)", len(runs))
        return runs
    except Exception:
        logger.exception("Failed to fetch workflow runs")
        return []


def get_run_jobs(run_id: int) -> list[dict]:
    url = f"{_GITHUB_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}/jobs"
    try:
        resp = requests.get(url, headers=_github_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("jobs", [])
    except Exception:
        logger.exception("Failed to fetch jobs for run %d", run_id)
        return []


# ---------------------------------------------------------------------------
# Failure analysis
# ---------------------------------------------------------------------------
def analyze_failure(run: dict, grafana_token: Optional[str]) -> dict:
    run_id: int = run["id"]
    run_name: str = run.get("name", "unknown")
    run_url: str = run.get("html_url", "")

    logger.info("Analyzing run %d (%s) — %s", run_id, run_name, run_url)

    analysis: dict = {
        "run_id": run_id,
        "run_name": run_name,
        "run_url": run_url,
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "failures": [],
        "recommendations": [],
        "external_issues": [],
        "code_issues": [],
    }

    for job in get_run_jobs(run_id):
        if job.get("conclusion") != "failure":
            continue

        job_name = job.get("name", "unknown-job")
        failure = {
            "job_name": job_name,
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "steps": [
                {"name": s["name"], "status": s["status"], "conclusion": s["conclusion"]}
                for s in job.get("steps", [])
                if s.get("conclusion") == "failure"
            ],
        }
        analysis["failures"].append(failure)

        jl = job_name.lower()
        if "loadtest" in jl or "k6" in jl:
            analysis["recommendations"].append(
                f"Analyze {job_name} with Grafana metrics"
            )
        elif "consistency" in jl:
            analysis["code_issues"].append(
                f"Consistency test failure in {job_name} – check service logic"
            )
        else:
            analysis["external_issues"].append(
                f"Unknown failure: {job_name} – investigate external dependencies"
            )

    # -------------------------------------------------------------------
    # If perf jobs failed AND we have a Grafana token, pull relevant panels.
    # -------------------------------------------------------------------
    has_perf_failure = any(
        "loadtest" in f.get("job_name", "").lower()
        or "k6" in f.get("job_name", "").lower()
        for f in analysis["failures"]
    )

    if has_perf_failure and grafana_token:
        logger.info("Perf failure detected – querying Grafana metrics")
        latency = _grafana_query("request_duration_seconds:avg", grafana_token)
        errors = _grafana_query("http_requests_total:rate5m", grafana_token)

        analysis["grafana_metrics"] = {
            "latency": latency,
            "errors": errors,
        }

        # Interpret latency
        frames = latency.get("results", {}).get("A", {}).get("frames", [])
        if frames:
            values = frames[0].get("data", {}).get("values", [[]])[0]
            if values:
                avg_lat = sum(values) / len(values)
                logger.info("Avg latency over window: %.1f ms", avg_lat)
                if avg_lat > 1000:
                    analysis["recommendations"].append(
                        "High latency – consider DB query optimization or caching"
                    )

        # Interpret error rate
        frames = errors.get("results", {}).get("A", {}).get("frames", [])
        if frames:
            values = frames[0].get("data", {}).get("values", [[]])[0]
            if values and max(values) > 10:
                analysis["recommendations"].append(
                    "High error rate – investigate service errors and deps"
                )

    return analysis


# ---------------------------------------------------------------------------
# PR creation (stub – real PR creation requires git operations)
# ---------------------------------------------------------------------------
def create_pr(analysis: dict) -> Optional[dict]:
    """Create a GitHub PR for code-level issues found during analysis."""
    code_issues = analysis.get("code_issues", [])
    if not code_issues:
        return None

    title = f"fix: perf test failure in {analysis['run_name']} (#{analysis['run_id']})"
    body_lines = [
        "## Summary",
        f"Address perf test failure detected in run [{analysis['run_id']}]({analysis['run_url']})",
        "",
        "## Identified Issues",
        *(f"- {i}" for i in code_issues),
        "",
        f"Analyzed by observability agent at {datetime.now(timezone.utc).isoformat()}",
    ]

    logger.info("Would create PR: %s", title)
    logger.debug("PR body:\n%s", "\n".join(body_lines))
    return {"title": title, "body": "\n".join(body_lines), "created": True}


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------
async def run_observability_agent() -> None:
    logger.info("Observability Agent starting")
    logger.info(
        "github=%s/%s  region=%s  interval=%ds  lookback=%dh",
        GITHUB_OWNER, GITHUB_REPO, AWS_REGION, CHECK_INTERVAL, LOOKBACK_HOURS,
    )

    grafana_token = get_grafana_token()
    if grafana_token:
        logger.info("Grafana token loaded from SSM %s", GRAFANA_TOKEN_SSM_PATH)
    else:
        logger.warning("Grafana token unavailable – metric queries disabled")

    llm_api_key = get_llm_api_key()
    if llm_api_key:
        logger.info("LLM API key loaded from SSM %s", LLM_API_KEY_SSM_PATH)

    # -----------------------------------------------------------------------
    # OpenHands agent initialisation (best-effort)
    # -----------------------------------------------------------------------
    agent = None
    if OPENHANDS_AVAILABLE and llm_api_key and LLM_MODEL:
        logger.info("Initialising OpenHands agent (model=%s)", LLM_MODEL)
        try:
            llm = LLM(
                model=LLM_MODEL,
                api_key=llm_api_key,
                base_url=LLM_BASE_URL or None,
            )
            agent = Agent(
                llm=llm,
                tools=[
                    Tool(name=TerminalTool.name),
                    Tool(name=FileEditorTool.name),
                    Tool(name=TaskTrackerTool.name),
                ],
                system_message=(
                    "You are the observability agent for the Flashsales platform."
                    " When perf tests fail you query Grafana, analyse the failure,"
                    " and create a PR with fixes when the root cause is in the codebase."
                    " If the failure is due to an external service, report it clearly."
                ),
            )
            logger.info("OpenHands agent initialised")
        except Exception:
            logger.exception(
                "Failed to initialise OpenHands agent – running in basic mode"
            )
            agent = None
    else:
        if not OPENHANDS_AVAILABLE:
            logger.info("OpenHands SDK not installed – basic mode")
        elif not llm_api_key:
            logger.warning("No LLM API key – skipping agent initialisation")
        elif not LLM_MODEL:
            logger.warning("LLM_MODEL not set – skipping agent initialisation")

    # -----------------------------------------------------------------------
    # Polling loop
    # -----------------------------------------------------------------------
    while True:
        try:
            runs = get_failed_workflow_runs()

            if not runs:
                logger.info("No failed runs in the last %dh", LOOKBACK_HOURS)
            else:
                for run in runs:
                    analysis = analyze_failure(run, grafana_token)

                    logger.info(
                        "run=%d  failures=%d  code_issues=%d  external=%d  recs=%d",
                        analysis["run_id"],
                        len(analysis["failures"]),
                        len(analysis["code_issues"]),
                        len(analysis["external_issues"]),
                        len(analysis["recommendations"]),
                    )

                    for issue in analysis["code_issues"]:
                        logger.warning("CODE: %s", issue)
                    for issue in analysis["external_issues"]:
                        logger.error("EXTERNAL: %s", issue)
                    for rec in analysis["recommendations"]:
                        logger.info("RECOMMENDATION: %s", rec)

                    # Create PR for code issues
                    create_pr(analysis)

                    # Optionally dispatch to OpenHands agent for deeper analysis
                    if analysis["failures"] and agent:
                        try:
                            prompt = (
                                "Analyse the following perf test failure and provide"
                                " root cause, code fix suggestions, and prevention steps:\n\n"
                                + json.dumps(analysis, indent=2, default=str)
                            )
                            conversation = Conversation(
                                agent=agent,
                                workspace="/workspace/project/homelab-cloud",
                            )
                            response = conversation.send_message(prompt)
                            logger.info(
                                "Agent response: %s", str(response)[:500]
                            )
                        except Exception:
                            logger.exception("OpenHands agent analysis failed")

            await asyncio.sleep(CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Agent loop cancelled – shutting down")
            break
        except Exception:
            logger.exception(
                "Unhandled error in agent loop – will retry after interval"
            )
            await asyncio.sleep(CHECK_INTERVAL)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info(
        "Observability Agent starting – log_level=%s log_format=%s",
        LOG_LEVEL, LOG_FORMAT,
    )
    try:
        asyncio.run(run_observability_agent())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
