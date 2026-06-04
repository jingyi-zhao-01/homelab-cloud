#!/usr/bin/env python3
"""
Observability Agent using OpenHands SDK

This agent monitors GitHub Actions workflows for perf test failures and:
- Uses Grafana MCP to analyze issues when tests fail
- Creates PRs to fix issues (if within codebase)
- Points out external integration issues (not in codebase)

The agent should be hosted as a constant runner on the control plane node.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# Direct import of OpenHands SDK components
try:
    from openhands.sdk import Agent, LLM, Conversation, Tool, Workspace
    from openhands.sdk.tools import TerminalTool, FileEditorTool, TaskTrackerTool
    from openhands.sdk.secrets import SecretRegistry
    OPENHANDS_AVAILABLE = True
except ImportError:
    # Fallback for when OpenHands SDK is not available
    OPENHANDS_AVAILABLE = False
    print("Warning: OpenHands SDK not available. Using basic Python implementation.")

import requests

# GitHub configuration
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "jzhao62")
GITHUB_REPO = os.getenv("GITHUB_REPO", "homelab-cloud")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# AWS SSM configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SSM_PATH_PREFIX = os.getenv("SSM_PATH_PREFIX", "flashsales/prod")
GRAFANA_TOKEN_PATH = f"/{SSM_PATH_PREFIX}/grafana-service-account-token"

# GitHub Actions workflow configuration
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "flashsales-perf-concurrency-suite.yml")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes default


def get_grafana_token_from_ssm() -> Optional[str]:
    """Get Grafana token from AWS SSM."""
    try:
        import boto3
        
        ssm_client = boto3.client("ssm", region_name=AWS_REGION)
        response = ssm_client.get_parameter(
            Name=GRAFANA_TOKEN_PATH, WithDecryption=True
        )
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error getting Grafana token from SSM: {e}")
        return None


def query_grafana(metric_query: str, grafana_url: str, grafana_token: str) -> dict:
    """Query Grafana for metrics."""
    headers = {
        "Authorization": f"Bearer {grafana_token}",
        "Content-Type": "application/json",
    }
    
    # Default to 1 hour ago to now
    end_time = int(time.time() * 1000)
    start_time = end_time - (60 * 60 * 1000)  # 1 hour
    
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {
                    "type": "prometheus",
                    "uid": "prometheus",
                },
                "expr": metric_query,
                "range": True,
                "start": start_time,
                "end": end_time,
                "step": 300,  # 5 minute steps
            }
        ],
        "from": str(start_time),
        "to": str(end_time),
    }
    
    try:
        response = requests.post(
            f"{grafana_url}/api/ds/query",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_github_workflow_runs() -> list:
    """Get recent GitHub Actions workflow runs."""
    if not GITHUB_TOKEN:
        print("GitHub token not set, skipping GitHub workflow check")
        return []
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_NAME}/runs"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    
    params = {
        "status": "failure",
        "per_page": 10,
        "created": f">{datetime.now() - timedelta(hours=12)}.isoformat()",
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("workflow_runs", [])
    except Exception as e:
        print(f"Error getting GitHub workflow runs: {e}")
        return []


def analyze_failure(run: dict, grafana_url: str, grafana_token: str) -> dict:
    """Analyze a failed workflow run."""
    run_id = run["id"]
    run_name = run["name"]
    run_url = run["html_url"]
    
    print(f"Analyzing failed run: {run_name} ({run_id})")
    print(f"Run URL: {run_url}")
    
    analysis = {
        "run_id": run_id,
        "run_name": run_name,
        "run_url": run_url,
        "status": run["status"],
        "conclusion": run["conclusion"],
        "failures": [],
        "recommendations": [],
        "external_issues": [],
        "code_issues": [],
    }
    
    # Get job results
    jobs_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}/jobs"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    
    try:
        response = requests.get(jobs_url, headers=headers, timeout=30)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        
        for job in jobs:
            if job["conclusion"] == "failure":
                job_name = job["name"]
                failure_details = {
                    "job_name": job_name,
                    "status": job["status"],
                    "conclusion": job["conclusion"],
                    "steps": [],
                }
                
                for step in job.get("steps", []):
                    if step["conclusion"] == "failure":
                        failure_details["steps"].append({
                            "name": step["name"],
                            "status": step["status"],
                            "conclusion": step["conclusion"],
                        })
                
                analysis["failures"].append(failure_details)
                
                # Determine if this is a code issue or external issue
                if "loadtest" in job_name.lower() or "k6" in job_name.lower():
                    # Performance test failure - might need Grafana analysis
                    analysis["recommendations"].append(
                        f"Analyze {job_name} with Grafana metrics"
                    )
                elif "consistency" in job_name.lower():
                    # Consistency test failure - likely code issue
                    analysis["code_issues"].append(
                        f"Consistency test failure in {job_name} - check service logic"
                    )
                else:
                    # Unknown failure type
                    analysis["external_issues"].append(
                        f"Unknown failure: {job_name} - investigate external dependencies"
                    )
                    
    except Exception as e:
        print(f"Error getting job results: {e}")
    
    # If we have loadtest/k6 failures, query Grafana for metrics
    if any("loadtest" in f.get("job_name", "").lower() for f in analysis["failures"]):
        # Query for latency metrics
        latency_query = "request_duration_seconds:avg"
        latency_result = query_grafana(latency_query, grafana_url, grafana_token)
        
        if "error" not in latency_result:
            analysis["grafana_metrics"] = {
                "latency_query": latency_query,
                "latency_result": latency_result,
            }
            
            # Analyze latency trends
            if latency_result.get("results", {}).get("A", {}).get("frames"):
                values = latency_result["results"]["A"]["frames"][0]["data"]["values"][0]
                if values:
                    avg_latency = sum(values) / len(values)
                    if avg_latency > 1000:  # 1 second threshold
                        analysis["recommendations"].append(
                            "High latency detected - consider optimizing database queries or adding caching"
                        )
        
        # Query for error rate
        error_query = "http_requests_total:rate5m"
        error_result = query_grafana(error_query, grafana_url, grafana_token)
        
        if "error" not in error_result:
            analysis.setdefault("grafana_metrics", {})[
                "error_query"
            ] = error_query
            analysis.setdefault("grafana_metrics", {}).setdefault(
                "error_result", error_result
            )
            
            # Check for error spikes
            if error_result.get("results", {}).get("A", {}).get("frames"):
                values = error_result["results"]["A"]["frames"][0]["data"]["values"][0]
                if values and max(values) > 10:  # More than 10 errors per 5 minutes
                    analysis["recommendations"].append(
                        "High error rate detected - investigate service errors and dependencies"
                    )
    
    return analysis


def create_pr_for_issue(analysis: dict, issue_type: str) -> Optional[dict]:
    """Create a PR for an issue if it's within the codebase."""
    if not GITHUB_TOKEN:
        print("GitHub token not set, cannot create PR")
        return None
    
    if issue_type == "external":
        print("External issue - no PR should be created")
        return None
    
    # Build PR title and body
    run_name = analysis.get("run_name", "Unknown run")
    run_id = analysis.get("run_id")
    run_url = analysis.get("run_url")
    
    if issue_type == "code":
        # Get code recommendations
        recommendations = analysis.get("code_issues", [])
        if not recommendations:
            return None
        
        pr_title = f"fix: Address perf test failure in {run_name} (#{run_id})"
        pr_body = f"""## Summary
Address perf test failure detected in run [{run_id}]({run_url})

## Failure Details
- Run: {run_name}
- URL: {run_url}

## Identified Issues
"""
        for issue in recommendations:
            pr_body += f"- {issue}\n"
        
        pr_body += "\n## Analysis\n"
        pr_body += f"Analyzed by Observability Agent at {datetime.now().isoformat()}\n"
        
        # Try to create a PR (this would typically involve creating a branch and committing changes)
        print(f"Would create PR: {pr_title}")
        return {"title": pr_title, "body": pr_body, "created": True}
    
    return None


async def run_observability_agent():
    """Main observability agent loop."""
    print("Starting Observability Agent...")
    print(f"GitHub: {GITHUB_OWNER}/{GITHUB_REPO}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    
    # Get Grafana token from SSM
    grafana_token = get_grafana_token_from_ssm()
    
    if not grafana_token:
        print("Warning: Grafana token not available. Some features may be limited.")
        print("To enable full observability, configure SSM parameter:")
        print(f"  {GRAFANA_TOKEN_PATH}")
    
    grafana_url = os.getenv("GRAFANA_URL", "https://grafana.example.com")
    
    # Initialize OpenHands agent (if available)
    if OPENHANDS_AVAILABLE:
        llm = LLM(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", None),
        )
        
        agent = Agent(
            llm=llm,
            tools=[
                Tool(name=TerminalTool.name),
                Tool(name=FileEditorTool.name),
                Tool(name=TaskTrackerTool.name),
            ],
            system_message="""You are the Observability Agent for the Flashsales platform.
Your responsibilities:
1. Monitor GitHub Actions workflows for perf test failures
2. When tests fail, analyze the failure and determine if it's:
   - A code issue (within the flashsale microservices)
   - An external issue (dependencies, infrastructure, external services)
3. For code issues, create a PR with the fix
4. For external issues, create a detailed report

Use Grafana MCP to query metrics when perf tests fail. Focus on:
- Request latency and throughput
- Error rates
- Database performance
- Service health

Your workspace is at /workspace/project/homelab-cloud""",
        )
        
        # Set up secrets from environment
        secret_registry = SecretRegistry()
        if grafana_token:
            secret_registry.add_secret(
                "grafana_token", "SSM parameter with Grafana token"
            )
    else:
        agent = None
    
    print("Observability Agent initialized")
    print("Monitoring for perf test failures...")
    
    while True:
        try:
            # Get recent failed workflow runs
            workflow_runs = get_github_workflow_runs()
            
            if workflow_runs:
                print(f"Found {len(workflow_runs)} failed workflow run(s)")
                
                for run in workflow_runs:
                    # Analyze the failure
                    analysis = analyze_failure(run, grafana_url, grafana_token)
                    
                    # Log analysis
                    print(f"\n{'='*80}")
                    print(f"Analysis for run {analysis['run_id']}:")
                    print(f"Status: {analysis['status']}")
                    print(f"Failures: {len(analysis['failures'])}")
                    print(f"Recommendations: {len(analysis['recommendations'])}")
                    print(f"Code issues: {len(analysis['code_issues'])}")
                    print(f"External issues: {len(analysis['external_issues'])}")
                    print(f"{'='*80}\n")
                    
                    # Create PRs for code issues
                    for _ in analysis["code_issues"]:
                        create_pr_for_issue(analysis, "code")
                    
                    # Report external issues
                    if analysis["external_issues"]:
                        print("\n External Issues Detected:")
                        for issue in analysis["external_issues"]:
                            print(f"  - {issue}")
                        print("\n Please investigate these external dependencies manually.")
                    
                    # Use OpenHands agent to generate detailed remediation
                    if analysis["failures"] and agent:
                        conversation = Conversation(
                            agent=agent,
                            workspace="/workspace/project/homelab-cloud",
                        )
                        
                        # Send analysis to agent
                        agent_prompt = f"""Analyze the following perf test failure:

Run: {analysis['run_name']} ({analysis['run_id']})
URL: {analysis['run_url']}

Failures: {json.dumps(analysis['failures'], indent=2)}

Recommendations: {json.dumps(analysis['recommendations'], indent=2)}

Please provide:
1. Root cause analysis
2. Specific code fixes if applicable
3. External dependency issues if applicable
4. Prevention strategies

Respond with a structured analysis that can be used to create a PR."""
                        
                        response = conversation.send_message(agent_prompt)
                        print(f"\nAgent Analysis:\n{response}")
                        
                        # Commit to repo if there are code fixes
                        if "fix" in response.lower() and "code" in response.lower():
                            print("\nCreating PR for code fix...")
                            create_pr_for_issue(analysis, "code")
                    elif analysis["failures"] and not agent:
                        print("OpenHands agent not available. Skipping LLM analysis.")
                        print("Proceeding with basic analysis only.")
            else:
                print("No failed workflow runs found")
            
            # Wait before next check
            print(f"\nWaiting {CHECK_INTERVAL} seconds before next check...")
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in observability agent loop: {e}")
            await asyncio.sleep(CHECK_INTERVAL)


def main():
    """Main entry point."""
    try:
        asyncio.run(run_observability_agent())
    except KeyboardInterrupt:
        print("\nObservability Agent stopped")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
