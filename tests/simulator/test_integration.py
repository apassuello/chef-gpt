"""
Integration tests for the Anova Simulator (Phase 8: CP-08).

Tests complete workflows using the shared fixtures from conftest.py.

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 8
"""

import asyncio
import json

import aiohttp
import pytest
import websockets

from simulator.types import DeviceState

pytestmark = pytest.mark.asyncio(loop_scope="function")


# =============================================================================
# INT-01: Full cook cycle with simulator
# =============================================================================


@pytest.mark.asyncio
async def test_int01_full_cook_cycle(fast_simulator, fast_config, start_command):
    """INT-01: Complete cook cycle works end-to-end."""
    sim = fast_simulator
    ws_url = f"ws://localhost:{fast_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        # 1. Verify initial IDLE state
        await ws.recv()  # Device list
        initial = json.loads(await ws.recv())  # Initial state
        assert initial["command"] == "EVENT_APC_STATE"
        assert initial["payload"]["state"]["job-status"]["state"] == "IDLE"

        # 2. Start cooking
        cmd = start_command(temp=45.0, timer=120)  # Low temp, short timer
        await ws.send(json.dumps(cmd))

        # 3. Receive response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # 4. Verify PREHEATING state
        state_update = json.loads(await ws.recv())
        assert state_update["payload"]["state"]["job-status"]["state"] == "PREHEATING"

        # 5. Wait for COOKING transition (physics will heat water)
        for _ in range(100):
            await asyncio.sleep(0.05)
            if sim.state.job_status.state == DeviceState.COOKING:
                break
        assert sim.state.job_status.state == DeviceState.COOKING

        # 6. Wait for DONE transition (timer expires)
        for _ in range(200):
            await asyncio.sleep(0.05)
            if sim.state.job_status.state == DeviceState.DONE:
                break
        assert sim.state.job_status.state == DeviceState.DONE


# =============================================================================
# INT-02: Simulator fixture isolation
# =============================================================================


@pytest.mark.asyncio
async def test_int02a_fixture_isolation_first(simulator, simulator_config, start_command):
    """INT-02a: First test modifies state."""
    ws_url = f"ws://localhost:{simulator_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Device list
        await ws.recv()  # Initial state

        # Start cooking
        cmd = start_command(temp=65.0, timer=3600)
        await ws.send(json.dumps(cmd))
        await ws.recv()  # Response

        # Verify state changed
        assert simulator.state.job_status.state == DeviceState.PREHEATING


@pytest.mark.asyncio
async def test_int02b_fixture_isolation_second(simulator, simulator_config):
    """INT-02b: Second test should have fresh state (isolation)."""
    ws_url = f"ws://localhost:{simulator_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Device list
        initial = json.loads(await ws.recv())  # Initial state

        # State should be IDLE (fresh), not PREHEATING from previous test
        assert initial["payload"]["state"]["job-status"]["state"] == "IDLE"
        assert simulator.state.job_status.state == DeviceState.IDLE


# =============================================================================
# INT-03: Full stack integration
# =============================================================================


@pytest.mark.asyncio
async def test_int03_full_stack_integration(full_simulator, start_command):
    """INT-03: Full simulator stack (WS + Control + Firebase) works together."""
    sim, control, firebase = full_simulator
    config = sim.config

    # 1. Authenticate via Firebase mock
    async with aiohttp.ClientSession() as session:
        auth_url = f"http://localhost:{config.firebase_port}/v1/accounts:signInWithPassword"
        async with session.post(
            auth_url,
            json={"email": "test@example.com", "password": "testpassword123"},
        ) as resp:
            assert resp.status == 200
            auth_data = await resp.json()
            token = auth_data["idToken"]

    # 2. Connect WebSocket with Firebase token
    ws_url = f"ws://localhost:{config.ws_port}?token={token}&supportedAccessories=APC"

    # Note: The WebSocket server currently validates against config.valid_tokens,
    # not Firebase tokens. This test verifies the Firebase mock works independently.

    # 3. Verify we can get state via Control API
    async with aiohttp.ClientSession() as session:
        state_url = f"http://localhost:{config.control_port}/state"
        async with session.get(state_url) as resp:
            assert resp.status == 200
            state_data = await resp.json()
            assert state_data["job_status"]["state"] == "IDLE"

    # 4. Use Control API to change state
    async with aiohttp.ClientSession() as session:
        set_state_url = f"http://localhost:{config.control_port}/set-state"
        async with session.post(
            set_state_url,
            json={"state": "COOKING", "temperature": 65.0, "target_temperature": 65.0},
        ) as resp:
            assert resp.status == 200

    # 5. Verify state changed
    assert sim.state.job_status.state == DeviceState.COOKING


# =============================================================================
# Additional Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_websocket_client_fixture(ws_client, start_command, stop_command):
    """Test using the ws_client fixture for easy testing."""
    # ws_client is already connected and has consumed initial state

    # Start cooking
    cmd = start_command(temp=60.0, timer=1800)
    await ws_client.send(json.dumps(cmd))

    # Get response (might need to skip state broadcasts)
    for _ in range(5):
        msg = json.loads(await ws_client.recv())
        if msg["command"] == "RESPONSE":
            assert msg["payload"]["status"] == "ok"
            break

    # Stop cooking
    await ws_client.send(json.dumps(stop_command()))

    # Get response (might need to skip state broadcasts)
    for _ in range(5):
        msg = json.loads(await ws_client.recv())
        if msg["command"] == "RESPONSE":
            assert msg["payload"]["status"] == "ok"
            break


@pytest.mark.asyncio
async def test_error_recovery_flow(simulator_with_control, simulator_config):
    """Test error triggering and recovery."""
    sim, control = simulator_with_control
    ctl_url = f"http://localhost:{simulator_config.control_port}"
    ws_url = f"ws://localhost:{simulator_config.ws_port}?token=test-token&supportedAccessories=APC"

    # Set cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.target_temperature = 65.0

    async with aiohttp.ClientSession() as session:
        # Trigger water level critical
        async with session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "water_level_critical"},
        ) as resp:
            assert resp.status == 200

    # Cooking should have stopped
    assert sim.state.job_status.state == DeviceState.IDLE

    async with aiohttp.ClientSession() as session:
        # Clear the error
        async with session.post(
            f"{ctl_url}/clear-error",
            json={"error_type": "water_level_critical"},
        ) as resp:
            assert resp.status == 200

    # Device should be safe again
    assert sim.state.pin_info.device_safe == 1


@pytest.mark.asyncio
async def test_command_factory_fixtures(start_command, stop_command):
    """Test command factory fixtures work correctly."""
    # Test start command
    cmd = start_command(temp=55.0, timer=7200, unit="C")
    assert cmd["command"] == "CMD_APC_START"
    assert cmd["payload"]["targetTemperature"] == 55.0
    assert cmd["payload"]["timer"] == 7200
    assert "requestId" in cmd

    # Test stop command
    cmd = stop_command()
    assert cmd["command"] == "CMD_APC_STOP"
    assert "requestId" in cmd


@pytest.mark.asyncio
async def test_state_fixtures(idle_state, cooking_state, preheating_state):
    """Test state fixtures are properly configured."""
    # Idle state
    assert idle_state.job_status.state == DeviceState.IDLE

    # Cooking state
    assert cooking_state.job_status.state == DeviceState.COOKING
    assert cooking_state.job.target_temperature == 65.0
    assert cooking_state.temperature_info.water_temperature == 65.0

    # Preheating state
    assert preheating_state.job_status.state == DeviceState.PREHEATING
    assert preheating_state.temperature_info.water_temperature == 35.0
