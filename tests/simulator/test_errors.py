"""
Tests for error simulation (Phase 7: CP-07).

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 7
"""

import asyncio
import json

import aiohttp
import pytest
import pytest_asyncio
import websockets

from simulator.config import Config
from simulator.control_api import ControlAPI
from simulator.errors import ErrorSimulator, ErrorType
from simulator.server import AnovaSimulator
from simulator.types import DeviceState

# Note: Only async tests should be marked with @pytest.mark.asyncio

# Unique ports for error tests
PORT_WS = 18950
PORT_CTL = 18951


# =============================================================================
# ERROR SIMULATOR UNIT TESTS
# =============================================================================


class TestErrorSimulator:
    """Tests for ErrorSimulator class."""

    def test_initial_state_no_errors(self):
        """All errors should be disabled by default."""
        sim = ErrorSimulator()
        for error_type in ErrorType:
            assert not sim.is_error_active(error_type)

    @pytest.mark.asyncio
    async def test_trigger_and_clear_error(self):
        """Should be able to trigger and clear errors."""
        sim = ErrorSimulator()

        # Trigger error
        await sim.trigger_error(ErrorType.WATER_LEVEL_LOW)
        assert sim.is_error_active(ErrorType.WATER_LEVEL_LOW)

        # Clear error
        await sim.clear_error(ErrorType.WATER_LEVEL_LOW)
        assert not sim.is_error_active(ErrorType.WATER_LEVEL_LOW)

    @pytest.mark.asyncio
    async def test_get_active_errors(self):
        """Should return list of active errors."""
        sim = ErrorSimulator()

        await sim.trigger_error(ErrorType.WATER_LEVEL_LOW)
        await sim.trigger_error(ErrorType.MOTOR_STUCK)

        active = sim.get_active_errors()
        assert ErrorType.WATER_LEVEL_LOW in active
        assert ErrorType.MOTOR_STUCK in active
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_auto_clear_duration(self):
        """Error should auto-clear after duration."""
        sim = ErrorSimulator()

        await sim.trigger_error(ErrorType.WATER_LEVEL_LOW, duration=0.1)
        assert sim.is_error_active(ErrorType.WATER_LEVEL_LOW)

        # Wait for auto-clear
        await asyncio.sleep(0.2)
        assert not sim.is_error_active(ErrorType.WATER_LEVEL_LOW)

    def test_intermittent_failure_rate(self):
        """Intermittent failure should respect failure rate."""
        sim = ErrorSimulator()

        # With 0% failure rate, should never fail
        sim._errors[ErrorType.INTERMITTENT_FAILURE].enabled = True
        sim._errors[ErrorType.INTERMITTENT_FAILURE].failure_rate = 0.0
        failures = sum(sim.should_fail_command() for _ in range(100))
        assert failures == 0

        # With 100% failure rate, should always fail
        sim._errors[ErrorType.INTERMITTENT_FAILURE].failure_rate = 1.0
        failures = sum(sim.should_fail_command() for _ in range(100))
        assert failures == 100

    def test_network_latency(self):
        """Network latency should return configured value."""
        sim = ErrorSimulator()

        # No latency by default
        assert sim.get_latency() == 0.0

        # With latency enabled
        sim._errors[ErrorType.NETWORK_LATENCY].enabled = True
        sim._errors[ErrorType.NETWORK_LATENCY].latency_ms = 500
        assert sim.get_latency() == 0.5


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.fixture
def err_config():
    """Configuration for error tests."""
    return Config(
        ws_port=PORT_WS,
        control_port=PORT_CTL,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def error_setup(err_config):
    """Setup simulator with control API for error tests."""
    sim = AnovaSimulator(config=err_config)
    await sim.start()

    control = ControlAPI(err_config, sim)
    await control.start()

    yield sim, control, err_config

    await control.stop()
    await sim.stop()


# =============================================================================
# ERR-01: Device goes offline
# =============================================================================


@pytest.fixture
def err01_config():
    """Configuration for ERR-01 test."""
    return Config(
        ws_port=PORT_WS + 10,
        control_port=PORT_CTL + 10,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def err01_setup(err01_config):
    """Setup for ERR-01 test."""
    sim = AnovaSimulator(config=err01_config)
    await sim.start()

    control = ControlAPI(err01_config, sim)
    await control.start()

    yield sim, control, err01_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_err01_device_goes_offline(err01_setup):
    """ERR-01: Device offline should close WebSocket with 1006."""
    sim, control, config = err01_setup

    ctl_url = f"http://localhost:{config.control_port}"
    ws_url = f"ws://localhost:{config.ws_port}?token=test-token&supportedAccessories=APC"

    # Connect WebSocket client
    ws = await websockets.connect(ws_url)
    await ws.recv()  # Initial state

    # Verify connected
    assert len(sim.ws_server.clients) == 1

    # Trigger device offline via API
    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "device_offline"},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "triggered"

    # Wait for disconnect
    await asyncio.sleep(0.1)

    # Client should be disconnected
    assert len(sim.ws_server.clients) == 0
    assert sim.state.online is False

    await ws.close()


# =============================================================================
# ERR-02: Water level low warning
# =============================================================================


@pytest.fixture
def err02_config():
    """Configuration for ERR-02 test."""
    return Config(
        ws_port=PORT_WS + 20,
        control_port=PORT_CTL + 20,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def err02_setup(err02_config):
    """Setup for ERR-02 test."""
    sim = AnovaSimulator(config=err02_config)
    await sim.start()

    control = ControlAPI(err02_config, sim)
    await control.start()

    yield sim, control, err02_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_err02_water_level_low_warning(err02_setup):
    """ERR-02: Water level low sets pin-info.water-level-low=1."""
    sim, control, config = err02_setup

    ctl_url = f"http://localhost:{config.control_port}"
    ws_url = f"ws://localhost:{config.ws_port}?token=test-token&supportedAccessories=APC"

    # Connect and verify initial state
    async with websockets.connect(ws_url) as ws:
        initial = json.loads(await ws.recv())
        assert initial["payload"]["state"]["pin-info"]["water-level-low"] == 0

        # Trigger water level low
        async with aiohttp.ClientSession() as session, session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "water_level_low"},
        ) as resp:
            assert resp.status == 200

        # Should receive state update with water-level-low=1
        updated = json.loads(await ws.recv())
        assert updated["payload"]["state"]["pin-info"]["water-level-low"] == 1


# =============================================================================
# ERR-03: Water level critical
# =============================================================================


@pytest.fixture
def err03_config():
    """Configuration for ERR-03 test."""
    return Config(
        ws_port=PORT_WS + 30,
        control_port=PORT_CTL + 30,
        time_scale=60.0,
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def err03_setup(err03_config):
    """Setup for ERR-03 test."""
    sim = AnovaSimulator(config=err03_config)
    await sim.start()

    control = ControlAPI(err03_config, sim)
    await control.start()

    yield sim, control, err03_config

    await control.stop()
    await sim.stop()


@pytest.mark.asyncio
async def test_err03_water_level_critical_stops_cooking(err03_setup):
    """ERR-03: Water level critical stops cooking."""
    sim, control, config = err03_setup

    ctl_url = f"http://localhost:{config.control_port}"

    # Set state to COOKING
    sim.state.job_status.state = DeviceState.COOKING
    sim.state.job.target_temperature = 65.0

    # Trigger water level critical
    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "water_level_critical"},
    ) as resp:
        assert resp.status == 200

    # Verify cooking stopped
    assert sim.state.job_status.state == DeviceState.IDLE
    assert sim.state.pin_info.water_level_critical == 1
    assert sim.state.pin_info.device_safe == 0


# =============================================================================
# ERR-04: Network latency
# =============================================================================


@pytest.mark.asyncio
async def test_err04_network_latency(error_setup):
    """ERR-04: Network latency can be configured."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    # Trigger network latency
    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "network_latency", "latency_ms": 500},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["latency_ms"] == 500

    # Verify latency is set
    assert control.error_simulator.get_latency() == 0.5


# =============================================================================
# ERR-05: Intermittent failures
# =============================================================================


@pytest.mark.asyncio
async def test_err05_intermittent_failures(error_setup):
    """ERR-05: Intermittent failures can be configured."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    # Trigger intermittent failures with 50% rate
    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "intermittent_failure", "failure_rate": 0.5},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["failure_rate"] == 0.5

    # Verify some commands would fail (statistical test)
    failures = sum(control.error_simulator.should_fail_command() for _ in range(100))
    # With 50% rate, expect roughly 50 failures (allow 20-80 range)
    assert 20 < failures < 80


# =============================================================================
# ADDITIONAL TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_errors_endpoint(error_setup):
    """GET /errors returns active errors."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    # Trigger some errors
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "water_level_low"},
        )
        await session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "motor_stuck"},
        )

        # Get errors
        async with session.get(f"{ctl_url}/errors") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "water_level_low" in data["active_errors"]
            assert "motor_stuck" in data["active_errors"]


@pytest.mark.asyncio
async def test_clear_error_endpoint(error_setup):
    """POST /clear-error clears an error."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    async with aiohttp.ClientSession() as session:
        # Trigger error
        await session.post(
            f"{ctl_url}/trigger-error",
            json={"error_type": "water_level_low"},
        )
        assert control.error_simulator.is_error_active(ErrorType.WATER_LEVEL_LOW)

        # Clear error
        async with session.post(
            f"{ctl_url}/clear-error",
            json={"error_type": "water_level_low"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "cleared"

        assert not control.error_simulator.is_error_active(ErrorType.WATER_LEVEL_LOW)


@pytest.mark.asyncio
async def test_invalid_error_type(error_setup):
    """Invalid error type returns 400."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "invalid_error"},
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "INVALID_ERROR_TYPE"


@pytest.mark.asyncio
async def test_motor_stuck_error(error_setup):
    """Motor stuck error sets pin-info and stops RPM."""
    sim, control, config = error_setup

    ctl_url = f"http://localhost:{config.control_port}"

    # Set some RPM
    sim.state.motor_info.rpm = 1200

    # Trigger motor stuck
    async with aiohttp.ClientSession() as session, session.post(
        f"{ctl_url}/trigger-error",
        json={"error_type": "motor_stuck"},
    ) as resp:
        assert resp.status == 200

    # Verify state
    assert sim.state.pin_info.motor_stuck == 1
    assert sim.state.motor_info.rpm == 0
