#!/usr/bin/env python3
"""
Tests for the observability agent HTTP server – self-contained.

Usage:
    cd flashsale/perf/python
    python3 test_observability_agent.py
"""

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Set required env vars BEFORE importing the agent.
# ---------------------------------------------------------------------------
os.environ.setdefault("AGENT_AUTH_TOKEN", "test-secret-token")
os.environ.setdefault("GITHUB_OWNER", "test-org")
os.environ.setdefault("GITHUB_REPO", "test-repo")
os.environ.setdefault("GITHUB_TOKEN", "ghp_fake")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("GRAFANA_URL", "https://grafana.example.com")
os.environ.setdefault("LOG_FORMAT", "text")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import observability_agent as oa

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  ✓  {name}")
        passed += 1
    else:
        print(f"  ✗  {name}" + (f"  ({detail})" if detail else ""))
        failed += 1


def section(title: str) -> None:
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_imports() -> None:
    section("Imports")
    for mod in ("requests", "boto3", "json", "os", "sys", "logging", "threading", "http.server"):
        try:
            __import__(mod)
            check(f"import {mod}", True)
        except ImportError:
            check(f"import {mod}", False, "missing")


def test_logging_setup() -> None:
    section("Logging")
    import logging
    check("logger exists", hasattr(oa, "logger"))
    check("logger is Logger", isinstance(oa.logger, logging.Logger))
    check("logger has handler", len(oa.logger.handlers) > 0)

    # Verify JSON formatter still works
    fmt = oa.JsonFormatter()
    record = logging.LogRecord("test", 20, "", 0, "hello", (), None)
    output = fmt.format(record)
    parsed = json.loads(output)
    check("JSON has ts", "ts" in parsed)
    check("JSON has msg", parsed.get("msg") == "hello")


def test_config_validation() -> None:
    section("Config validation")
    check("_require_env callable", callable(oa._require_env))
    check("_optional_env callable", callable(oa._optional_env))
    check("LISTEN_PORT set", oa.LISTEN_PORT == 8080)
    check("AGENT_AUTH_TOKEN set", oa.AGENT_AUTH_TOKEN == "test-secret-token")

    with patch.object(sys, "exit") as mock_exit:
        oa._require_env("MISSING_VAR")
        check("_require_env exits on missing", mock_exit.called)


def test_ssm_fetch_mocked() -> None:
    section("SSM parameter fetch (mocked)")
    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "secret-abc"}}
        mock_boto.return_value = mock_client
        result = oa._fetch_ssm_parameter("/test/path")
        check("fetches SSM parameter", result == "secret-abc")


def test_github_api_mocked() -> None:
    section("GitHub API (mocked)")
    mock_jobs = MagicMock()
    mock_jobs.status_code = 200
    mock_jobs.json.return_value = {
        "jobs": [
            {
                "id": 1,
                "name": "k6 load test",
                "status": "completed",
                "conclusion": "failure",
                "steps": [
                    {"name": "Run k6", "status": "completed", "conclusion": "failure"}
                ],
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_jobs
        jobs = oa.get_run_jobs(42)
        check("fetches jobs", len(jobs) == 1)
        check("job name", jobs[0]["name"] == "k6 load test")


def test_analysis_structure() -> None:
    section("Failure analysis structure (mocked)")
    run = {
        "id": 99,
        "name": "loadtest",
        "html_url": "https://gh/t/r/99",
        "status": "completed",
        "conclusion": "failure",
    }

    mock_jobs = MagicMock()
    mock_jobs.status_code = 200
    mock_jobs.json.return_value = {
        "jobs": [
            {
                "id": 1,
                "name": "k6 load test",
                "status": "completed",
                "conclusion": "failure",
                "steps": [
                    {"name": "Run k6", "status": "completed", "conclusion": "failure"}
                ],
            }
        ]
    }

    # Mock both jobs and logs calls
    with patch("requests.get") as mock_get:
        mock_jobs_resp = MagicMock()
        mock_jobs_resp.status_code = 200
        mock_jobs_resp.json.return_value = mock_jobs.json.return_value
        mock_get.return_value = mock_jobs_resp

        analysis = oa.analyze_failure(run, grafana_token=None)

        check("has run_id", analysis["run_id"] == 99)
        check("has failures", len(analysis["failures"]) == 1)
        check("failure job name", analysis["failures"][0]["job_name"] == "k6 load test")
        check("has recommendation", len(analysis["recommendations"]) > 0)


def test_pr_creation() -> None:
    section("PR creation")
    analysis = {
        "run_id": 10,
        "run_name": "smoke",
        "run_url": "https://gh/t/r/10",
        "code_issues": ["Consistency test failure – check service logic"],
        "external_issues": [],
        "failures": [],
        "recommendations": [],
    }
    pr = oa.create_pr(analysis)
    check("creates PR for code issues", pr is not None)
    check("has title", "fix:" in pr["title"])
    check("has body", "Consistency" in pr["body"])
    pr2 = oa.create_pr({"code_issues": []})
    check("no PR when no code issues", pr2 is None)


def test_grafana_query_mocked() -> None:
    section("Grafana query (mocked)")
    check("_grafana_query callable", callable(oa._grafana_query))
    with patch("requests.post") as mock_post:
        mock_post.side_effect = __import__("requests").ConnectionError("timeout")
        result = oa._grafana_query("up", "fake-token")
        check("returns error dict on failure", "error" in result)


def test_get_run_logs_mocked() -> None:
    section("Run logs fetch (mocked)")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "line 1\nline 2\n... lots of logs ..."
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_resp
        logs = oa.get_run_logs(42)
        check("fetches logs", len(logs) > 0)


def test_agent_handler_methods() -> None:
    section("HTTP handler methods")
    check("AgentHandler has do_GET", hasattr(oa.AgentHandler, "do_GET"))
    check("AgentHandler has do_POST", hasattr(oa.AgentHandler, "do_POST"))
    check("AgentHandler has _respond", hasattr(oa.AgentHandler, "_respond"))
    check("AgentHandler has log_message", hasattr(oa.AgentHandler, "log_message"))

    # Verify the auth check code path exists by inspecting the method source
    import inspect
    source = inspect.getsource(oa.AgentHandler.do_POST)
    check("do_POST checks X-Agent-Token", "X-Agent-Token" in source)
    check("do_POST returns 403 on bad token", "403" in source)
    check("do_POST returns 202 on success", "202" in source)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("Observability Agent Test Suite (HTTP Server)")
    print("=" * 60)

    test_imports()
    test_logging_setup()
    test_config_validation()
    test_ssm_fetch_mocked()
    test_github_api_mocked()
    test_analysis_structure()
    test_pr_creation()
    test_grafana_query_mocked()
    test_get_run_logs_mocked()
    test_agent_handler_methods()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed  ({passed + failed} total)")
    print("=" * 60)

    if failed:
        print("\n✗ Some tests FAILED")
        return 1
    print("\n✓ All tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
