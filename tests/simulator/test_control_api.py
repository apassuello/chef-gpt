"""
Tests for Test Control API (Phase 6: CP-06).

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 6
"""

import asyncio
import json

import aiohttp
import pytest
import pytest_asyncio
import websockets

from simulator.config import Config
from simulator.control_api import ControlAPI
from simulator.server import AnovaSimulator
from simulator.types import DeviceState

pytestmark = pytest.mark.asyncio(loop_scope="function")

# Unique ports for control API tests
PORT_WS = 18900
PORT_CTL = 18901


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def ctl_config():
    """Configuration for control API tests."""
    return Config(
        ws_port=PORT_WS,
        control_port=PORT_CTL,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def simulator_with_control(ctl_config):
    """Start simulator with control API for tests."""
    sim = AnovaSimulator(config=ctl_config)
    await sim.start()

    control = ControlAPI(ctl_config, sim)
    await control.start()

    yield sim, control

    await control.stop()
    await sim.stop()


@pytest.fixture
def ctl_url(ctl_config):
    """Control API base URL."""
    return f"http://localhost:{ctl_config.control_port}"


@pytest.fixture
def ws_url(ctl_config):
    """WebSocket URL."""
    return f"ws://localhost:{ctl_config.ws_port}?token=test-token&supportedAccessories=APC"


# =============================================================================
# CTL-01: Reset to initial state
# =============================================================================


@pytest.mark.asyncio
async def test_ctl01_reset_to_initial_state(simulator_with_control, ctl_url):
    """CTL-01: Reset returns state to IDLE and ambient temperature."""
    sim, control = simulator_with_control

    # First, modify state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.temperature_info.water_temperature = 75.0
    sim.state.job.target_temperature = 80.0

    # Reset via API
    async with aiohttp.ClientSession() as session, session.post(f"{ctl_url}/reset") as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "reset"
        assert data["state"] == "IDLE"

    # Verify state was reset
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.temperature_info.water_temperature == sim.config.ambient_temp


# =============================================================================
# CTL-02: Set state to COOKING
# =============================================================================


@pytest.mark.asyncio
async def test_ctl02_set_state_to_cooking(simulator_with_control, ctl_url):
    """CTL-02: Set state updates state and physics become active."""
    sim, control = simulator_with_control

    # Set state to COOKING via API
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-state",
            json={
                "state": "COOKING",
                "temperature": 65.0,
                "target_temperature": 65.0,
                "timer_remaining": 3600,
            },
        ) as resp,
    ):
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "updated"
        assert data["state"] == "COOKING"

    # Verify state was updated
    assert sim.state.job_status.state == DeviceState.COOKING
    assert sim.state.job.mode == "COOKING"  # Must match job_status.state (spec Section 4.4)
    assert sim.state.temperature_info.water_temperature == 65.0
    assert sim.state.job.target_temperature == 65.0
    assert sim.state.job_status.cook_time_remaining == 3600


@pytest.mark.asyncio
async def test_set_state_maintains_job_mode_invariant(simulator_with_control, ctl_url):
    """Verify job.mode always matches job_status.state (spec Section 4.4 invariant)."""
    sim, control = simulator_with_control

    # Test all state transitions via /set-state
    states_to_test = ["PREHEATING", "COOKING", "DONE", "IDLE"]

    for state in states_to_test:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{ctl_url}/set-state",
                json={"state": state},
            ) as resp,
        ):
            assert resp.status == 200

        # Verify invariant: job.mode must equal job_status.state
        assert sim.state.job_status.state.value == state
        assert sim.state.job.mode == state, (
            f"job.mode invariant violated: job_status.state={state}, job.mode={sim.state.job.mode}"
        )


# =============================================================================
# CTL-03: Set offline
# =============================================================================


@pytest.fixture
def ctl03_config():
    """Configuration for CTL-03 test."""
    return Config(
        ws_port=PORT_WS + 10,
        control_port=PORT_CTL + 10,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ctl03_setup(ctl03_config):
    """Setup for CTL-03 test."""
    sim = AnovaSimulator(config=ctl03_config)
    await sim.start()

    control = ControlAPI(ctl03_config, sim)
    await control.start()

    yield sim, control, ctl03_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_ctl03_set_offline_disconnects_clients(ctl03_setup):
    """CTL-03: Set offline disconnects WebSocket clients."""
    sim, control, config = ctl03_setup

    ctl_url = f"http://localhost:{config.control_port}"
    ws_url = f"ws://localhost:{config.ws_port}?token=test-token&supportedAccessories=APC"

    # Connect a WebSocket client
    ws = await websockets.connect(ws_url)
    await ws.recv()  # Initial state

    # Verify client is connected
    assert len(sim.ws_server.clients) == 1

    # Set offline via API
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-offline",
            json={"offline": True},
        ) as resp,
    ):
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "offline"

    # Wait for disconnect
    await asyncio.sleep(0.1)

    # Verify client was disconnected
    assert len(sim.ws_server.clients) == 0
    assert sim.state.online is False

    await ws.close()


# =============================================================================
# CTL-04: Set time scale
# =============================================================================


@pytest.mark.asyncio
async def test_ctl04_set_time_scale(simulator_with_control, ctl_url):
    """CTL-04: Set time scale changes physics acceleration."""
    sim, control = simulator_with_control

    # Initial time scale
    original_scale = sim.config.time_scale

    # Set new time scale via API
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-time-scale",
            json={"time_scale": 120.0},
        ) as resp,
    ):
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "updated"
        assert data["time_scale"] == 120.0

    # Verify time scale was updated
    assert sim.config.time_scale == 120.0
    assert sim.config.time_scale != original_scale


# =============================================================================
# CTL-05: Get state
# =============================================================================


@pytest.mark.asyncio
async def test_ctl05_get_state(simulator_with_control, ctl_url):
    """CTL-05: Get state returns full state JSON."""
    sim, control = simulator_with_control

    # Set some state
    sim.state.job_status.state = DeviceState.PREHEATING
    sim.state.job.target_temperature = 55.0
    sim.state.temperature_info.water_temperature = 30.0

    # Get state via API
    async with aiohttp.ClientSession() as session, session.get(f"{ctl_url}/state") as resp:
        assert resp.status == 200
        data = await resp.json()

        # Verify structure
        assert "cooker_id" in data
        assert "device_type" in data
        assert "job" in data
        assert "job_status" in data
        assert "temperature_info" in data
        assert "pin_info" in data

        # Verify values
        assert data["job_status"]["state"] == "PREHEATING"
        assert data["job"]["target_temperature"] == 55.0
        assert data["temperature_info"]["water_temperature"] == 30.0


# =============================================================================
# CTL-06: Get messages
# =============================================================================


@pytest.fixture
def ctl06_config():
    """Configuration for CTL-06 test."""
    return Config(
        ws_port=PORT_WS + 20,
        control_port=PORT_CTL + 20,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ctl06_setup(ctl06_config):
    """Setup for CTL-06 test."""
    sim = AnovaSimulator(config=ctl06_config)
    await sim.start()

    control = ControlAPI(ctl06_config, sim)
    await control.start()

    yield sim, control, ctl06_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_ctl06_get_messages(ctl06_setup):
    """CTL-06: Get messages returns message history."""
    sim, control, config = ctl06_setup

    ctl_url = f"http://localhost:{config.control_port}"
    ws_url = f"ws://localhost:{config.ws_port}?token=test-token&supportedAccessories=APC"

    # Generate some messages by connecting and sending a command
    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state (outbound)

        # Send a command (inbound)
        await ws.send(
            json.dumps(
                {
                    "command": "CMD_APC_START",
                    "requestId": "test-request-1",
                    "payload": {
                        "cookerId": "anova sim-0000000000",
                        "type": "pro",
                        "targetTemperature": 65.0,
                        "unit": "C",
                        "timer": 3600,
                    },
                }
            )
        )
        await ws.recv()  # Response (outbound)

    # Get messages via API
    async with aiohttp.ClientSession() as session, session.get(f"{ctl_url}/messages") as resp:
        assert resp.status == 200
        data = await resp.json()

        assert "count" in data
        assert "messages" in data
        assert data["count"] > 0

        # Check we have both inbound and outbound messages
        directions = {m["direction"] for m in data["messages"]}
        assert "outbound" in directions


# =============================================================================
# ADDITIONAL TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_set_state_invalid_state(simulator_with_control, ctl_url):
    """Set state with invalid state value returns error."""
    sim, control = simulator_with_control

    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-state",
            json={"state": "INVALID_STATE"},
        ) as resp,
    ):
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "INVALID_STATE"


@pytest.mark.asyncio
async def test_set_time_scale_invalid(simulator_with_control, ctl_url):
    """Set time scale with invalid value returns error."""
    sim, control = simulator_with_control

    async with aiohttp.ClientSession() as session:
        # Missing time_scale
        async with session.post(
            f"{ctl_url}/set-time-scale",
            json={},
        ) as resp:
            assert resp.status == 400
            data = await resp.json()
            assert data["error"] == "MISSING_TIME_SCALE"

        # Negative time_scale
        async with session.post(
            f"{ctl_url}/set-time-scale",
            json={"time_scale": -1},
        ) as resp:
            assert resp.status == 400
            data = await resp.json()
            assert data["error"] == "INVALID_TIME_SCALE"


@pytest.mark.asyncio
async def test_health_endpoint(simulator_with_control, ctl_url):
    """Health endpoint returns status."""
    sim, control = simulator_with_control

    async with aiohttp.ClientSession() as session, session.get(f"{ctl_url}/health") as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "control-api"
        assert "simulator_state" in data


@pytest.mark.asyncio
async def test_get_messages_with_filter(ctl06_setup):
    """Get messages with direction filter."""
    sim, control, config = ctl06_setup

    ctl_url = f"http://localhost:{config.control_port}"
    ws_url = f"ws://localhost:{config.ws_port}?token=test-token&supportedAccessories=APC"

    # Generate some messages
    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state
        await ws.send(
            json.dumps(
                {
                    "command": "CMD_APC_START",
                    "requestId": "test-request-2",
                    "payload": {
                        "cookerId": "anova sim-0000000000",
                        "type": "pro",
                        "targetTemperature": 65.0,
                        "unit": "C",
                        "timer": 3600,
                    },
                }
            )
        )
        await ws.recv()

    # Get only inbound messages
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"{ctl_url}/messages?direction=inbound") as resp,
    ):
        assert resp.status == 200
        data = await resp.json()
        for msg in data["messages"]:
            assert msg["direction"] == "inbound"
