"""
Shared pytest fixtures for simulator tests.

Provides reusable fixtures for:
- Simulator instances with various configurations
- Control API and Firebase mock
- WebSocket connections
- Port management for test isolation
- State fixtures for testing

Usage:
    @pytest.mark.asyncio
    async def test_something(simulator, ws_client):
        # simulator is running AnovaSimulator instance
        # ws_client is connected WebSocket
        pass
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import websockets

from simulator.config import Config
from simulator.control_api import ControlAPI
from simulator.firebase_mock import FirebaseMock
from simulator.server import AnovaSimulator
from simulator.types import CookerState, DeviceState, SimulatorConfig

# =============================================================================
# PORT MANAGEMENT
# =============================================================================


class PortManager:
    """Manages port allocation for test isolation."""

    _base_port = 19000
    _port_offset = 0

    @classmethod
    def get_ports(cls) -> tuple:
        """Get unique ports for WS, control, and firebase."""
        ws_port = cls._base_port + cls._port_offset
        ctl_port = ws_port + 1
        fb_port = ws_port + 2
        cls._port_offset += 10
        return ws_port, ctl_port, fb_port


@pytest.fixture
def unique_ports() -> tuple:
    """Get unique ports for a test."""
    return PortManager.get_ports()


# =============================================================================
# CONFIGURATION FIXTURES
# =============================================================================


@pytest.fixture
def config() -> Config:
    """Default test configuration."""
    return Config(
        ws_port=8765,
        firebase_port=8764,
        control_port=8766,
        time_scale=60.0,  # Accelerated for tests
        ambient_temp=22.0,
        heating_rate=1.0,
        cooker_id="anova test-0000000000",
    )


@pytest.fixture
def simulator_config(unique_ports) -> Config:
    """Standard configuration for simulator tests with unique ports."""
    ws_port, ctl_port, fb_port = unique_ports
    return Config(
        ws_port=ws_port,
        control_port=ctl_port,
        firebase_port=fb_port,
        time_scale=60.0,
        valid_tokens=["test-token"],
        firebase_credentials={"test@example.com": "testpassword123"},
    )


@pytest.fixture
def fast_config(unique_ports) -> Config:
    """Configuration with accelerated physics for fast tests."""
    ws_port, ctl_port, fb_port = unique_ports
    return Config(
        ws_port=ws_port,
        control_port=ctl_port,
        firebase_port=fb_port,
        time_scale=600.0,  # 10x faster
        heating_rate=120.0,  # Fast heating
        valid_tokens=["test-token"],
    )


@pytest.fixture
def legacy_simulator_config() -> SimulatorConfig:
    """SimulatorConfig for type tests (legacy support)."""
    return SimulatorConfig(
        ws_port=8765,
        time_scale=60.0,
        cooker_id="anova test-0000000000",
    )


# =============================================================================
# STATE FIXTURES
# =============================================================================


@pytest.fixture
def idle_state() -> CookerState:
    """Cooker in idle state."""
    return CookerState(
        cooker_id="anova test-0000000000",
    )


@pytest.fixture
def cooking_state() -> CookerState:
    """Cooker in cooking state."""
    state = CookerState(
        cooker_id="anova test-0000000000",
    )
    state.job_status.state = DeviceState.COOKING
    state.job.target_temperature = 65.0
    state.job.cook_time_seconds = 5400
    state.job_status.cook_time_remaining = 2700
    state.temperature_info.water_temperature = 65.0
    state.heater_control.duty_cycle = 15.0
    state.motor_control.duty_cycle = 100.0
    state.motor_info.rpm = 1200
    return state


@pytest.fixture
def preheating_state() -> CookerState:
    """Cooker in preheating state."""
    state = CookerState(
        cooker_id="anova test-0000000000",
    )
    state.job_status.state = DeviceState.PREHEATING
    state.job.target_temperature = 65.0
    state.job.cook_time_seconds = 5400
    state.job_status.cook_time_remaining = 5400
    state.temperature_info.water_temperature = 35.0
    state.heater_control.duty_cycle = 100.0
    state.motor_control.duty_cycle = 100.0
    state.motor_info.rpm = 1200
    return state


# =============================================================================
# SIMULATOR FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def simulator(simulator_config) -> AsyncGenerator[AnovaSimulator, None]:
    """
    Running AnovaSimulator instance.

    Example:
        async def test_something(simulator):
            assert simulator.state.job_status.state == DeviceState.IDLE
    """
    sim = AnovaSimulator(config=simulator_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest_asyncio.fixture
async def fast_simulator(fast_config) -> AsyncGenerator[AnovaSimulator, None]:
    """Simulator with accelerated physics for fast tests."""
    sim = AnovaSimulator(config=fast_config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest_asyncio.fixture
async def simulator_with_control(
    simulator_config,
) -> AsyncGenerator[tuple, None]:
    """
    Simulator with Control API running.

    Example:
        async def test_something(simulator_with_control):
            sim, control = simulator_with_control
            # Use sim.state or control API endpoints
    """
    sim = AnovaSimulator(config=simulator_config)
    await sim.start()

    control = ControlAPI(simulator_config, sim)
    await control.start()

    yield sim, control

    await control.stop()
    await sim.stop()


@pytest_asyncio.fixture
async def full_simulator(
    simulator_config,
) -> AsyncGenerator[tuple, None]:
    """
    Full simulator stack: Simulator + Control API + Firebase Mock.

    Example:
        async def test_something(full_simulator):
            sim, control, firebase = full_simulator
    """
    sim = AnovaSimulator(config=simulator_config)
    await sim.start()

    control = ControlAPI(simulator_config, sim)
    await control.start()

    firebase = FirebaseMock(simulator_config)
    await firebase.start()

    yield sim, control, firebase

    await firebase.stop()
    await control.stop()
    await sim.stop()


# =============================================================================
# WEBSOCKET FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def ws_client(simulator, simulator_config) -> AsyncGenerator:
    """
    Connected WebSocket client.

    Example:
        async def test_something(ws_client):
            await ws_client.send(json.dumps({"command": "CMD_APC_START", ...}))
            response = await ws_client.recv()
    """
    url = f"ws://localhost:{simulator_config.ws_port}?token=test-token&supportedAccessories=APC"
    ws = await websockets.connect(url)
    await ws.recv()  # Consume initial state
    yield ws
    await ws.close()


@pytest.fixture
def ws_url(simulator_config) -> str:
    """WebSocket URL for manual connection."""
    return f"ws://localhost:{simulator_config.ws_port}?token=test-token&supportedAccessories=APC"


# =============================================================================
# CONTROL API FIXTURES
# =============================================================================


@pytest.fixture
def control_url(simulator_config) -> str:
    """Control API base URL."""
    return f"http://localhost:{simulator_config.control_port}"


# =============================================================================
# HELPER FIXTURES
# =============================================================================


@pytest.fixture
def start_command():
    """Factory for CMD_APC_START messages."""

    def _make_command(
        temp: float = 65.0,
        timer: int = 3600,
        unit: str = "C",
    ) -> dict:
        from simulator.types import generate_request_id

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

    return _make_command


@pytest.fixture
def stop_command():
    """Factory for CMD_APC_STOP messages."""

    def _make_command() -> dict:
        from simulator.types import generate_request_id

        request_id = generate_request_id()
        return {
            "command": "CMD_APC_STOP",
            "requestId": request_id,
            "payload": {
                "cookerId": "anova sim-0000000000",
            },
        }

    return _make_command
