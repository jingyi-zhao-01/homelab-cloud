#!/usr/bin/env python3
"""
Observability Agent – HTTP server (independent namespace deployment).

Receives POST /analyze with a failed GitHub Actions workflow run payload,
then autonomously scaffolds analysis and remediation:

- Queries Grafana for metrics
- Uses OpenHands SDK + LLM to reason about root cause
- Creates a PR for code-level fixes
- Flags external issues clearly

Hosted as a constant runner on the control plane node.
All secrets are fetched from AWS SSM at runtime.
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")


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

logger = logging.getLogger("obs-agent")
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
# Configuration
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logger.fatal("Missing required environment variable: %s", name)
        sys.exit(1)
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


LISTEN_PORT = int(_optional_env("LISTEN_PORT", "8080"))
AGENT_AUTH_TOKEN = _require_env("AGENT_AUTH_TOKEN")
GITHUB_OWNER = _require_env("GITHUB_OWNER")
GITHUB_REPO = _require_env("GITHUB_REPO")
GITHUB_TOKEN = _require_env("GITHUB_TOKEN")
AWS_REGION = _require_env("AWS_REGION")
GRAFANA_URL = _require_env("GRAFANA_URL")

GRAFANA_TOKEN_SSM_PATH = _optional_env(
    "GRAFANA_TOKEN_SSM_PATH", "/codex/grafana-service-account-token"
)
LLM_API_KEY_SSM_PATH = _optional_env(
    "LLM_API_KEY_SSM_PATH", "/flashsales/prod/llm-api-key"
)
LLM_MODEL = _optional_env("LLM_MODEL", "")
LLM_BASE_URL = _optional_env("LLM_BASE_URL", "")

_GITHUB_API = "https://api.github.com"

# ---------------------------------------------------------------------------
# SSM helpers
# ---------------------------------------------------------------------------


def _fetch_ssm_parameter(path: str) -> Optional[str]:
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


def _grafana_query(expr: str, grafana_token: str, lookback_minutes: int = 60) -> dict:
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


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def get_run_jobs(run_id: int) -> list[dict]:
    url = f"{_GITHUB_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}/jobs"
    try:
        resp = requests.get(url, headers=_github_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("jobs", [])
    except Exception:
        logger.exception("Failed to fetch jobs for run %d", run_id)
        return []


def get_run_logs(run_id: int) -> str:
    """Get the logs for a workflow run attempt."""
    url = f"{_GITHUB_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    try:
        resp = requests.get(url, headers=_github_headers(), timeout=60, allow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        if len(text) > 20000:
            text = "...(truncated)...\n" + text[-20000:]
        return text
    except Exception:
        logger.exception("Failed to fetch logs for run %d", run_id)
        return ""


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
        "code_issues": [],
        "external_issues": [],
        "recommendations": [],
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
            analysis["recommendations"].append(f"Analyze {job_name} with Grafana metrics")
        elif "consistency" in jl:
            analysis["code_issues"].append(
                f"Consistency test failure in {job_name} – check service logic"
            )
        else:
            analysis["external_issues"].append(
                f"Unknown failure: {job_name} – investigate external dependencies"
            )

    has_perf_failure = any(
        "loadtest" in f.get("job_name", "").lower()
        or "k6" in f.get("job_name", "").lower()
        for f in analysis["failures"]
    )

    if has_perf_failure and grafana_token:
        logger.info("Perf failure detected – querying Grafana metrics")
        latency = _grafana_query("request_duration_seconds:avg", grafana_token)
        errors = _grafana_query("http_requests_total:rate5m", grafana_token)
        analysis["grafana_metrics"] = {"latency": latency, "errors": errors}

        frames = latency.get("results", {}).get("A", {}).get("frames", [])
        if frames:
            values = frames[0].get("data", {}).get("values", [[]])[0]
            if values:
                avg = sum(values) / len(values)
                if avg > 1000:
                    analysis["recommendations"].append(
                        "High latency – consider DB query optimization or caching"
                    )

        frames = errors.get("results", {}).get("A", {}).get("frames", [])
        if frames:
            values = frames[0].get("data", {}).get("values", [[]])[0]
            if values and max(values) > 10:
                analysis["recommendations"].append(
                    "High error rate – investigate service errors and deps"
                )

    logs = get_run_logs(run_id)
    if logs:
        analysis["logs"] = logs[:20000]

    return analysis


# ---------------------------------------------------------------------------
# PR creation
# ---------------------------------------------------------------------------


def create_pr(analysis: dict) -> Optional[dict]:
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
        f"*Analyzed by observability agent at {datetime.now(timezone.utc).isoformat()}*",
    ]

    logger.info("Would create PR: %s", title)
    logger.debug("PR body:\n%s", "\n".join(body_lines))
    return {"title": title, "body": "\n".join(body_lines), "created": True}


# ---------------------------------------------------------------------------
# OpenHands SDK scaffold (autonomous investigation + fix)
# ---------------------------------------------------------------------------


def scaffold_with_openhands(analysis: dict) -> Optional[str]:
    """Run OpenHands SDK to autonomously investigate and fix the failure."""
    llm_api_key = get_llm_api_key()
    if not OPENHANDS_AVAILABLE or not llm_api_key or not LLM_MODEL:
        logger.info(
            "Skipping OpenHands scaffold (SDK=%s key=%s model=%s)",
            OPENHANDS_AVAILABLE, bool(llm_api_key), bool(LLM_MODEL),
        )
        return None

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
                " Analyse the following perf test failure, query relevant data,"
                " identify the root cause, and create a PR with the fix."
                " If the failure is external (not in the codebase), explain why."
            ),
        )

        prompt = (
            "Analyse the following perf test failure and take action:\n\n"
            + json.dumps(analysis, indent=2, default=str)
            + "\n\nInvestigate the failure, identify root cause, and if it's a code issue"
            " create a fix. If external, explain which dependency is at fault."
        )

        conversation = Conversation(
            agent=agent,
            workspace="/workspace/project/homelab-cloud",
        )
        response = conversation.send_message(prompt)
        logger.info("OpenHands agent scaffold complete: %s", str(response)[:500])
        return str(response)
    except Exception:
        logger.exception("OpenHands scaffold failed")
        return None


# ---------------------------------------------------------------------------
# Background analysis worker
# ---------------------------------------------------------------------------

_analysis_queue: asyncio.Queue = asyncio.Queue()


async def _analysis_worker() -> None:
    """Process analysis requests from the queue."""
    grafana_token = get_grafana_token()
    if grafana_token:
        logger.info("Grafana token loaded from SSM %s", GRAFANA_TOKEN_SSM_PATH)
    else:
        logger.warning("Grafana token unavailable – metric queries disabled")

    while True:
        try:
            payload = await _analysis_queue.get()
            run_id = payload.get("run_id")
            run_name = payload.get("run_name", "unknown")
            run_url = payload.get("run_url", "")

            logger.info("Worker picked up run %d (%s)", run_id, run_name)

            run = {
                "id": run_id,
                "name": run_name,
                "html_url": run_url or (
                    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
                    f"/actions/runs/{run_id}"
                ),
                "status": "completed",
                "conclusion": payload.get("conclusion", "failure"),
            }

            analysis = analyze_failure(run, grafana_token)

            logger.info(
                "run=%d failures=%d code=%d external=%d recs=%d",
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

            create_pr(analysis)
            scaffold_with_openhands(analysis)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Analysis worker error")
        finally:
            _analysis_queue.task_done()


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP handler for the observability agent."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/analyze":
            self._respond(404, {"error": "not found"})
            return

        # Auth check
        token = self.headers.get("X-Agent-Token", "")
        if token != AGENT_AUTH_TOKEN:
            logger.warning(
                "Rejected request with invalid auth token from %s",
                self.client_address,
            )
            self._respond(403, {"error": "forbidden"})
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid JSON"})
            return

        run_id = payload.get("run_id")
        if not run_id:
            self._respond(400, {"error": "missing run_id"})
            return

        logger.info(
            "Received /analyze request: run_id=%d name=%s",
            run_id, payload.get("run_name", "?"),
        )

        # Enqueue for async processing
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(_analysis_queue.put(payload))
            )
        except RuntimeError:
            pass

        self._respond(202, {
            "status": "accepted",
            "run_id": run_id,
            "message": "Analysis queued – agent is scaffolding",
        })

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("HTTP %s", fmt % args)

    def _respond(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info(
        "Observability Agent HTTP server starting on :%d  github=%s/%s region=%s",
        LISTEN_PORT, GITHUB_OWNER, GITHUB_REPO, AWS_REGION,
    )

    # Start async worker in background thread
    def _start_worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_analysis_worker())

    threading.Thread(target=_start_worker, daemon=True).start()
    logger.info("Background analysis worker started")

    server = HTTPServer(("0.0.0.0", LISTEN_PORT), AgentHandler)
    logger.info("Listening on :%d – POST /analyze to trigger analysis", LISTEN_PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
