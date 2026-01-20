"""
Type definitions for the Anova Simulator.

Contains enums, dataclasses, and type aliases used throughout the simulator.

Reference: docs/SIMULATOR-SPECIFICATION.md Section 4 (State Machine)
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DeviceState(Enum):
    """
    Device states matching the real Anova API.

    Reference: SIMULATOR-SPECIFICATION.md Section 4.1
    """

    IDLE = "IDLE"
    PREHEATING = "PREHEATING"
    COOKING = "COOKING"
    DONE = "DONE"


class TemperatureUnit(Enum):
    """Temperature unit selection."""

    CELSIUS = "C"
    FAHRENHEIT = "F"


class ConnectionStatus(Enum):
    """Network connection status."""

    CONNECTED = "connected-station"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"


@dataclass
class JobInfo:
    """
    Current job (cook) information.

    Maps to: payload.state.job in EVENT_APC_STATE
    """

    id: str = ""
    mode: str = "IDLE"
    target_temperature: float = 0.0
    temperature_unit: TemperatureUnit = TemperatureUnit.CELSIUS
    cook_time_seconds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "target-temperature": self.target_temperature,
            "temperature-unit": self.temperature_unit.value,
            "cook-time-seconds": self.cook_time_seconds,
        }


@dataclass
class JobStatus:
    """
    Current job status.

    Maps to: payload.state.job-status in EVENT_APC_STATE
    """

    state: DeviceState = DeviceState.IDLE
    cook_time_remaining: int = 0
    job_start_systick: int = 0
    state_change_systick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "cook-time-remaining": self.cook_time_remaining,
            "job-start-systick": self.job_start_systick,
            "state-change-systick": self.state_change_systick,
        }


@dataclass
class TemperatureInfo:
    """
    Temperature sensor readings.

    Maps to: payload.state.temperature-info in EVENT_APC_STATE
    """

    water_temperature: float = 22.0
    heater_temperature: float = 22.0
    triac_temperature: int = 25

    def to_dict(self) -> dict[str, Any]:
        return {
            "water-temperature": self.water_temperature,
            "heater-temperature": self.heater_temperature,
            "triac-temperature": self.triac_temperature,
        }


@dataclass
class PinInfo:
    """
    Safety pin information.

    Maps to: payload.state.pin-info in EVENT_APC_STATE
    """

    device_safe: int = 1  # 1=safe, 0=error
    water_leak: int = 0
    water_level_low: int = 0
    water_level_critical: int = 0
    motor_stuck: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "device-safe": self.device_safe,
            "water-leak": self.water_leak,
            "water-level-low": self.water_level_low,
            "water-level-critical": self.water_level_critical,
            "motor-stuck": self.motor_stuck,
        }


@dataclass
class NetworkInfo:
    """
    Network connection information.

    Maps to: payload.state.network-info in EVENT_APC_STATE
    """

    connection_status: str = "connected-station"
    mac_address: str = "AA:BB:CC:DD:EE:FF"
    ssid: str = "SimulatorNetwork"
    security_type: str = "WPA2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection-status": self.connection_status,
            "mac-address": self.mac_address,
            "ssid": self.ssid,
            "security-type": self.security_type,
        }


@dataclass
class HeaterControl:
    """Heater control state."""

    duty_cycle: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"duty-cycle": self.duty_cycle}


@dataclass
class MotorControl:
    """Motor (circulation pump) control state."""

    duty_cycle: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"duty-cycle": self.duty_cycle}


@dataclass
class MotorInfo:
    """Motor information."""

    rpm: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"rpm": self.rpm}


@dataclass
class CookerState:
    """
    Complete cooker state.

    This is the main state container that maps to the full
    EVENT_APC_STATE message structure.

    Reference: SIMULATOR-SPECIFICATION.md Section 3.4.1
    """

    # Device identification
    cooker_id: str = "anova sim-0000000000"
    device_type: str = "pro"
    firmware_version: str = "3.3.01"

    # Operational state
    job: JobInfo = field(default_factory=JobInfo)
    job_status: JobStatus = field(default_factory=JobStatus)

    # Sensor data
    temperature_info: TemperatureInfo = field(default_factory=TemperatureInfo)

    # Control state
    heater_control: HeaterControl = field(default_factory=HeaterControl)
    motor_control: MotorControl = field(default_factory=MotorControl)
    motor_info: MotorInfo = field(default_factory=MotorInfo)

    # Safety
    pin_info: PinInfo = field(default_factory=PinInfo)

    # Network
    network_info: NetworkInfo = field(default_factory=NetworkInfo)

    # Simulator metadata (not sent to clients)
    online: bool = True
    time_scale: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def state(self) -> DeviceState:
        """Convenience property for current device state."""
        return self.job_status.state

    @property
    def water_temp(self) -> float:
        """Convenience property for current water temperature."""
        return self.temperature_info.water_temperature

    @property
    def target_temp(self) -> float | None:
        """Convenience property for target temperature."""
        if self.job_status.state == DeviceState.IDLE:
            return None
        return self.job.target_temperature

    @property
    def timer_remaining(self) -> int | None:
        """Convenience property for timer remaining in seconds."""
        if self.job_status.state == DeviceState.IDLE:
            return None
        return self.job_status.cook_time_remaining

    def to_event_payload(self) -> dict[str, Any]:
        """
        Convert to EVENT_APC_STATE payload format.

        Returns the full nested structure matching the real API.
        """
        return {
            "cookerId": self.cooker_id,
            "type": self.device_type,
            "state": {
                "audio": {
                    "file-name": "",
                    "volume": 50,
                },
                "cap-touch": {
                    "minus-button": 0,
                    "play-button": 0,
                    "plus-button": 0,
                    "target-temperature-button": 0,
                    "timer-button": 0,
                    "water-temperature-button": 0,
                },
                "firmware-info": {
                    "firmware-version": self.firmware_version,
                    "firmware-update-available": False,
                },
                "heater-control": self.heater_control.to_dict(),
                "job": self.job.to_dict(),
                "job-status": self.job_status.to_dict(),
                "motor-control": self.motor_control.to_dict(),
                "motor-info": self.motor_info.to_dict(),
                "network-info": self.network_info.to_dict(),
                "pin-info": self.pin_info.to_dict(),
                "system-info": {
                    "firmware-version": self.firmware_version,
                    "mcu-temperature": 35,
                    "heap-size": 102400,
                },
                "temperature-info": self.temperature_info.to_dict(),
            },
        }


@dataclass
class SimulatorConfig:
    """
    Simulator configuration.

    Reference: SIMULATOR-SPECIFICATION.md Section 10
    """

    # Server ports
    ws_port: int = 8765
    firebase_port: int = 8764
    control_port: int = 8766

    # Physics parameters
    ambient_temp: float = 22.0
    heating_rate: float = 1.0  # degrees C per minute
    cooling_rate: float = 0.5  # degrees C per minute
    temp_tolerance: float = 0.5  # threshold for "at temperature"
    temp_oscillation: float = 0.2  # random variation when maintaining

    # Timing
    time_scale: float = 1.0  # 1.0 = realtime, 60.0 = 1min/s
    broadcast_interval_idle: float = 30.0  # seconds
    broadcast_interval_cooking: float = 2.0  # seconds

    # Device defaults
    cooker_id: str = "anova sim-0000000000"
    device_type: str = "pro"
    firmware_version: str = "3.3.01"

    # Authentication
    valid_tokens: list = field(default_factory=lambda: ["valid-test-token"])

    # Validation limits (from food safety rules)
    min_temp_celsius: float = 40.0
    max_temp_celsius: float = 100.0
    min_timer_seconds: int = 60  # 1 minute
    max_timer_seconds: int = 359940  # 99h 59m


def generate_request_id() -> str:
    """
    Generate a 22-digit hexadecimal request ID.

    Matches the format used by the real Anova API.
    """
    return secrets.token_hex(11)


def generate_cook_id() -> str:
    """Generate a unique cook ID."""
    return f"cook-{secrets.token_hex(8)}"
