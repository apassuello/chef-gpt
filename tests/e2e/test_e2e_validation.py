"""
E2E tests for input validation.

Tests that validation rules work correctly through the complete
Flask server → WebSocket client → simulator stack.

These tests verify that:
- Temperature limits are enforced
- Food safety rules are applied
- Time limits are validated
- Missing fields are detected

Reference: Plan Phase 2 - E2E Test Files
"""

import pytest


@pytest.mark.asyncio
class TestTemperatureValidation:
    """E2E tests for temperature validation."""

    async def test_temperature_below_minimum_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Temperature below 40°C should return TEMPERATURE_TOO_LOW."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["temp_too_low"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]
        assert "danger zone" in data["message"].lower()

    async def test_temperature_above_maximum_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Temperature above 100°C should return TEMPERATURE_TOO_HIGH."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["temp_too_high"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]

    async def test_exact_minimum_temperature_accepted(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """Temperature exactly at 40°C should be accepted."""
        simulator, control = e2e_simulator
        simulator.reset()

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["minimum_temp"],
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "started"
        assert data["target_temp_celsius"] == 40.0

        # Cleanup
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)

    async def test_exact_maximum_temperature_accepted(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """Temperature exactly at 100°C should be accepted."""
        simulator, control = e2e_simulator
        simulator.reset()

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["maximum_temp"],
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "started"
        assert data["target_temp_celsius"] == 100.0

        # Cleanup
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)


@pytest.mark.asyncio
class TestFoodSafetyValidation:
    """E2E tests for food safety validation."""

    async def test_poultry_below_safe_temp_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Poultry below 57°C should return POULTRY_TEMP_UNSAFE."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["unsafe_poultry"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
                "food_type": request["food_type"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]
        assert "poultry" in data["message"].lower()

    async def test_ground_meat_below_safe_temp_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Ground meat below 60°C should return GROUND_MEAT_TEMP_UNSAFE."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["unsafe_ground_meat"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
                "food_type": request["food_type"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]

    async def test_poultry_at_safe_temp_accepted(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Poultry at exactly 57°C should be accepted (with extended time)."""
        simulator, control = e2e_simulator
        simulator.reset()

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": 57.0,
                "time_minutes": 180,  # Extended time required
                "food_type": "chicken",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "started"

        # Cleanup
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)


@pytest.mark.asyncio
class TestTimeValidation:
    """E2E tests for time validation."""

    async def test_zero_time_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Zero cook time should return TIME_TOO_SHORT."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["time_zero"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]

    async def test_excessive_time_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Time above 5999 minutes should return TIME_TOO_LONG."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["time_too_long"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": request["temperature_celsius"],
                "time_minutes": request["time_minutes"],
            },
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]


@pytest.mark.asyncio
class TestMissingFieldValidation:
    """E2E tests for missing field validation."""

    async def test_missing_temperature_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Missing temperature should return MISSING_TEMPERATURE."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["missing_temperature"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={"time_minutes": request["time_minutes"]},
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]

    async def test_missing_time_rejected(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        invalid_e2e_cook_requests,
    ):
        """Missing time should return MISSING_TIME."""
        simulator, control = e2e_simulator
        request = invalid_e2e_cook_requests["missing_time"]

        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={"temperature_celsius": request["temperature_celsius"]},
        )

        assert response.status_code == request["expected_status"]
        data = response.get_json()
        assert data["error"] == request["expected_error"]
