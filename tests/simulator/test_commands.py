"""
Tests for APC command handlers (Phase 2: CP-02).

Test cases:
- CMD-01: START with valid params
- CMD-02: START with temp < 40
- CMD-03: START with temp > 100
- CMD-04: START when already cooking
- CMD-05: STOP when cooking
- CMD-06: STOP when idle
- CMD-07: SET_TARGET_TEMP valid
- CMD-08: SET_TIMER valid

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 2
"""

import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from simulator.config import Config
from simulator.server import AnovaSimulator
from simulator.types import generate_request_id

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture
def config():
    """Test configuration."""
    return Config(
        ws_port=18766,  # Different port to avoid conflicts
        time_scale=60.0,
        valid_tokens=["valid-test-token"],
    )


@pytest_asyncio.fixture
async def simulator(config):
    """Start simulator for tests."""
    sim = AnovaSimulator(config=config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def ws_url(config):
    """WebSocket URL."""
    return f"ws://localhost:{config.ws_port}?token=valid-test-token&supportedAccessories=APC"


def build_start_command(temp: float = 65.0, timer: int = 5400, unit: str = "C"):
    """Build CMD_APC_START message."""
    request_id = generate_request_id()
    return {
        "command": "CMD_APC_START",
        "requestId": request_id,
        "payload": {
            "cookerId": "anova sim-0000000000",
            "type": "pro",
            "targetTemperature": temp,
            "unit": unit,
            "timer": timer,
            "requestId": request_id,
        },
    }


def build_stop_command():
    """Build CMD_APC_STOP message."""
    request_id = generate_request_id()
    return {
        "command": "CMD_APC_STOP",
        "requestId": request_id,
        "payload": {
            "cookerId": "anova sim-0000000000",
            "type": "pro",
            "requestId": request_id,
        },
    }


def build_set_temp_command(temp: float, unit: str = "C"):
    """Build CMD_APC_SET_TARGET_TEMP message."""
    request_id = generate_request_id()
    return {
        "command": "CMD_APC_SET_TARGET_TEMP",
        "requestId": request_id,
        "payload": {
            "cookerId": "anova sim-0000000000",
            "type": "pro",
            "targetTemperature": temp,
            "unit": unit,
            "requestId": request_id,
        },
    }


def build_set_timer_command(timer: int):
    """Build CMD_APC_SET_TIMER message."""
    request_id = generate_request_id()
    return {
        "command": "CMD_APC_SET_TIMER",
        "requestId": request_id,
        "payload": {
            "cookerId": "anova sim-0000000000",
            "type": "pro",
            "timer": timer,
            "requestId": request_id,
        },
    }


class TestStartCommand:
    """Test CMD_APC_START command."""

    @pytest.mark.asyncio
    async def test_cmd01_start_valid_params(self, simulator, ws_url):
        """CMD-01: START with valid params should succeed."""
        async with websockets.connect(ws_url) as ws:
            # Consume initial state
            await ws.recv()

            # Send START command
            cmd = build_start_command(temp=65.0, timer=5400)
            await ws.send(json.dumps(cmd))

            # Should receive success response
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["requestId"] == cmd["requestId"]
            assert response["payload"]["status"] == "ok"

            # Should also receive state update
            state_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert state_msg["command"] == "EVENT_APC_STATE"
            assert state_msg["payload"]["state"]["job-status"]["state"] == "PREHEATING"

    @pytest.mark.asyncio
    async def test_cmd02_start_temp_too_low(self, simulator, ws_url):
        """CMD-02: START with temp < 40°C should fail."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            cmd = build_start_command(temp=35.0)
            await ws.send(json.dumps(cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "error"
            assert response["payload"]["code"] == "INVALID_TEMPERATURE"

    @pytest.mark.asyncio
    async def test_cmd03_start_temp_too_high(self, simulator, ws_url):
        """CMD-03: START with temp > 100°C should fail."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            cmd = build_start_command(temp=105.0)
            await ws.send(json.dumps(cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "error"
            assert response["payload"]["code"] == "INVALID_TEMPERATURE"

    @pytest.mark.asyncio
    async def test_cmd04_start_when_cooking(self, simulator, ws_url):
        """CMD-04: START when already cooking should fail with DEVICE_BUSY."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            # Start first cook
            cmd1 = build_start_command(temp=65.0, timer=5400)
            await ws.send(json.dumps(cmd1))
            await ws.recv()  # Response
            await ws.recv()  # State update

            # Try to start second cook
            cmd2 = build_start_command(temp=70.0, timer=3600)
            await ws.send(json.dumps(cmd2))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "error"
            assert response["payload"]["code"] == "DEVICE_BUSY"


class TestStopCommand:
    """Test CMD_APC_STOP command."""

    @pytest.mark.asyncio
    async def test_cmd05_stop_when_cooking(self, simulator, ws_url):
        """CMD-05: STOP when cooking should succeed."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            # Start cook
            start_cmd = build_start_command()
            await ws.send(json.dumps(start_cmd))
            await ws.recv()  # Response
            await ws.recv()  # State update

            # Stop cook
            stop_cmd = build_stop_command()
            await ws.send(json.dumps(stop_cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "ok"

            # Should also receive state update showing IDLE
            state_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert state_msg["payload"]["state"]["job-status"]["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_cmd06_stop_when_idle(self, simulator, ws_url):
        """CMD-06: STOP when idle should fail with NO_ACTIVE_COOK."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            # Try to stop without active cook
            cmd = build_stop_command()
            await ws.send(json.dumps(cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "error"
            assert response["payload"]["code"] == "NO_ACTIVE_COOK"


class TestSetTempCommand:
    """Test CMD_APC_SET_TARGET_TEMP command."""

    @pytest.mark.asyncio
    async def test_cmd07_set_temp_valid(self, simulator, ws_url):
        """CMD-07: SET_TARGET_TEMP with valid temp should succeed."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            # Start cook first
            start_cmd = build_start_command(temp=65.0)
            await ws.send(json.dumps(start_cmd))
            await ws.recv()  # Response
            await ws.recv()  # State update

            # Change temperature
            set_temp_cmd = build_set_temp_command(temp=70.0)
            await ws.send(json.dumps(set_temp_cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "ok"

            # Verify temp changed in state
            state_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert state_msg["payload"]["state"]["job"]["target-temperature"] == 70.0


class TestSetTimerCommand:
    """Test CMD_APC_SET_TIMER command."""

    @pytest.mark.asyncio
    async def test_cmd08_set_timer_valid(self, simulator, ws_url):
        """CMD-08: SET_TIMER with valid timer should succeed."""
        async with websockets.connect(ws_url) as ws:
            await ws.recv()  # Initial state

            # Start cook first
            start_cmd = build_start_command(timer=5400)
            await ws.send(json.dumps(start_cmd))
            await ws.recv()  # Response
            await ws.recv()  # State update

            # Change timer
            set_timer_cmd = build_set_timer_command(timer=7200)
            await ws.send(json.dumps(set_timer_cmd))

            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))

            assert response["command"] == "RESPONSE"
            assert response["payload"]["status"] == "ok"

            # Verify timer changed in state
            state_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert state_msg["payload"]["state"]["job"]["cook-time-seconds"] == 7200
