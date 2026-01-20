"""
Edge case and protocol conformance tests (identified by audit).

These tests cover scenarios that weren't covered in the initial test suite:
- Protocol behavior (PROT-XX)
- Command handling (CMD-XX)
- State machine transitions (SM-XX)
- Additional error types (ERR-XX)
- Control API edge cases (CTL-XX)
- WebSocket edge cases (WS-XX)

Reference: docs/SIMULATOR-SPECIFICATION.md
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

# Unique ports for edge case tests
PORT_WS = 19050
PORT_CTL = 19051


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def edge_config():
    """Configuration for edge case tests."""
    return Config(
        ws_port=PORT_WS,
        control_port=PORT_CTL,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def edge_simulator(edge_config):
    """Simulator for edge case tests."""
    sim = AnovaSimulator(config=edge_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest_asyncio.fixture
async def edge_setup(edge_config):
    """Simulator with control API for edge case tests."""
    sim = AnovaSimulator(config=edge_config)
    await sim.start()

    control = ControlAPI(edge_config, sim)
    await control.start()

    yield sim, control, edge_config

    await control.stop()
    await sim.stop()


# =============================================================================
# PROT-03: Temperature Unit Handling
# =============================================================================


@pytest.fixture
def prot03_config():
    """Configuration for PROT-03 test."""
    return Config(
        ws_port=PORT_WS + 10,
        control_port=PORT_CTL + 10,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def prot03_simulator(prot03_config):
    """Simulator for PROT-03 test."""
    sim = AnovaSimulator(config=prot03_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_prot03_fahrenheit_temperature_handling(prot03_simulator, prot03_config):
    """PROT-03: Fahrenheit temperature in request is converted to Celsius in state."""
    sim = prot03_simulator
    ws_url = f"ws://localhost:{prot03_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send start command with Fahrenheit temperature
        # 149°F = 65°C
        cmd = {
            "command": "CMD_APC_START",
            "requestId": "test-prot03",
            "payload": {
                "targetTemperature": 149.0,
                "timer": 3600,
                "unit": "F",
            },
        }
        await ws.send(json.dumps(cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify state has temperature in Celsius
        state_update = json.loads(await ws.recv())
        # Should be approximately 65°C
        target_temp = state_update["payload"]["state"]["job"]["target-temperature"]
        assert 64.5 <= target_temp <= 65.5


@pytest.mark.asyncio
async def test_prot03_fahrenheit_below_minimum(prot03_simulator, prot03_config):
    """PROT-03: Fahrenheit below minimum (104°F) is rejected."""
    sim = prot03_simulator
    ws_url = f"ws://localhost:{prot03_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send start command with temperature below minimum in Fahrenheit
        # 100°F < 104°F minimum
        cmd = {
            "command": "CMD_APC_START",
            "requestId": "test-prot03-min",
            "payload": {
                "targetTemperature": 100.0,
                "timer": 3600,
                "unit": "F",
            },
        }
        await ws.send(json.dumps(cmd))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"
        assert "below minimum" in response["payload"]["message"].lower()


# =============================================================================
# CMD-01/02: SET_TEMPERATURE and SET_TIMER Commands
# =============================================================================


@pytest.fixture
def cmd_config():
    """Configuration for CMD tests."""
    return Config(
        ws_port=PORT_WS + 20,
        control_port=PORT_CTL + 20,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def cmd_simulator(cmd_config):
    """Simulator for CMD tests."""
    sim = AnovaSimulator(config=cmd_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_cmd01_set_temperature(cmd_simulator, cmd_config):
    """CMD-01: CMD_APC_SET_TARGET_TEMP updates target temperature."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send set temperature command
        cmd = {
            "command": "CMD_APC_SET_TARGET_TEMP",
            "requestId": "test-cmd01",
            "payload": {
                "targetTemperature": 70.0,
                "unit": "C",
            },
        }
        await ws.send(json.dumps(cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify state updated
        assert sim.state.job.target_temperature == 70.0


@pytest.mark.asyncio
async def test_cmd01_set_temperature_fahrenheit(cmd_simulator, cmd_config):
    """CMD-01: CMD_APC_SET_TARGET_TEMP works with Fahrenheit."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send set temperature command in Fahrenheit (158°F = 70°C)
        cmd = {
            "command": "CMD_APC_SET_TARGET_TEMP",
            "requestId": "test-cmd01-f",
            "payload": {
                "targetTemperature": 158.0,
                "unit": "F",
            },
        }
        await ws.send(json.dumps(cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify state updated (should be ~70°C)
        assert 69.5 <= sim.state.job.target_temperature <= 70.5


@pytest.mark.asyncio
async def test_cmd01_set_temperature_invalid(cmd_simulator, cmd_config):
    """CMD-01: CMD_APC_SET_TARGET_TEMP rejects invalid temperature."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send invalid temperature
        cmd = {
            "command": "CMD_APC_SET_TARGET_TEMP",
            "requestId": "test-cmd01-inv",
            "payload": {
                "targetTemperature": 30.0,  # Below minimum
                "unit": "C",
            },
        }
        await ws.send(json.dumps(cmd))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"


@pytest.mark.asyncio
async def test_cmd02_set_timer(cmd_simulator, cmd_config):
    """CMD-02: CMD_APC_SET_TIMER updates timer."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send set timer command
        cmd = {
            "command": "CMD_APC_SET_TIMER",
            "requestId": "test-cmd02",
            "payload": {
                "timer": 7200,
            },
        }
        await ws.send(json.dumps(cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify state updated
        assert sim.state.job.cook_time_seconds == 7200
        assert sim.state.job_status.cook_time_remaining == 7200


@pytest.mark.asyncio
async def test_cmd02_set_timer_invalid(cmd_simulator, cmd_config):
    """CMD-02: CMD_APC_SET_TIMER rejects invalid timer."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send invalid timer (too long)
        cmd = {
            "command": "CMD_APC_SET_TIMER",
            "requestId": "test-cmd02-inv",
            "payload": {
                "timer": 400000,  # Above maximum
            },
        }
        await ws.send(json.dumps(cmd))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"


# =============================================================================
# CMD-03: Unknown Command
# =============================================================================


@pytest.mark.asyncio
async def test_cmd03_unknown_command(cmd_simulator, cmd_config):
    """CMD-03: Unknown command returns INVALID_COMMAND error."""
    sim = cmd_simulator
    ws_url = f"ws://localhost:{cmd_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Send unknown command
        cmd = {
            "command": "CMD_APC_UNKNOWN",
            "requestId": "test-cmd03",
            "payload": {},
        }
        await ws.send(json.dumps(cmd))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"
        assert response["payload"]["code"] == "INVALID_COMMAND"


# =============================================================================
# WS-01: Multiple Concurrent Clients
# =============================================================================


@pytest.fixture
def ws01_config():
    """Configuration for WS-01 test."""
    return Config(
        ws_port=PORT_WS + 30,
        control_port=PORT_CTL + 30,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ws01_simulator(ws01_config):
    """Simulator for WS-01 test."""
    sim = AnovaSimulator(config=ws01_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_ws01_multiple_concurrent_clients(ws01_simulator, ws01_config):
    """WS-01: Multiple clients can connect and receive state updates."""
    sim = ws01_simulator
    ws_url = f"ws://localhost:{ws01_config.ws_port}?token=test-token&supportedAccessories=APC"

    # Connect three clients
    clients = []
    for i in range(3):
        ws = await websockets.connect(ws_url)
        initial = json.loads(await ws.recv())
        assert initial["command"] == "EVENT_APC_STATE"
        clients.append(ws)

    # Verify all clients are connected
    assert len(sim.ws_server.clients) == 3

    # First client sends a command
    cmd = {
        "command": "CMD_APC_START",
        "requestId": "test-ws01",
        "payload": {
            "targetTemperature": 65.0,
            "timer": 3600,
        },
    }
    await clients[0].send(json.dumps(cmd))

    # First client should receive response
    response = json.loads(await clients[0].recv())
    assert response["command"] == "RESPONSE"
    assert response["payload"]["status"] == "ok"

    # All clients should receive state broadcast
    for i, ws in enumerate(clients):
        state = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        assert state["command"] == "EVENT_APC_STATE"
        assert state["payload"]["state"]["job-status"]["state"] == "PREHEATING"

    # Clean up
    for ws in clients:
        await ws.close()


# =============================================================================
# SM-02/03: Stop During PREHEATING/COOKING
# =============================================================================


@pytest.fixture
def sm_config():
    """Configuration for SM tests."""
    return Config(
        ws_port=PORT_WS + 40,
        control_port=PORT_CTL + 40,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def sm_simulator(sm_config):
    """Simulator for SM tests."""
    sim = AnovaSimulator(config=sm_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.mark.asyncio
async def test_sm02_stop_during_preheating(sm_simulator, sm_config):
    """SM-02: Stop during PREHEATING returns to IDLE."""
    sim = sm_simulator
    ws_url = f"ws://localhost:{sm_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Start cooking
        start_cmd = {
            "command": "CMD_APC_START",
            "requestId": "test-sm02-start",
            "payload": {
                "targetTemperature": 65.0,
                "timer": 3600,
            },
        }
        await ws.send(json.dumps(start_cmd))
        await ws.recv()  # Response
        await ws.recv()  # State update

        # Verify PREHEATING
        assert sim.state.job_status.state == DeviceState.PREHEATING

        # Stop cooking
        stop_cmd = {
            "command": "CMD_APC_STOP",
            "requestId": "test-sm02-stop",
            "payload": {},
        }
        await ws.send(json.dumps(stop_cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify IDLE
        assert sim.state.job_status.state == DeviceState.IDLE
        assert sim.state.job.mode == "IDLE"


@pytest.mark.asyncio
async def test_sm03_stop_during_cooking_preserves_temp(sm_simulator, sm_config):
    """SM-03: Stop during COOKING returns to IDLE, water temp is preserved."""
    sim = sm_simulator

    # Manually set to COOKING state with hot water
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.mode = "COOKING"
    sim.state.job.target_temperature = 65.0
    sim.state.job.cook_time_seconds = 3600
    sim.state.job_status.cook_time_remaining = 1800
    sim.state.temperature_info.water_temperature = 65.0
    sim.state.heater_control.duty_cycle = 100.0
    sim.state.motor_info.rpm = 1200

    ws_url = f"ws://localhost:{sm_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Stop cooking
        stop_cmd = {
            "command": "CMD_APC_STOP",
            "requestId": "test-sm03",
            "payload": {},
        }
        await ws.send(json.dumps(stop_cmd))

        # Get response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "ok"

        # Verify IDLE
        assert sim.state.job_status.state == DeviceState.IDLE

        # Water temperature should still be hot (preserved, will cool naturally)
        assert sim.state.temperature_info.water_temperature >= 60.0


# =============================================================================
# ERR-06/07/08: Additional Error Types
# =============================================================================


@pytest.fixture
def err_additional_config():
    """Configuration for additional error tests."""
    return Config(
        ws_port=PORT_WS + 50,
        control_port=PORT_CTL + 50,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def err_additional_setup(err_additional_config):
    """Setup for additional error tests."""
    sim = AnovaSimulator(config=err_additional_config)
    await sim.start()

    control = ControlAPI(err_additional_config, sim)
    await control.start()

    yield sim, control, err_additional_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_err06_heater_overtemp(err_additional_setup):
    """ERR-06: Heater overtemp stops cooking and sets device_safe=0."""
    sim, control, config = err_additional_setup
    ctl_url = f"http://localhost:{config.control_port}"

    # Set cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.mode = "COOKING"
    sim.state.job.target_temperature = 65.0

    # Trigger heater overtemp
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "heater_overtemp"},
        ) as resp,
    ):
        assert resp.status == 200

    # Verify effects
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.pin_info.device_safe == 0
    assert sim.state.heater_control.duty_cycle == 0.0
    assert sim.state.temperature_info.heater_temperature >= 100.0


@pytest.mark.asyncio
async def test_err07_triac_overtemp(err_additional_setup):
    """ERR-07: Triac overtemp stops cooking and sets device_safe=0."""
    sim, control, config = err_additional_setup
    ctl_url = f"http://localhost:{config.control_port}"

    # Set cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.mode = "COOKING"
    sim.state.job.target_temperature = 65.0

    # Trigger triac overtemp
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "triac_overtemp"},
        ) as resp,
    ):
        assert resp.status == 200

    # Verify effects
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.pin_info.device_safe == 0
    assert sim.state.temperature_info.triac_temperature >= 80.0


@pytest.mark.asyncio
async def test_err08_water_leak(err_additional_setup):
    """ERR-08: Water leak stops cooking and sets device_safe=0."""
    sim, control, config = err_additional_setup
    ctl_url = f"http://localhost:{config.control_port}"

    # Set cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.mode = "COOKING"
    sim.state.job.target_temperature = 65.0

    # Trigger water leak
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "water_leak"},
        ) as resp,
    ):
        assert resp.status == 200

    # Verify effects
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.pin_info.device_safe == 0
    assert sim.state.pin_info.water_leak == 1


# =============================================================================
# CTL-01/02/03: Control API Edge Cases
# =============================================================================


@pytest.fixture
def ctl_config():
    """Configuration for CTL tests."""
    return Config(
        ws_port=PORT_WS + 60,
        control_port=PORT_CTL + 60,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def ctl_setup(ctl_config):
    """Setup for CTL tests."""
    sim = AnovaSimulator(config=ctl_config)
    await sim.start()

    control = ControlAPI(ctl_config, sim)
    await control.start()

    yield sim, control, ctl_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_ctl01_set_state_invalid(ctl_setup):
    """CTL-01: /set-state with invalid state returns 400."""
    sim, control, config = ctl_setup
    ctl_url = f"http://localhost:{config.control_port}"

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
async def test_ctl02_reset_while_cooking(ctl_setup):
    """CTL-02: /reset while cooking stops cook and resets state."""
    sim, control, config = ctl_setup
    ctl_url = f"http://localhost:{config.control_port}"

    # Set cooking state
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.mode = "COOKING"
    sim.state.job.target_temperature = 65.0
    sim.state.temperature_info.water_temperature = 65.0

    # Reset
    async with aiohttp.ClientSession() as session, session.post(f"{ctl_url}/reset") as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "reset"
        assert data["state"] == "IDLE"

    # Verify state reset
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.job.mode == "IDLE"
    assert sim.state.job.target_temperature == 0.0
    assert sim.state.temperature_info.water_temperature == sim.config.ambient_temp


@pytest.mark.asyncio
async def test_ctl03_time_scale_limits(ctl_setup):
    """CTL-03: /set-time-scale rejects invalid time_scale values."""
    sim, control, config = ctl_setup
    ctl_url = f"http://localhost:{config.control_port}"

    # Test negative time_scale
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-time-scale",
            json={"time_scale": -1.0},
        ) as resp,
    ):
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "INVALID_TIME_SCALE"

    # Test zero time_scale
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{ctl_url}/set-time-scale",
            json={"time_scale": 0},
        ) as resp,
    ):
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "INVALID_TIME_SCALE"

    # Test valid time_scale
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

    # Verify time_scale updated
    assert sim.config.time_scale == 120.0


# =============================================================================
# Additional Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_stop_when_idle_returns_error(sm_simulator, sm_config):
    """Stopping when already IDLE returns error."""
    sim = sm_simulator
    ws_url = f"ws://localhost:{sm_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Try to stop when idle
        stop_cmd = {
            "command": "CMD_APC_STOP",
            "requestId": "test-stop-idle",
            "payload": {},
        }
        await ws.send(json.dumps(stop_cmd))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"
        assert response["payload"]["code"] == "NO_ACTIVE_COOK"


@pytest.mark.asyncio
async def test_start_when_already_cooking_returns_error(sm_simulator, sm_config):
    """Starting when already cooking returns DEVICE_BUSY error."""
    sim = sm_simulator
    ws_url = f"ws://localhost:{sm_config.ws_port}?token=test-token&supportedAccessories=APC"

    async with websockets.connect(ws_url) as ws:
        await ws.recv()  # Initial state

        # Start cooking
        start_cmd = {
            "command": "CMD_APC_START",
            "requestId": "test-start-1",
            "payload": {
                "targetTemperature": 65.0,
                "timer": 3600,
            },
        }
        await ws.send(json.dumps(start_cmd))
        await ws.recv()  # Response
        await ws.recv()  # State update

        # Try to start again
        start_cmd2 = {
            "command": "CMD_APC_START",
            "requestId": "test-start-2",
            "payload": {
                "targetTemperature": 70.0,
                "timer": 7200,
            },
        }
        await ws.send(json.dumps(start_cmd2))

        # Get error response
        response = json.loads(await ws.recv())
        assert response["command"] == "RESPONSE"
        assert response["payload"]["status"] == "error"
        assert response["payload"]["code"] == "DEVICE_BUSY"
