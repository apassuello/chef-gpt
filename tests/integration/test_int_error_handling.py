"""
Integration tests for error handling.

Verifies that exceptions from validators and anova_client are properly
mapped to HTTP status codes via middleware error handlers.

Reference: docs/09-integration-test-specification.md Section 6
"""

import pytest
import responses


@pytest.mark.parametrize(
    "request_data,expected_error,expected_status",
    [
        # Temperature validation
        ({"temperature_celsius": 35, "time_minutes": 60}, "TEMPERATURE_TOO_LOW", 400),
        ({"temperature_celsius": 105, "time_minutes": 60}, "TEMPERATURE_TOO_HIGH", 400),
        # Time validation
        ({"temperature_celsius": 65, "time_minutes": 0}, "TIME_TOO_SHORT", 400),
        ({"temperature_celsius": 65, "time_minutes": 6000}, "TIME_TOO_LONG", 400),
        # Missing field validation
        ({"time_minutes": 60}, "MISSING_TEMPERATURE", 400),
        ({"temperature_celsius": 65}, "MISSING_TIME", 400),
    ],
)
def test_int_err_01_validation_error_to_400(
    client, auth_headers, request_data, expected_error, expected_status
):
    """
    INT-ERR-01: ValidationError from validators maps to 400.

    Tests all validation error scenarios to ensure consistent 400 response
    with appropriate error codes.

    Reference: Spec lines 1254-1280
    """
    # ACT: Send invalid request
    response = client.post("/start-cook", json=request_data, headers=auth_headers)
    data = response.get_json()

    # ASSERT: Verify 400 status and error code
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code} for {expected_error}"
    )
    assert data["error"] == expected_error, (
        f"Expected error code {expected_error}, got {data.get('error')}"
    )
    assert "message" in data, "Response should contain error message"
    assert len(data["message"]) > 0, "Error message should not be empty"


@responses.activate
def test_int_err_02_device_offline_error_to_503(client, auth_headers, mock_anova_api_offline):
    """
    INT-ERR-02: DeviceOfflineError maps to 503 Service Unavailable.

    Verifies that when device is offline/unreachable, API returns 503
    with appropriate retry guidance.

    Reference: Spec lines 1284-1302
    """
    # ACT: Try to start cook with offline device
    response = client.post(
        "/start-cook", json={"temperature_celsius": 65.0, "time_minutes": 90}, headers=auth_headers
    )
    data = response.get_json()

    # ASSERT: Verify 503 status
    assert response.status_code == 503, (
        f"Expected 503 for offline device, got {response.status_code}"
    )
    assert data["error"] == "DEVICE_OFFLINE", (
        f"Expected DEVICE_OFFLINE error code, got {data.get('error')}"
    )
    assert "message" in data, "Response should contain error message"

    # Message should mention offline, retry, or connectivity
    message_lower = data["message"].lower()
    assert (
        "offline" in message_lower or "connection" in message_lower or "available" in message_lower
    ), f"Message should mention connectivity issue, got: {data['message']}"


@responses.activate
def test_int_err_03_device_busy_error_to_409(client, auth_headers, mock_anova_api_busy):
    """
    INT-ERR-03: DeviceBusyError maps to 409 Conflict.

    Verifies that when device is already cooking, API returns 409
    indicating resource conflict.

    Reference: Spec lines 1306-1321
    """
    # ACT: Try to start cook when device already cooking
    response = client.post(
        "/start-cook", json={"temperature_celsius": 65.0, "time_minutes": 90}, headers=auth_headers
    )
    data = response.get_json()

    # ASSERT: Verify 409 status
    assert response.status_code == 409, f"Expected 409 for busy device, got {response.status_code}"
    assert data["error"] == "DEVICE_BUSY", (
        f"Expected DEVICE_BUSY error code, got {data.get('error')}"
    )
    assert "message" in data, "Response should contain error message"


@pytest.mark.parametrize(
    "headers,description",
    [
        ({}, "missing Authorization header"),
        ({"Authorization": "Bearer wrong-api-key-12345"}, "invalid API key"),
    ],
)
def test_int_err_04_authentication_error_to_401(client, headers, description):
    """
    INT-ERR-04: Missing/invalid authentication returns 401.

    Tests both missing and invalid auth scenarios to ensure consistent
    401 Unauthorized response.

    Reference: Spec lines 1325-1345
    """
    # ACT: Send request with invalid/missing auth
    response = client.post(
        "/start-cook", json={"temperature_celsius": 65.0, "time_minutes": 90}, headers=headers
    )
    data = response.get_json()

    # ASSERT: Verify 401 status
    assert response.status_code == 401, (
        f"Expected 401 for {description}, got {response.status_code}"
    )
    assert data["error"] == "UNAUTHORIZED", (
        f"Expected UNAUTHORIZED error code for {description}, got {data.get('error')}"
    )
    assert "message" in data, f"Response should contain error message for {description}"
