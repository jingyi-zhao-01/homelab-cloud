#!/usr/bin/env python3
"""
Tests for the observability agent – self-contained, no external services needed.

Usage:
    cd flashsale/perf/python
    python3 test_observability_agent.py
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Set required env vars BEFORE importing observability_agent.
# The module calls _require_env at module scope.
# ---------------------------------------------------------------------------
os.environ.setdefault("GITHUB_OWNER", "test-org")
os.environ.setdefault("GITHUB_REPO", "test-repo")
os.environ.setdefault("GITHUB_TOKEN", "ghp_fake")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("GRAFANA_URL", "https://grafana.example.com")

# Import the module-under-test
import observability_agent as oa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  ✓ PASS  {name}")
        passed += 1
    else:
        print(f"  ✗ FAIL  {name}" + (f"  ({detail})" if detail else ""))
        failed += 1


def section(title: str) -> None:
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_imports() -> None:
    section("Imports")
    for mod in ("requests", "boto3", "json", "os", "sys", "logging"):
        try:
            __import__(mod)
            check(f"import {mod}", True)
        except ImportError:
            check(f"import {mod}", False, "missing")


def test_logging_setup() -> None:
    section("Logging")
    try:
        import logging

        check("logger exists", hasattr(oa, "logger"))
        check("logger is Logger", isinstance(oa.logger, logging.Logger))
        check("logger has handler", len(oa.logger.handlers) > 0)

        # Verify JSON format produces valid JSON
        fmt = oa._handler.formatter
        log_record = logging.LogRecord("test", 20, "", 0, "hello", (), None)
        output = fmt.format(log_record)
        parsed = json.loads(output)
        check("JSON log format parses", "ts" in parsed and "level" in parsed)
        check("JSON has msg field", parsed.get("msg") == "hello")
    except Exception as e:
        check("logging setup", False, str(e))


def test_config_validation() -> None:
    section("Config validation – missing required vars")

    check("_require_env is callable", callable(oa._require_env))
    check("_optional_env is callable", callable(oa._optional_env))

    # Test that _require_env exits on missing
    with patch.object(sys, "exit") as mock_exit:
        oa._require_env("MISSING_VAR")
        check("_require_env exits on missing var", mock_exit.called)


def test_ssm_fetch_mocked() -> None:
    section("SSM parameter fetch (mocked)")

    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "secret-token-abc123"}
        }
        mock_boto.return_value = mock_client

        result = oa._fetch_ssm_parameter("/test/path")
        check("fetches SSM parameter", result == "secret-token-abc123")


def test_github_fetch_mocked() -> None:
    section("GitHub workflow run fetch (mocked)")

    mock_run = {
        "id": 42,
        "name": "loadtest",
        "html_url": "https://github.com/t/r/42",
        "status": "completed",
        "conclusion": "failure",
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"workflow_runs": [mock_run]}
        mock_get.return_value = mock_resp

        runs = oa.get_failed_workflow_runs()
        check("fetches failed runs", len(runs) == 1)
        check("correct run id", runs[0]["id"] == 42)


def test_analysis_structure() -> None:
    section("Failure analysis structure (mocked)")

    run = {
        "id": 99,
        "name": "loadtest",
        "html_url": "https://gh/t/r/99",
        "status": "completed",
        "conclusion": "failure",
    }

    # Mock jobs response
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
                    {
                        "name": "Run k6",
                        "status": "completed",
                        "conclusion": "failure",
                    }
                ],
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_jobs

        analysis = oa.analyze_failure(run, grafana_token=None)

        check("has run_id", analysis["run_id"] == 99)
        check("has failures", len(analysis["failures"]) == 1)
        check("failure job name", analysis["failures"][0]["job_name"] == "k6 load test")
        check(
            "recommendation",
            len(analysis["recommendations"]) > 0,
        )


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

    # No code issues = no PR
    pr2 = oa.create_pr({"code_issues": []})
    check("no PR when no code issues", pr2 is None)


def test_grafana_query_interface() -> None:
    section("Grafana query interface")

    check("_grafana_query is callable", callable(oa._grafana_query))

    # Quick mock to verify it doesn't crash when Grafana is unavailable
    with patch("requests.post") as mock_post:
        mock_post.side_effect = __import__("requests").ConnectionError("timeout")
        result = oa._grafana_query("up", "fake-token")
        check("returns error dict on Grafana failure", "error" in result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("Observability Agent Test Suite")
    print("=" * 60)

    test_imports()
    test_logging_setup()
    test_config_validation()
    test_ssm_fetch_mocked()
    test_github_fetch_mocked()
    test_analysis_structure()
    test_pr_creation()
    test_grafana_query_interface()

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
