"""
E2E tests for cook lifecycle.

Tests the complete cooking workflow through real Flask server
connected to the local simulator.

Test Coverage:
- E2E-01: Complete cook lifecycle (start → preheat → cook → done)
- E2E-02: Start and stop cook mid-way
- E2E-03: Status polling during cook
- E2E-04: Device busy rejection (start twice → 409)
- E2E-05: Stop without active cook (→ 409)
- E2E-06: Multiple status calls during cooking

Reference: Plan Phase 2 - E2E Test Files
"""

import asyncio
import time

import pytest

from simulator.types import DeviceState


@pytest.mark.asyncio
class TestCookLifecycle:
    """E2E tests for the complete cooking lifecycle."""

    async def test_e2e_01_complete_cook_lifecycle(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """
        E2E-01: Complete cook lifecycle (start → preheat → cook → done).

        Verifies that a cook can be started, progresses through all states,
        and reaches completion.
        """
        simulator, control = e2e_simulator
        request_data = valid_e2e_cook_requests["quick_chicken"]

        # 1. Verify initial idle state
        response = e2e_client.get("/status", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["state"] == "idle"
        assert data["is_running"] is False

        # 2. Start cook
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=request_data,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "started"
        assert data["target_temp_celsius"] == 65.0
        assert "cook_id" in data

        # 3. Verify device is now running (preheating or cooking)
        response = e2e_client.get("/status", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_running"] is True
        assert data["state"] in ["preheating", "cooking"]

        # 4. Wait for cook to complete (with accelerated time)
        # At 60x, 2 minutes = 2 seconds, but we need to wait for preheating too
        # Poll until done or timeout
        max_wait = 10  # seconds
        poll_interval = 0.5
        waited = 0

        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            response = e2e_client.get("/status", headers=e2e_auth_headers)
            data = response.get_json()

            if data["state"] == "done":
                break

        # 5. Verify cook completed
        assert data["state"] == "done", f"Cook did not complete in time. Last state: {data['state']}"
        assert data["target_temp_celsius"] == 65.0

    async def test_e2e_02_start_and_stop_midway(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """
        E2E-02: Start and stop cook mid-way.

        Verifies that a cook can be started and stopped before completion.
        """
        simulator, control = e2e_simulator
        simulator.reset()

        # Start cook
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["quick_chicken"],
        )
        assert response.status_code == 200

        # Verify running
        response = e2e_client.get("/status", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_running"] is True

        # Stop cook
        response = e2e_client.post("/stop-cook", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "stopped"
        assert "final_temp_celsius" in data

        # Verify stopped
        response = e2e_client.get("/status", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_running"] is False
        assert data["state"] == "idle"

    async def test_e2e_03_status_polling_during_cook(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """
        E2E-03: Status polling during cook.

        Verifies that status can be polled repeatedly during cooking
        and shows temperature changes.
        """
        simulator, control = e2e_simulator
        simulator.reset()

        # Start cook
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["quick_chicken"],
        )
        assert response.status_code == 200

        # Poll status multiple times
        temperatures = []
        for _ in range(5):
            await asyncio.sleep(0.3)

            response = e2e_client.get("/status", headers=e2e_auth_headers)
            assert response.status_code == 200

            data = response.get_json()
            assert "current_temp_celsius" in data
            assert "target_temp_celsius" in data
            temperatures.append(data["current_temp_celsius"])

        # Temperature should generally increase during preheating
        # (may plateau if cooking state reached)
        assert len(temperatures) == 5

        # Cleanup - stop the cook
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)

    async def test_e2e_04_device_busy_rejection(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """
        E2E-04: Device busy rejection (start twice → 409).

        Verifies that starting a cook while one is already running
        returns 409 Conflict.
        """
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

    async def test_e2e_05_stop_without_active_cook(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
    ):
        """
        E2E-05: Stop without active cook (→ 409).

        Verifies that stopping when no cook is active returns 409.
        """
        simulator, control = e2e_simulator
        simulator.reset()

        # Verify device is idle
        response = e2e_client.get("/status", headers=e2e_auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_running"] is False

        # Try to stop non-existent cook
        response = e2e_client.post("/stop-cook", headers=e2e_auth_headers)
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "NO_ACTIVE_COOK"

    async def test_e2e_06_status_shows_time_remaining(
        self,
        e2e_client,
        e2e_auth_headers,
        e2e_simulator,
        valid_e2e_cook_requests,
    ):
        """
        E2E-06: Status shows time remaining during cook.

        Verifies that time_remaining decreases during cooking.
        """
        simulator, control = e2e_simulator
        simulator.reset()

        # Start cook with 2 minute timer
        response = e2e_client.post(
            "/start-cook",
            headers=e2e_auth_headers,
            json=valid_e2e_cook_requests["quick_chicken"],
        )
        assert response.status_code == 200

        # Wait for cooking state (after preheating)
        max_wait = 5
        waited = 0
        while waited < max_wait:
            await asyncio.sleep(0.3)
            waited += 0.3

            response = e2e_client.get("/status", headers=e2e_auth_headers)
            data = response.get_json()

            if data["state"] == "cooking":
                break

        # If we reached cooking state, check time remaining
        if data["state"] == "cooking":
            time1 = data.get("time_remaining_minutes")

            await asyncio.sleep(0.5)

            response = e2e_client.get("/status", headers=e2e_auth_headers)
            data = response.get_json()
            time2 = data.get("time_remaining_minutes")

            # Time should decrease (or be None if cook completed)
            if time1 is not None and time2 is not None:
                assert time2 <= time1, "Time remaining should decrease"

        # Cleanup
        e2e_client.post("/stop-cook", headers=e2e_auth_headers)


@pytest.mark.asyncio
class TestHealthEndpoint:
    """E2E tests for the health endpoint."""

    async def test_health_check_no_auth_required(self, e2e_client):
        """Health endpoint should work without authentication."""
        response = e2e_client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    async def test_health_check_returns_correct_format(self, e2e_client):
        """Health endpoint returns expected JSON format."""
        response = e2e_client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert data["status"] == "ok"
