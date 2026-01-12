"""
Integration tests for error path scenarios.

Tests error handling through the Flask application for device offline,
busy states, and authentication failures.

Reference: docs/09-integration-test-specification.md Section 3.2
"""

import pytest
import responses


@responses.activate
def test_int_03_device_offline_during_start(
    client,
    auth_headers,
    valid_cook_requests
):
    """
    INT-03: Device offline returns 503 error.

    Validates: FR-06
    Reference: Spec lines 518-567
    """
    # ARRANGE: Mock Firebase auth (succeeds)
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # ARRANGE: Mock device status check (offline)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={"error": "Device not found or offline"},
        status=404  # Anova returns 404 when device offline
    )

    # ACT: Try to start cook
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    # ASSERT: Returns 503 Service Unavailable
    assert response.status_code == 503, \
        f"Expected 503, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()

    # Validate error response structure
    assert error_data["error"] == "DEVICE_OFFLINE", \
        f"Expected DEVICE_OFFLINE, got {error_data.get('error')}"
    assert "offline" in error_data["message"].lower(), \
        f"Error message should mention 'offline': {error_data['message']}"

    # Should include retry guidance
    assert "retry_after" in error_data, \
        "Response should include retry_after field"
    assert error_data["retry_after"] > 0, \
        "retry_after should be a positive number of seconds"


@responses.activate
def test_int_04_device_busy_already_cooking(
    client,
    auth_headers,
    valid_cook_requests
):
    """
    INT-04: Starting cook when already cooking returns 409.

    Validates: Concurrent cook prevention
    Reference: Spec lines 568-617
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # ARRANGE: Mock device status (already cooking)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",  # Already cooking!
            "currentTemperature": 64.5,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 3600,  # 60 minutes remaining
            "cookTimeElapsed": 1800  # 30 minutes elapsed
        },
        status=200
    )

    # ACT: Try to start another cook
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["steak"]  # Different cook
    )

    # ASSERT: Returns 409 Conflict
    assert response.status_code == 409, \
        f"Expected 409, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()

    # Validate error response
    assert error_data["error"] == "DEVICE_BUSY", \
        f"Expected DEVICE_BUSY, got {error_data.get('error')}"
    assert "already cooking" in error_data["message"].lower(), \
        f"Error message should mention 'already cooking': {error_data['message']}"
    assert "stop" in error_data["message"].lower(), \
        f"Error message should mention stopping current cook: {error_data['message']}"


def test_int_05_authentication_failure(client, valid_cook_requests):
    """
    INT-05: Missing or invalid auth returns 401.

    Validates: QR-33 (authentication required)
    Reference: Spec lines 620-680

    Note: No @responses.activate needed - auth fails before any API calls
    """
    # ACT 1: No Authorization header
    response = client.post(
        '/start-cook',
        json=valid_cook_requests["chicken"]
        # No headers at all
    )

    # ASSERT 1: Returns 401
    assert response.status_code == 401, \
        f"Expected 401, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()
    assert error_data["error"] == "UNAUTHORIZED", \
        f"Expected UNAUTHORIZED, got {error_data.get('error')}"
    assert "Authorization" in error_data["message"], \
        f"Error message should mention Authorization: {error_data['message']}"

    # ACT 2: Invalid Authorization format (not "Bearer <token>")
    response = client.post(
        '/start-cook',
        headers={"Authorization": "InvalidFormat token123"},
        json=valid_cook_requests["chicken"]
    )

    # ASSERT 2: Returns 401 for invalid format
    assert response.status_code == 401, \
        f"Expected 401, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()
    assert error_data["error"] == "UNAUTHORIZED", \
        f"Expected UNAUTHORIZED, got {error_data.get('error')}"
    assert "Bearer" in error_data["message"], \
        f"Error message should hint at Bearer format: {error_data['message']}"

    # ACT 3: Wrong API key
    response = client.post(
        '/start-cook',
        headers={"Authorization": "Bearer wrong-key-12345"},
        json=valid_cook_requests["chicken"]
    )

    # ASSERT 3: Returns 401 for wrong key
    assert response.status_code == 401, \
        f"Expected 401, got {response.status_code}: {response.get_json()}"

    error_data = response.get_json()
    assert error_data["error"] == "UNAUTHORIZED", \
        f"Expected UNAUTHORIZED, got {error_data.get('error')}"
    assert "Invalid API key" in error_data["message"], \
        f"Error message should mention invalid API key: {error_data['message']}"

    # ASSERT 4: Error messages don't leak info
    # Should NOT include the actual API key in error message
    assert "test-api-key-12345" not in error_data["message"], \
        "Error message should not leak the valid API key"
    assert "wrong-key-12345" not in error_data["message"], \
        "Error message should not leak the provided wrong key"
