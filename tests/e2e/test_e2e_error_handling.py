"""
E2E tests for error handling.

Tests that errors are properly handled and returned through the
complete Flask server → WebSocket client → simulator stack.

Test Coverage:
- Authentication errors (401)
- Device state errors (409 - busy, no active cook)
- Invalid request format errors

Reference: Plan Phase 2 - E2E Test Files
"""

import pytest


@pytest.mark.asyncio
class TestAuthenticationErrors:
    """E2E tests for authentication error handling."""

    async def test_missing_auth_header_returns_401(
        self,
        e2e_client,
        e2e_simulator,
    ):
        """Request without Authorization header returns 401."""
        response = e2e_client.post(
            "/start-cook",
            json={"temperature_celsius": 65.0, "time_minutes": 60},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"
        assert "Authorization" in data["message"]

    async def test_invalid_api_key_returns_401(
        self,
        e2e_client,
        e2e_invalid_auth_headers,
        e2e_simulator,
    ):
        """Request with invalid API key returns 401."""
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_invalid_auth_headers,
            json={"temperature_celsius": 65.0, "time_minutes": 60},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"

    async def test_malformed_auth_header_returns_401(
        self,
        e2e_client,
        e2e_simulator,
    ):
        """Request with malformed Authorization header returns 401."""
        response = e2e_client.post(
            "/start-cook",
            headers={"Authorization": "InvalidFormat", "Content-Type": "application/json"},
            json={"temperature_celsius": 65.0, "time_minutes": 60},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"
        assert "Bearer" in data["message"]

    async def test_status_endpoint_requires_auth(
        self,
        e2e_client,
        e2e_simulator,
    ):
        """GET /status requires authentication."""
        response = e2e_client.get("/status")

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"

    async def test_stop_endpoint_requires_auth(
        self,
        e2e_client,
        e2e_simulator,
    ):
        """POST /stop-cook requires authentication."""
        response = e2e_client.post("/stop-cook")

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
class TestDeviceStateErrors:
    """E2E tests for device state error handling."""

    async def test_device_busy_returns_409(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """Starting cook while device is busy returns 409."""
        simulator, control = e2e_simulator
        simulator.reset()

        # Start first cook
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["quick_chicken"],
        )
        assert response.status_code == 200

        # Try to start second cook
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["quick_steak"],
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "DEVICE_BUSY"

        # Cleanup
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)

    async def test_no_active_cook_returns_409(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Stopping cook when none active returns 409."""
        simulator, control = e2e_simulator
        simulator.reset()

        # Try to stop when no cook is active
        response = e2e_client.post("/stop-cook", headers=e2e_auth_headers)

        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "NO_ACTIVE_COOK"


@pytest.mark.asyncio
class TestRequestFormatErrors:
    """E2E tests for request format error handling."""

    async def test_invalid_json_returns_400(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request with invalid JSON returns 400."""
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            data="not valid json",
            content_type="application/json",
        )

        # Flask returns 400 or 415 for invalid JSON
        assert response.status_code in [400, 415]

    async def test_empty_body_returns_400(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request with empty body returns 400."""
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={},
        )

        assert response.status_code == 400
        data = response.get_json()
        # Should be missing temperature or time error
        assert data["error"] in ["MISSING_TEMPERATURE", "MISSING_TIME"]

    async def test_invalid_temperature_type_returns_400(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request with non-numeric temperature returns 400."""
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": "hot",
                "time_minutes": 60,
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "INVALID_TEMPERATURE"

    async def test_invalid_time_type_returns_400(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request with non-numeric time returns 400."""
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json={
                "temperature_celsius": 65.0,
                "time_minutes": "one hour",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "INVALID_TIME"


@pytest.mark.asyncio
class TestEndpointNotFound:
    """E2E tests for endpoint not found handling."""

    async def test_unknown_endpoint_returns_404(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request to unknown endpoint returns 404."""
        response = e2e_client.get("/unknown-endpoint", headers=e2e_auth_headers)
        assert response.status_code == 404

    async def test_wrong_method_returns_405(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """Request with wrong HTTP method returns 405."""
        # /start-cook only accepts POST
        response = e2e_client.get("/start-cook", headers=e2e_auth_headers)
        assert response.status_code == 405
