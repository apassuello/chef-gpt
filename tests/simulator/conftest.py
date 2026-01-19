"""
Pytest fixtures for Anova Simulator tests.

Provides fixtures for:
- Simulator configuration
- Device state
- WebSocket client connections
- Test control API client
"""

import pytest
from simulator.types import CookerState, DeviceState, SimulatorConfig
from simulator.config import Config


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
def simulator_config() -> SimulatorConfig:
    """SimulatorConfig for type tests."""
    return SimulatorConfig(
        ws_port=8765,
        time_scale=60.0,
        cooker_id="anova test-0000000000",
    )


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
