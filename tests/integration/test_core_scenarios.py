"""
Integration tests for core cooking scenarios.

Tests the full request/response cycle through the Flask application
for happy path scenarios.

Reference: docs/09-integration-test-specification.md
Reference: PHASE-2-PLAN.md
Reference: HANDOFF-INTEGRATION-TESTS.md
"""

import responses


@responses.activate
def test_int_01_happy_path_start_cook(
    client, auth_headers, valid_cook_requests, mock_anova_api_success
):
    """
    INT-01: Happy Path - Start Cook

    Scenario: User starts a valid chicken cook at 65°C for 90 minutes

    Steps:
    1. Verify device is idle
    2. Start cook with valid parameters
    3. Verify response indicates success
    4. Verify device state transitions to "preheating"
    5. Check status endpoint reflects active cook

    Validates: FR-01, FR-02, QR-01
    Reference: Spec Section 3.1, PHASE-2-PLAN.md lines 104-200
    """
    # Setup: mock_anova_api_success provides all necessary mocks
    # This fixture mocks Firebase auth and Anova API responses

    # ACT 1: Start cook with valid chicken parameters
    start_response = client.post(
        "/start-cook", headers=auth_headers, json=valid_cook_requests["chicken"]
    )

    # ASSERT 1: Start cook succeeded
    assert start_response.status_code == 200, (
        f"Expected 200, got {start_response.status_code}: {start_response.get_json()}"
    )

    start_data = start_response.get_json()

    # Validate response schema (all required fields present)
    required_fields = [
        "success",
        "message",
        "cook_id",
        "device_state",
        "target_temp_celsius",
        "time_minutes",
        "estimated_completion",
    ]
    for field in required_fields:
        assert field in start_data, f"Response missing required field: {field}"

    # Validate response values match request
    assert start_data["success"] is True
    assert start_data["target_temp_celsius"] == 65.0
    assert start_data["time_minutes"] == 90
    assert start_data["device_state"] == "preheating"

    # Validate field types and formats
    assert isinstance(start_data["cook_id"], str)
    assert len(start_data["cook_id"]) == 36  # UUID format
    assert "T" in start_data["estimated_completion"]  # ISO 8601
    assert start_data["estimated_completion"].endswith("Z")  # UTC

    # ACT 2: Check status after starting cook
    status_response = client.get("/status", headers=auth_headers)

    # ASSERT 2: Status shows device running
    assert status_response.status_code == 200
    status_data = status_response.get_json()

    # Device should be in preheating or cooking state
    assert status_data["state"] in ["preheating", "cooking"]
    assert status_data["is_running"] is True
    assert status_data["target_temp_celsius"] == 65.0
