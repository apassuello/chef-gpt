"""
Tests for physics simulation and state broadcasting (Phase 3-4: CP-03, CP-04).

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 3-4
"""

import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from simulator.config import Config
from simulator.server import AnovaSimulator
from simulator.types import DeviceState, generate_request_id

pytestmark = pytest.mark.asyncio(loop_scope="function")

# Unique ports - spread out to avoid collisions
PORT_BC = 18800
PORT_PH = 18810


def build_start_command(temp: float = 65.0, timer: int = 300):
    """Build CMD_APC_START message."""
    request_id = generate_request_id()
    return {
        "command": "CMD_APC_START",
        "requestId": request_id,
        "payload": {
            "cookerId": "anova sim-0000000000",
            "type": "pro",
            "targetTemperature": temp,
            "unit": "C",
            "timer": timer,
            "requestId": request_id,
        },
    }


# =============================================================================
# BROADCASTING TESTS (Phase 3) - Using fixtures
# =============================================================================


@pytest.fixture
def bc_config():
    """Configuration for broadcast tests."""
    return Config(ws_port=PORT_BC, time_scale=60.0, valid_tokens=["test-token"])


@pytest_asyncio.fixture
async def bc_simulator(bc_config):
    """Start simulator for broadcast tests."""
    sim = AnovaSimulator(config=bc_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def bc_url(bc_config):
    """WebSocket URL for broadcast tests."""
    return f"ws://localhost:{bc_config.ws_port}?token=test-token&supportedAccessories=APC"


@pytest.mark.asyncio
async def test_bc01_initial_state_on_connect(bc_simulator, bc_url):
    """BC-01: Should receive initial messages immediately on connect."""
    async with websockets.connect(bc_url) as ws:
        # First message: device list
        msg1 = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data1 = json.loads(msg1)
        assert data1["command"] == "EVENT_APC_WIFI_LIST"
        assert "payload" in data1
        assert isinstance(data1["payload"], list)

        # Second message: initial state
        msg2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data2 = json.loads(msg2)
        assert data2["command"] == "EVENT_APC_STATE"
        assert "payload" in data2
        assert "state" in data2["payload"]


@pytest.fixture
def bc04_config():
    """Configuration for BC-04 test."""
    return Config(ws_port=PORT_BC + 1, time_scale=60.0, valid_tokens=["test-token"])


@pytest_asyncio.fixture
async def bc04_simulator(bc04_config):
    """Start simulator for BC-04 test."""
    sim = AnovaSimulator(config=bc04_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def bc04_url(bc04_config):
    """WebSocket URL for BC-04 test."""
    return f"ws://localhost:{bc04_config.ws_port}?token=test-token&supportedAccessories=APC"


@pytest.mark.asyncio
async def test_bc04_state_reflects_current_values(bc04_simulator, bc04_url):
    """BC-04: State should reflect current device values."""
    async with websockets.connect(bc04_url) as ws:
        # Initial state
        await ws.recv()  # Device list
        initial = json.loads(await ws.recv())  # Initial state
        state = initial["payload"]["state"]
        assert state["job-status"]["state"] == "IDLE"

        # Start cooking
        cmd = build_start_command(temp=65.0, timer=300)
        await ws.send(json.dumps(cmd))
        await ws.recv()  # Response

        # Updated state
        updated = json.loads(await ws.recv())
        state = updated["payload"]["state"]
        assert state["job-status"]["state"] == "PREHEATING"
        assert state["job"]["target-temperature"] == 65.0


# =============================================================================
# PHYSICS TESTS (Phase 4) - Using fixtures
# =============================================================================


@pytest.fixture
def ph01_config():
    """Configuration for PH-01 test."""
    return Config(
        ws_port=PORT_PH,
        time_scale=600.0,
        heating_rate=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ph01_simulator(ph01_config):
    """Start simulator for PH-01 test."""
    sim = AnovaSimulator(config=ph01_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def ph01_url(ph01_config):
    """WebSocket URL for PH-01 test."""
    return f"ws://localhost:{ph01_config.ws_port}?token=test-token&supportedAccessories=APC"


@pytest.mark.asyncio
async def test_ph01_temperature_increases_during_preheat(ph01_simulator, ph01_url):
    """PH-01: Temperature should increase during preheating."""
    async with websockets.connect(ph01_url) as ws:
        await ws.recv()  # Device list
        await ws.recv()  # Initial state

        cmd = build_start_command(temp=65.0, timer=600)
        await ws.send(json.dumps(cmd))
        await ws.recv()  # Response
        await ws.recv()  # State

        initial = ph01_simulator.state.temperature_info.water_temperature

        for _ in range(20):
            await asyncio.sleep(0.05)
            if ph01_simulator.state.temperature_info.water_temperature > initial:
                break

        assert ph01_simulator.state.temperature_info.water_temperature > initial


@pytest.fixture
def ph02_config():
    """Configuration for PH-02 test."""
    return Config(
        ws_port=PORT_PH + 1,
        time_scale=600.0,
        heating_rate=120.0,  # Very fast
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ph02_simulator(ph02_config):
    """Start simulator for PH-02 test."""
    sim = AnovaSimulator(config=ph02_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def ph02_url(ph02_config):
    """WebSocket URL for PH-02 test."""
    return f"ws://localhost:{ph02_config.ws_port}?token=test-token&supportedAccessories=APC"


@pytest.mark.asyncio
async def test_ph02_preheating_to_cooking_transition(ph02_simulator, ph02_url):
    """PH-02: Should transition PREHEATING→COOKING at target temp."""
    async with websockets.connect(ph02_url) as ws:
        await ws.recv()  # Device list
        await ws.recv()  # Initial state

        cmd = build_start_command(temp=45.0, timer=600)  # Low target
        await ws.send(json.dumps(cmd))
        await ws.recv()
        await ws.recv()

        assert ph02_simulator.state.job_status.state == DeviceState.PREHEATING

        for _ in range(50):
            await asyncio.sleep(0.05)
            if ph02_simulator.state.job_status.state == DeviceState.COOKING:
                break

        assert ph02_simulator.state.job_status.state == DeviceState.COOKING


# =============================================================================
# PHYSICS TESTS WITHOUT WEBSOCKET (Direct state manipulation)
# =============================================================================


@pytest.fixture
def ph03_config():
    """Configuration for PH-03 test."""
    return Config(ws_port=PORT_PH + 2, time_scale=600.0, valid_tokens=["test-token"])


@pytest_asyncio.fixture
async def ph03_simulator(ph03_config):
    """Start simulator for PH-03 test."""
    sim = AnovaSimulator(config=ph03_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_ph03_timer_counts_down_during_cooking(ph03_simulator):
    """PH-03: Timer counts down during COOKING."""
    sim = ph03_simulator

    # Force into cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.target_temperature = 65.0
    sim.state.job_status.cook_time_remaining = 600
    sim.state.temperature_info.water_temperature = 65.0

    initial = sim.state.job_status.cook_time_remaining

    for _ in range(20):
        await asyncio.sleep(0.05)
        if sim.state.job_status.cook_time_remaining < initial:
            break

    assert sim.state.job_status.cook_time_remaining < initial


@pytest.fixture
def ph04_config():
    """Configuration for PH-04 test."""
    return Config(ws_port=PORT_PH + 3, time_scale=600.0, valid_tokens=["test-token"])


@pytest_asyncio.fixture
async def ph04_simulator(ph04_config):
    """Start simulator for PH-04 test."""
    sim = AnovaSimulator(config=ph04_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_ph04_cooking_to_done_transition(ph04_simulator):
    """PH-04: Should transition COOKING→DONE when timer=0."""
    sim = ph04_simulator

    # Force into cooking with short timer
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.target_temperature = 65.0
    sim.state.job_status.cook_time_remaining = 5  # Very short timer
    sim.state.temperature_info.water_temperature = 65.0

    for _ in range(100):
        await asyncio.sleep(0.02)
        if sim.state.job_status.state == DeviceState.DONE:
            break

    assert sim.state.job_status.state == DeviceState.DONE


@pytest.fixture
def ph05_config():
    """Configuration for PH-05 test."""
    return Config(ws_port=PORT_PH + 4, time_scale=600.0, valid_tokens=["test-token"])


@pytest_asyncio.fixture
async def ph05_simulator(ph05_config):
    """Start simulator for PH-05 test."""
    sim = AnovaSimulator(config=ph05_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_ph05_time_acceleration(ph05_simulator):
    """PH-05: Time acceleration affects physics speed."""
    sim = ph05_simulator

    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.target_temperature = 65.0
    sim.state.job_status.cook_time_remaining = 3000
    sim.state.temperature_info.water_temperature = 65.0

    initial = sim.state.job_status.cook_time_remaining
    await asyncio.sleep(0.5)  # Longer wait for physics

    decrease = initial - sim.state.job_status.cook_time_remaining
    assert decrease > 50  # Should decrease significantly (0.5s * 600 = 300s simulated)


@pytest.fixture
def ph06_config():
    """Configuration for PH-06 test."""
    return Config(
        ws_port=PORT_PH + 5,
        time_scale=600.0,
        cooling_rate=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ph06_simulator(ph06_config):
    """Start simulator for PH-06 test."""
    sim = AnovaSimulator(config=ph06_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_ph06_temperature_cools_when_idle(ph06_simulator):
    """PH-06: Temperature cools toward ambient when idle."""
    sim = ph06_simulator

    sim.state.job_status.state = DeviceState.IDLE
    sim.state.temperature_info.water_temperature = 70.0

    initial = sim.state.temperature_info.water_temperature

    for _ in range(20):
        await asyncio.sleep(0.05)
        if sim.state.temperature_info.water_temperature < initial:
            break

    assert sim.state.temperature_info.water_temperature < initial
