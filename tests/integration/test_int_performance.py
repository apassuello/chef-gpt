"""
Integration tests for performance expectations.

These are NOT load tests - they verify basic response time characteristics
with mocked dependencies. Real API latency will be higher.

Thresholds include buffer (25-50%) to prevent flakiness in CI/CD.

Reference: docs/09-integration-test-specification.md Section 7
"""

import time

import responses


def test_int_perf_01_health_check_fast(client):
    """
    INT-PERF-01: Health check responds in < 100ms.

    Health endpoint should be very fast (no auth, no logic, no external calls).
    Threshold: 150ms (spec: 100ms + 50ms buffer for CI/CD variance)

    Reference: Spec lines 1358-1366
    """
    # ACT: Time the health check
    start = time.time()
    response = client.get("/health")
    duration = time.time() - start

    # ASSERT: Fast response
    assert response.status_code == 200
    assert duration < 0.15, f"Health check took {duration:.3f}s (threshold: 0.15s)"


@responses.activate
def test_int_perf_02_start_cook_reasonable(
    client, auth_headers, valid_cook_requests, mock_anova_api_success
):
    """
    INT-PERF-02: Start cook responds in < 2 seconds.

    With mocked Anova API, start-cook should complete reasonably fast.
    Threshold: 2.5s (spec: 2.0s + 500ms buffer for CI/CD variance)

    Reference: Spec lines 1368-1380
    """
    # ARRANGE: Use valid chicken cook request
    cook_request = valid_cook_requests["chicken"]

    # ACT: Time the start cook operation
    start = time.time()
    response = client.post("/start-cook", json=cook_request, headers=auth_headers)
    duration = time.time() - start

    # ASSERT: Reasonable response time
    assert response.status_code == 200, (
        f"Request failed with {response.status_code}: {response.get_json()}"
    )
    assert duration < 2.5, f"Start cook took {duration:.3f}s (threshold: 2.5s)"


@responses.activate
def test_int_perf_03_status_fast(client, auth_headers, mock_anova_api_success):
    """
    INT-PERF-03: Status query responds in < 500ms.

    Status endpoint should be fast (simple GET operation).
    Threshold: 750ms (spec: 500ms + 250ms buffer for CI/CD variance)

    Reference: Spec lines 1382-1390
    """
    # ACT: Time the status query
    start = time.time()
    response = client.get("/status", headers=auth_headers)
    duration = time.time() - start

    # ASSERT: Fast response
    assert response.status_code == 200, (
        f"Request failed with {response.status_code}: {response.get_json()}"
    )
    assert duration < 0.75, f"Status query took {duration:.3f}s (threshold: 0.75s)"
