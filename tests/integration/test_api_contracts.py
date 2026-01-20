"""
Integration tests for API contract verification.

Validates that response schemas match the API specification for all endpoints.

Reference: docs/09-integration-test-specification.md Section 5
"""

from datetime import datetime

import responses


@responses.activate
def test_int_api_01_start_cook_response_schema(
    client, auth_headers, valid_cook_requests, mock_anova_api_success
):
    """
    INT-API-01: Start cook response matches schema.

    Reference: Spec lines 1105-1145
    """
    # ACT: Start cook
    response = client.post("/start-cook", headers=auth_headers, json=valid_cook_requests["chicken"])

    assert response.status_code == 200
    data = response.get_json()

    # ASSERT: Required fields present and correct types
    assert "success" in data
    assert isinstance(data["success"], bool)
    assert data["success"] is True, "Success should be true for valid request"

    assert "cook_id" in data
    assert isinstance(data["cook_id"], str)
    assert len(data["cook_id"]) > 0, "cook_id should not be empty"

    assert "device_state" in data
    assert isinstance(data["device_state"], str)
    assert data["device_state"] in ["preheating", "cooking"], (
        f"device_state should be preheating or cooking, got {data['device_state']}"
    )

    assert "target_temp_celsius" in data
    assert isinstance(data["target_temp_celsius"], (int, float))
    assert data["target_temp_celsius"] == 65.0, "Should match requested temp"

    assert "time_minutes" in data
    assert isinstance(data["time_minutes"], int)
    assert data["time_minutes"] == 90, "Should match requested time"

    # ASSERT: Optional fields (if present, validate types)
    if "message" in data:
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0, "Message should not be empty"

    if "estimated_completion" in data:
        assert isinstance(data["estimated_completion"], str)
        # Should be ISO 8601 format with Z suffix
        assert "T" in data["estimated_completion"], "Should be ISO 8601 format"
        assert data["estimated_completion"].endswith("Z"), "Should have Z suffix (UTC)"
        # Verify it's parseable as datetime
        datetime.fromisoformat(data["estimated_completion"].replace("Z", "+00:00"))


@responses.activate
def test_int_api_02_status_response_schema(client, auth_headers, mock_anova_api_success):
    """
    INT-API-02: Status response matches schema.

    Reference: Spec lines 1149-1224
    """
    # ACT: Get status
    response = client.get("/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # ASSERT: Required fields present and correct types
    assert "device_online" in data
    assert isinstance(data["device_online"], bool)

    assert "state" in data
    assert isinstance(data["state"], str)
    assert data["state"] in ["idle", "preheating", "cooking", "done"], (
        f"state should be valid state, got {data['state']}"
    )

    assert "current_temp_celsius" in data
    assert isinstance(data["current_temp_celsius"], (int, float))
    assert data["current_temp_celsius"] >= 0, "Temperature should be non-negative"

    # ASSERT: Optional/nullable fields (present but may be None)
    assert "target_temp_celsius" in data
    if data["target_temp_celsius"] is not None:
        assert isinstance(data["target_temp_celsius"], (int, float))
        assert data["target_temp_celsius"] >= 0

    assert "time_remaining_minutes" in data
    if data["time_remaining_minutes"] is not None:
        assert isinstance(data["time_remaining_minutes"], int)
        assert data["time_remaining_minutes"] >= 0

    assert "time_elapsed_minutes" in data
    if data["time_elapsed_minutes"] is not None:
        assert isinstance(data["time_elapsed_minutes"], int)
        assert data["time_elapsed_minutes"] >= 0

    assert "is_running" in data
    assert isinstance(data["is_running"], bool)

    # ASSERT: Logical consistency
    if data["is_running"]:
        # If running, should have target temp
        assert data["target_temp_celsius"] is not None, (
            "Running device should have target temperature"
        )


@responses.activate
def test_int_api_03_stop_cook_response_schema(
    client, auth_headers, valid_cook_requests, mock_anova_api_success
):
    """
    INT-API-03: Stop cook response matches schema.

    Expected schema:
    - success (bool)
    - device_state (string) = "idle"
    - final_temp_celsius (optional, number or null)
    - message (optional, string)

    Reference: Spec lines 1186-1218
    """
    # ARRANGE: Start a cook first
    start_response = client.post(
        "/start-cook", json=valid_cook_requests["chicken"], headers=auth_headers
    )
    assert start_response.status_code == 200

    # ACT: Stop the cook
    stop_response = client.post("/stop-cook", headers=auth_headers)
    data = stop_response.get_json()

    # ASSERT: Required fields present and correct types
    assert stop_response.status_code == 200

    assert "success" in data
    assert isinstance(data["success"], bool)

    assert "device_state" in data
    assert isinstance(data["device_state"], str)
    assert data["device_state"] == "idle", (
        f"Device should be idle after stopping, got {data['device_state']}"
    )

    # ASSERT: Optional fields (if present, validate types)
    if "final_temp_celsius" in data:
        # Can be number or null
        assert data["final_temp_celsius"] is None or isinstance(
            data["final_temp_celsius"], (int, float)
        ), f"final_temp_celsius should be number or null, got {type(data['final_temp_celsius'])}"
        if data["final_temp_celsius"] is not None:
            assert data["final_temp_celsius"] >= 0, "Temperature should be non-negative"

    if "message" in data:
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0, "Message should not be empty"


def test_int_api_04_error_response_schema(client, auth_headers):
    """
    INT-API-04: Error responses follow consistent schema.

    Expected schema:
    - error (string) - error code
    - message (string) - human-readable message

    Reference: Spec lines 1222-1246
    """
    # ARRANGE: Trigger validation error with temperature too low
    invalid_request = {"temperature_celsius": 35.0, "time_minutes": 60}

    # ACT: Send invalid request
    response = client.post("/start-cook", json=invalid_request, headers=auth_headers)
    data = response.get_json()

    # ASSERT: Required fields present and correct types
    assert response.status_code == 400, (
        f"Should return 400 for validation error, got {response.status_code}"
    )

    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0, "Error code should not be empty"
    assert data["error"] == "TEMPERATURE_TOO_LOW", (
        f"Expected TEMPERATURE_TOO_LOW, got {data['error']}"
    )

    assert "message" in data
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0, "Error message should not be empty"
    # Message should be human-readable (contains spaces, proper case)
    assert " " in data["message"], "Message should be human-readable with spaces"
