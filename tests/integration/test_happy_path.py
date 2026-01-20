"""
Integration tests for happy path scenarios.

Tests validation logic and successful workflows through the Flask application.

Reference: docs/09-integration-test-specification.md Section 3.1
"""

import responses


@responses.activate
def test_int_02_validation_rejection_flow(client, auth_headers, mock_anova_api_success):
    """
    INT-02: Validation rejects unsafe request before calling Anova API.

    Validates: FR-04, FR-05, FR-07, FR-08
    Reference: Spec lines 462-513

    This test proves validation is our first line of defense.
    If validation passes unsafe requests, code is unsafe.
    """
    # ARRANGE: Mock Anova API (should NOT be called)
    # We'll verify at the end that no API calls were made

    # ACT 1: Try to cook chicken at UNSAFE temperature (56°C, below 57°C minimum)
    unsafe_chicken_request = {
        "temperature_celsius": 56.0,  # Below poultry minimum (57°C)
        "time_minutes": 90,
        "food_type": "chicken breast",
    }

    response = client.post("/start-cook", headers=auth_headers, json=unsafe_chicken_request)

    # ASSERT 1: Request rejected with 400 (validation error)
    assert response.status_code == 400, (
        f"Expected 400, got {response.status_code}: {response.get_json()}"
    )

    error_data = response.get_json()
    assert error_data["error"] == "POULTRY_TEMP_UNSAFE", (
        f"Expected POULTRY_TEMP_UNSAFE, got {error_data.get('error')}"
    )
    assert "57" in error_data["message"], (
        f"Error message should mention 57°C minimum: {error_data['message']}"
    )

    # ASSERT 2: No Anova API calls were made
    # responses library tracks all matched calls
    assert len(responses.calls) == 0, "Validator should reject before calling Anova API"

    # ACT 2: Try cook with time too short (0 minutes)
    invalid_time_request = {
        "temperature_celsius": 65.0,
        "time_minutes": 0,  # Below minimum (1 minute)
        "food_type": "chicken",
    }

    # Reset mock call tracker
    responses.reset()

    response = client.post("/start-cook", headers=auth_headers, json=invalid_time_request)

    # ASSERT 3: Time validation also blocks before API call
    assert response.status_code == 400, (
        f"Expected 400, got {response.status_code}: {response.get_json()}"
    )

    error_data = response.get_json()
    assert error_data["error"] == "TIME_TOO_SHORT", (
        f"Expected TIME_TOO_SHORT, got {error_data.get('error')}"
    )
    assert len(responses.calls) == 0, (
        "Validator should reject time validation before calling Anova API"
    )

    # ACT 3: Try with temperature below absolute minimum (39°C)
    too_cold_request = {
        "temperature_celsius": 39.0,  # Below 40°C absolute minimum
        "time_minutes": 90,
    }

    responses.reset()

    response = client.post("/start-cook", headers=auth_headers, json=too_cold_request)

    # ASSERT 4: Absolute temp minimum also enforced
    assert response.status_code == 400, (
        f"Expected 400, got {response.status_code}: {response.get_json()}"
    )

    error_data = response.get_json()
    assert error_data["error"] == "TEMPERATURE_TOO_LOW", (
        f"Expected TEMPERATURE_TOO_LOW, got {error_data.get('error')}"
    )
    assert "danger zone" in error_data["message"].lower(), (
        f"Error message should mention danger zone: {error_data['message']}"
    )
    assert len(responses.calls) == 0, (
        "Validator should reject absolute minimum before calling Anova API"
    )
