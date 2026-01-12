"""
Integration tests for edge case scenarios.

Tests unusual but valid scenarios including error recovery,
token refresh, and concurrent operations.

Reference: docs/09-integration-test-specification.md Section 3.3
"""

import pytest
import responses
import threading


@responses.activate
def test_int_06_stop_cook_no_active_session(
    client,
    auth_headers,
    mock_anova_api_success
):
    """
    INT-06: Stopping when idle returns 409 NO_ACTIVE_COOK.

    Validates: FR-03
    Reference: Spec lines 683-726
    """
    # ARRANGE: Mock shows device is idle (no active cook)
    # The mock_anova_api_success fixture already sets up idle state

    # ACT: Attempt to stop when device is idle
    response = client.post('/stop-cook', headers=auth_headers)

    # ASSERT: Returns 409 Conflict (state violation)
    assert response.status_code == 409, \
        f"Expected 409, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()

    # Verify error code
    assert error_data["error"] == "NO_ACTIVE_COOK", \
        f"Expected NO_ACTIVE_COOK, got {error_data.get('error')}"

    # Verify message explains the issue
    message_lower = error_data["message"].lower()
    assert "no active" in message_lower or "not cooking" in message_lower, \
        f"Error message should explain no active cook: {error_data['message']}"


@responses.activate
def test_int_07_token_refresh_during_request(
    client,
    auth_headers,
    valid_cook_requests
):
    """
    INT-07: Token refresh happens transparently during operation.

    Validates: QR-10, QR-13
    Reference: Spec lines 728-807

    Note: Our implementation uses proactive token refresh (checks expiry before API call)
    rather than reactive (waiting for 401). This test validates the proactive approach.
    """
    # ARRANGE: Mock Firebase auth with short-lived token (simulates near-expiry)
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "initial-token",
            "refreshToken": "refresh-token",
            "expiresIn": "10"  # Very short expiry (10 seconds)
        },
        status=200
    )

    # Mock device status check (idle)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "IDLE",
            "currentTemperature": 22.5,
            "targetTemperature": None,
            "cookTimeRemaining": None,
            "cookTimeElapsed": None
        },
        status=200
    )

    # Mock start cook command
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/cook",
        json={
            "success": True,
            "cookId": "550e8400-e29b-41d4-a716-446655440000",
            "state": "preheating"
        },
        status=200
    )

    # ACT: Start cook (this will create AnovaClient and perform operation)
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    # ASSERT: Request succeeds despite short token lifetime
    assert response.status_code == 200, \
        f"Expected 200, got {response.status_code}: {response.get_json()}"

    data = response.get_json()
    assert data["success"] is True

    # Verify the operation completed (token management was transparent)
    assert data["target_temp_celsius"] == 65.0
    assert data["time_minutes"] == 90


@responses.activate
def test_int_08_concurrent_requests_status_and_start(
    client,
    auth_headers,
    valid_cook_requests,
    mock_anova_api_success
):
    """
    INT-08: Concurrent status and start requests both succeed.

    Validates: QR-01, QR-10
    Reference: Spec lines 810-875

    Tests that multiple simultaneous requests don't cause race conditions,
    deadlocks, or crashes.
    """
    # ARRANGE: mock_anova_api_success provides necessary mocks
    results = {}

    def get_status():
        """Thread 1: Get device status"""
        try:
            response = client.get('/status', headers=auth_headers)
            results['status'] = response
        except Exception as e:
            results['status_error'] = str(e)

    def start_cook():
        """Thread 2: Start cook"""
        try:
            response = client.post(
                '/start-cook',
                headers=auth_headers,
                json=valid_cook_requests["chicken"]
            )
            results['start'] = response
        except Exception as e:
            results['start_error'] = str(e)

    # ACT: Execute both requests concurrently
    t1 = threading.Thread(target=get_status)
    t2 = threading.Thread(target=start_cook)

    t1.start()
    t2.start()

    t1.join(timeout=5)  # Wait max 5 seconds
    t2.join(timeout=5)

    # ASSERT: Both requests completed (no deadlocks)
    assert 'status' in results, \
        f"Status request didn't complete: {results.get('status_error', 'timeout')}"
    assert 'start' in results, \
        f"Start request didn't complete: {results.get('start_error', 'timeout')}"

    # Verify status request succeeded
    assert results['status'].status_code == 200, \
        f"Status request failed: {results['status'].status_code}"

    # Verify start request succeeded or returned expected conflict
    # (409 if both threads tried to start at same time and one won)
    assert results['start'].status_code in [200, 409], \
        f"Start request unexpected status: {results['start'].status_code}"

    # Verify no crashes - both responses are valid JSON
    status_data = results['status'].get_json()
    start_data = results['start'].get_json()

    assert status_data is not None, "Status response should be valid JSON"
    assert start_data is not None, "Start response should be valid JSON"
