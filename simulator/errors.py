"""
Error simulation for the Anova Simulator.

Implements various error conditions for comprehensive testing:
- Device offline simulation
- Water level warnings (low, critical)
- Motor stuck error
- Network latency injection
- Intermittent failure mode

Reference: docs/SIMULATOR-SPECIFICATION.md Section 8
"""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .server import AnovaSimulator

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can be simulated."""

    DEVICE_OFFLINE = "device_offline"
    WATER_LEVEL_LOW = "water_level_low"
    WATER_LEVEL_CRITICAL = "water_level_critical"
    MOTOR_STUCK = "motor_stuck"
    NETWORK_LATENCY = "network_latency"
    INTERMITTENT_FAILURE = "intermittent_failure"
    HEATER_OVERTEMP = "heater_overtemp"
    TRIAC_OVERTEMP = "triac_overtemp"
    WATER_LEAK = "water_leak"


@dataclass
class ErrorConfig:
    """Configuration for an error simulation."""

    error_type: ErrorType
    enabled: bool = False
    duration: float | None = None  # Auto-clear after duration (seconds)

    # Latency-specific
    latency_ms: int = 0

    # Intermittent-specific
    failure_rate: float = 0.0  # 0.0 to 1.0


@dataclass
class ErrorSimulator:
    """
    Manages error simulation for the Anova Simulator.

    Provides methods to trigger, clear, and check various error conditions.
    """

    simulator: Optional["AnovaSimulator"] = None

    # Active error configurations
    _errors: dict = field(default_factory=dict)

    # Callbacks for when errors are triggered/cleared
    _on_error_triggered: list[Callable] = field(default_factory=list)
    _on_error_cleared: list[Callable] = field(default_factory=list)

    # Tasks for auto-clearing errors
    _clear_tasks: dict = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all error types as disabled
        for error_type in ErrorType:
            self._errors[error_type] = ErrorConfig(error_type=error_type)

    async def trigger_error(
        self,
        error_type: ErrorType,
        duration: float | None = None,
        **kwargs,
    ) -> dict:
        """
        Trigger an error condition.

        Args:
            error_type: Type of error to trigger
            duration: Auto-clear after this many seconds (None = permanent)
            **kwargs: Error-specific parameters

        Returns:
            Status dict with error details
        """
        config = self._errors[error_type]
        config.enabled = True
        config.duration = duration

        # Apply error-specific parameters
        if error_type == ErrorType.NETWORK_LATENCY:
            config.latency_ms = kwargs.get("latency_ms", 1000)
        elif error_type == ErrorType.INTERMITTENT_FAILURE:
            config.failure_rate = kwargs.get("failure_rate", 0.3)

        # Apply the error effect
        await self._apply_error(error_type)

        # Schedule auto-clear if duration specified
        if duration is not None:
            await self._schedule_clear(error_type, duration)

        logger.info(f"Triggered error: {error_type.value}")

        # Notify callbacks
        for callback in self._on_error_triggered:
            try:
                await callback(error_type)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

        return {
            "error_type": error_type.value,
            "enabled": True,
            "duration": duration,
            **kwargs,
        }

    async def clear_error(self, error_type: ErrorType) -> dict:
        """
        Clear an error condition.

        Args:
            error_type: Type of error to clear

        Returns:
            Status dict
        """
        config = self._errors[error_type]
        config.enabled = False
        config.duration = None

        # Cancel any scheduled clear
        if error_type in self._clear_tasks:
            self._clear_tasks[error_type].cancel()
            del self._clear_tasks[error_type]

        # Remove the error effect
        await self._remove_error(error_type)

        logger.info(f"Cleared error: {error_type.value}")

        # Notify callbacks
        for callback in self._on_error_cleared:
            try:
                await callback(error_type)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

        return {
            "error_type": error_type.value,
            "enabled": False,
        }

    def is_error_active(self, error_type: ErrorType) -> bool:
        """Check if an error is currently active."""
        return self._errors[error_type].enabled

    def get_active_errors(self) -> list[ErrorType]:
        """Get list of currently active errors."""
        return [
            error_type
            for error_type, config in self._errors.items()
            if config.enabled
        ]

    def get_error_config(self, error_type: ErrorType) -> ErrorConfig:
        """Get configuration for an error type."""
        return self._errors[error_type]

    def should_fail_command(self) -> bool:
        """Check if intermittent failure should cause command to fail."""
        config = self._errors[ErrorType.INTERMITTENT_FAILURE]
        if not config.enabled:
            return False
        return random.random() < config.failure_rate

    def get_latency(self) -> float:
        """Get current latency in seconds."""
        config = self._errors[ErrorType.NETWORK_LATENCY]
        if not config.enabled:
            return 0.0
        return config.latency_ms / 1000.0

    async def _apply_error(self, error_type: ErrorType):
        """Apply an error effect to the simulator state."""
        if self.simulator is None:
            return

        if error_type == ErrorType.DEVICE_OFFLINE:
            await self.simulator.ws_server.disconnect_all(
                code=1006, reason="Device offline"
            )
            self.simulator.state.online = False

        elif error_type == ErrorType.WATER_LEVEL_LOW:
            self.simulator.state.pin_info.water_level_low = 1
            # Broadcast state update
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.WATER_LEVEL_CRITICAL:
            self.simulator.state.pin_info.water_level_critical = 1
            self.simulator.state.pin_info.device_safe = 0
            # Stop cooking if active
            from .types import DeviceState

            if self.simulator.state.job_status.state in (
                DeviceState.COOKING,
                DeviceState.PREHEATING,
            ):
                self.simulator.state.job_status.state = DeviceState.IDLE
                self.simulator.state.job.mode = "IDLE"
                self.simulator.state.heater_control.duty_cycle = 0.0
                self.simulator.state.motor_control.duty_cycle = 0.0
            # Broadcast state update
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.MOTOR_STUCK:
            self.simulator.state.pin_info.motor_stuck = 1
            self.simulator.state.motor_info.rpm = 0
            # Broadcast state update
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.HEATER_OVERTEMP:
            # Heater overtemperature - stop heating, set flag
            self.simulator.state.temperature_info.heater_temperature = 150.0  # Critical temp
            self.simulator.state.heater_control.duty_cycle = 0.0
            self.simulator.state.pin_info.device_safe = 0
            # Stop cooking if active
            from .types import DeviceState

            if self.simulator.state.job_status.state in (
                DeviceState.COOKING,
                DeviceState.PREHEATING,
            ):
                self.simulator.state.job_status.state = DeviceState.IDLE
                self.simulator.state.job.mode = "IDLE"
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.TRIAC_OVERTEMP:
            # Triac overtemperature - stop heating, set flag
            self.simulator.state.temperature_info.triac_temperature = 100.0  # Critical temp
            self.simulator.state.heater_control.duty_cycle = 0.0
            self.simulator.state.pin_info.device_safe = 0
            # Stop cooking if active
            from .types import DeviceState

            if self.simulator.state.job_status.state in (
                DeviceState.COOKING,
                DeviceState.PREHEATING,
            ):
                self.simulator.state.job_status.state = DeviceState.IDLE
                self.simulator.state.job.mode = "IDLE"
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.WATER_LEAK:
            # Water leak detected - stop cooking immediately
            self.simulator.state.pin_info.water_leak = 1
            self.simulator.state.pin_info.device_safe = 0
            from .types import DeviceState

            if self.simulator.state.job_status.state in (
                DeviceState.COOKING,
                DeviceState.PREHEATING,
            ):
                self.simulator.state.job_status.state = DeviceState.IDLE
                self.simulator.state.job.mode = "IDLE"
                self.simulator.state.heater_control.duty_cycle = 0.0
                self.simulator.state.motor_control.duty_cycle = 0.0
            await self.simulator.ws_server._broadcast_state()

        # NETWORK_LATENCY and INTERMITTENT_FAILURE don't modify state directly

    async def _remove_error(self, error_type: ErrorType):
        """Remove an error effect from the simulator state."""
        if self.simulator is None:
            return

        if error_type == ErrorType.DEVICE_OFFLINE:
            self.simulator.state.online = True

        elif error_type == ErrorType.WATER_LEVEL_LOW:
            self.simulator.state.pin_info.water_level_low = 0
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.WATER_LEVEL_CRITICAL:
            self.simulator.state.pin_info.water_level_critical = 0
            self.simulator.state.pin_info.device_safe = 1
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.MOTOR_STUCK:
            self.simulator.state.pin_info.motor_stuck = 0
            # Restore RPM if cooking
            from .types import DeviceState

            if self.simulator.state.job_status.state in (
                DeviceState.COOKING,
                DeviceState.PREHEATING,
            ):
                self.simulator.state.motor_info.rpm = 1200
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.HEATER_OVERTEMP:
            self.simulator.state.temperature_info.heater_temperature = 65.0  # Normal temp
            self.simulator.state.pin_info.device_safe = 1
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.TRIAC_OVERTEMP:
            self.simulator.state.temperature_info.triac_temperature = 40.0  # Normal temp
            self.simulator.state.pin_info.device_safe = 1
            await self.simulator.ws_server._broadcast_state()

        elif error_type == ErrorType.WATER_LEAK:
            self.simulator.state.pin_info.water_leak = 0
            self.simulator.state.pin_info.device_safe = 1
            await self.simulator.ws_server._broadcast_state()

    async def _schedule_clear(self, error_type: ErrorType, duration: float):
        """Schedule automatic clearing of an error."""
        # Cancel any existing clear task
        if error_type in self._clear_tasks:
            self._clear_tasks[error_type].cancel()

        async def clear_after_delay():
            await asyncio.sleep(duration)
            await self.clear_error(error_type)

        task = asyncio.create_task(clear_after_delay())
        self._clear_tasks[error_type] = task
