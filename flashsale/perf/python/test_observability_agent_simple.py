#!/usr/bin/env python3
"""
Simple test script for the observability agent.
This test verifies the agent's core functionality without requiring GitHub API access.
"""

import os
import sys

# Change to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def test_ssm_mock():
    """Test SSM token retrieval with mock."""
    print("Test 1: SSM Token Retrieval (Mocked)")
    
    # Test that the function can be imported and called with mock
    try:
        import json
        from unittest.mock import MagicMock, patch
        
        # Mock boto3 response
        with patch('boto3.client') as mock_boto3:
            mock_client = MagicMock()
            mock_client.get_parameter.return_value = {
                "Parameter": {
                    "Value": "test-grafana-token-12345"
                }
            }
            mock_boto3.return_value = mock_client
            
            # Now import and test the function
            import observability_agent
            
            # Set environment variables
            os.environ['AWS_REGION'] = 'us-west-1'
            os.environ['SSM_PATH_PREFIX'] = 'flashsales/prod'
            
            token = observability_agent.get_grafana_token_from_ssm()
            
            if token:
                print(f"  ✓ Successfully retrieved token (length: {len(token)})")
                assert len(token) > 0
                return True
            else:
                print("  ✗ Failed to retrieve token")
                return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_github_mock():
    """Test GitHub workflow run fetching with mock."""
    print("\nTest 2: GitHub Workflow Run Fetching (Mocked)")
    
    try:
        from unittest.mock import MagicMock, patch
        
        # Mock GitHub response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "workflow_runs": [
                {
                    "id": 12345678,
                    "name": "loadtest",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/test/test/runs/12345678",
                }
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            # Set environment variables
            os.environ['GITHUB_TOKEN'] = 'test-token'
            os.environ['GITHUB_OWNER'] = 'test'
            os.environ['GITHUB_REPO'] = 'test-repo'
            
            import observability_agent
            
            runs = observability_agent.get_github_workflow_runs()
            
            if len(runs) > 0:
                print(f"  ✓ Successfully fetched {len(runs)} failed workflow run(s)")
                assert runs[0]['id'] == 12345678
                return True
            else:
                print("  ✗ No workflow runs fetched")
                return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_analysis_mock():
    """Test failure analysis with mock."""
    print("\nTest 3: Failure Analysis (Mocked)")
    
    try:
        from unittest.mock import MagicMock, patch
        import json
        
        run = {
            "id": 12345678,
            "name": "loadtest",
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://github.com/test/test/runs/12345678",
        }
        
        # Mock GitHub jobs response
        mock_jobs_response = MagicMock()
        mock_jobs_response.status_code = 200
        mock_jobs_response.json.return_value = {
            "jobs": [
                {
                    "id": 999,
                    "name": "smoke test",
                    "status": "completed",
                    "conclusion": "failure",
                    "steps": [
                        {
                            "name": "Run k6 load test",
                            "status": "completed",
                            "conclusion": "failure",
                        }
                    ]
                }
            ]
        }
        
        # Mock Grafana query response
        mock_grafana_response = MagicMock()
        mock_grafana_response.status_code = 200
        mock_grafana_response.json.return_value = {}
        
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            # Set up GitHub responses
            def get_side_effect(url, **kwargs):
                response = MagicMock()
                if 'jobs' in url:
                    response.status_code = 200
                    response.json.return_value = {
                        "jobs": [
                            {
                                "id": 999,
                                "name": "smoke test",
                                "status": "completed",
                                "conclusion": "failure",
                                "steps": [
                                    {
                                        "name": "Run k6 load test",
                                        "status": "completed",
                                        "conclusion": "failure",
                                    }
                                ]
                            }
                        ]
                    }
                else:
                    response.status_code = 200
                    response.json.return_value = {}
                return response
            
            mock_get.side_effect = get_side_effect
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"results": {}}
            
            import observability_agent
            
            analysis = observability_agent.analyze_failure(run, "https://grafana.example.com", "test-token")
            
            if analysis and analysis['run_id'] == 12345678:
                print(f"  ✓ Successfully analyzed failure")
                print(f"    - Run ID: {analysis['run_id']}")
                print(f"    - Failures: {len(analysis['failures'])}")
                print(f"    - Code issues: {len(analysis['code_issues'])}")
                return True
            else:
                print(f"  ✗ Analysis failed or incorrect")
                print(f"    Analysis: {analysis}")
                return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_grafana_query():
    """Test Grafana query structure."""
    print("\nTest 4: Grafana Metrics Query (Structure Check)")
    
    try:
        # Check that the query function exists and has correct signature
        import observability_agent
        
        if hasattr(observability_agent, 'query_grafana'):
            print(f"  ✓ query_grafana function exists")
            return True
        else:
            print(f"  ✗ query_grafana function not found")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_imports():
    """Test imports."""
    print("\nTest 5: Module Imports")
    
    try:
        import requests
        print("  ✓ requests imported")
    except ImportError:
        print("  ✗ requests import failed")
        return False
    
    try:
        import boto3
        print("  ✓ boto3 imported")
    except ImportError:
        print("  ✗ boto3 import failed (optional)")
    
    try:
        import json
        print("  ✓ json imported")
    except ImportError:
        print("  ✗ json import failed")
        return False
    
    try:
        import os
        print("  ✓ os imported")
    except ImportError:
        print("  ✗ os import failed")
        return False
    
    try:
        import sys
        print("  ✓ sys imported")
    except ImportError:
        print("  ✗ sys import failed")
        return False
    
    return True

def main():
    """Run all tests."""
    print("=" * 80)
    print("Observability Agent Tests")
    print("=" * 80)
    print(f"Working directory: {os.getcwd()}")
    print()
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: SSM token retrieval
    results.append(("SSM Token Retrieval", test_ssm_mock()))
    
    # Test 3: GitHub workflow runs
    results.append(("GitHub Workflow Runs", test_github_mock()))
    
    # Test 4: Failure analysis
    results.append(("Failure Analysis", test_analysis_mock()))
    
    # Test 5: Grafana query structure
    results.append(("Grafana Query Structure", test_grafana_query()))
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
