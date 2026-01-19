"""
Main entry point for the Anova Simulator.

Starts all simulator components:
- WebSocket server (device communication)
- Firebase mock (authentication)
- Control API (test setup)

Usage:
    python -m simulator.server

    # With custom time scale
    SIM_TIME_SCALE=60 python -m simulator.server

Reference: docs/SIMULATOR-SPECIFICATION.md
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from .config import Config
from .types import CookerState, DeviceState, generate_cook_id
from .websocket_server import WebSocketServer
from .messages import (
    build_success_response,
    build_error_response,
    ErrorCode,
    CMD_APC_START,
    CMD_APC_STOP,
    CMD_APC_SET_TARGET_TEMP,
    CMD_APC_SET_TIMER,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class AnovaSimulator:
    """
    Anova Precision Cooker 3.0 Simulator.

    Provides a complete simulation of the Anova Cloud API for testing.

    Example:
        sim = AnovaSimulator(time_scale=60.0)
        await sim.start()
        # ... run tests ...
        await sim.stop()
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        time_scale: float = 1.0,
        ws_port: int = 8765,
        control_port: int = 8766,
    ):
        """
        Initialize simulator.

        Args:
            config: Configuration (uses defaults if None)
            time_scale: Time acceleration factor (1.0 = realtime)
            ws_port: WebSocket server port
            control_port: Control API port
        """
        if config is not None:
            # Use provided config as-is
            self.config = config
        else:
            # Create default config with overrides
            self.config = Config.load()
            self.config.time_scale = time_scale
            self.config.ws_port = ws_port
            self.config.control_port = control_port

        # Initialize state
        self.state = CookerState(
            cooker_id=self.config.cooker_id,
            device_type=self.config.device_type,
            firmware_version=self.config.firmware_version,
        )
        self.state.temperature_info.water_temperature = self.config.ambient_temp

        # Initialize servers
        self.ws_server = WebSocketServer(self.config, self.state)

        # Register command handlers
        self._register_handlers()

        # Physics task
        self._physics_task: Optional[asyncio.Task] = None
        self._running = False

    def _register_handlers(self):
        """Register command handlers with WebSocket server."""
        self.ws_server.register_handler(CMD_APC_START, self._handle_start)
        self.ws_server.register_handler(CMD_APC_STOP, self._handle_stop)
        self.ws_server.register_handler(CMD_APC_SET_TARGET_TEMP, self._handle_set_temp)
        self.ws_server.register_handler(CMD_APC_SET_TIMER, self._handle_set_timer)

    async def start(self, host: str = "localhost"):
        """Start all simulator components."""
        logger.info(f"Starting Anova Simulator (time_scale={self.config.time_scale})")

        self._running = True

        # Start WebSocket server
        await self.ws_server.start(host)

        # Start physics loop
        self._physics_task = asyncio.create_task(self._physics_loop())

        logger.info("Simulator started")

    async def stop(self):
        """Stop all simulator components."""
        logger.info("Stopping simulator...")
        self._running = False

        # Stop physics
        if self._physics_task:
            self._physics_task.cancel()
            try:
                await self._physics_task
            except asyncio.CancelledError:
                pass

        # Stop WebSocket server
        await self.ws_server.stop()

        logger.info("Simulator stopped")

    def reset(self):
        """Reset simulator to initial state."""
        self.state.job_status.state = DeviceState.IDLE
        self.state.job.target_temperature = 0.0
        self.state.job.cook_time_seconds = 0
        self.state.job_status.cook_time_remaining = 0
        self.state.temperature_info.water_temperature = self.config.ambient_temp
        self.state.heater_control.duty_cycle = 0.0
        self.state.motor_control.duty_cycle = 0.0
        self.state.motor_info.rpm = 0
        self.state.pin_info.device_safe = 1
        self.state.pin_info.water_level_low = 0
        self.state.pin_info.water_level_critical = 0
        logger.info("Simulator reset to initial state")

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    async def _handle_start(self, request_id: str, payload: dict) -> dict:
        """
        Handle CMD_APC_START command.

        Validates parameters and starts cooking session.
        """
        # Check if already cooking
        if self.state.job_status.state in (DeviceState.COOKING, DeviceState.PREHEATING):
            return build_error_response(
                request_id,
                ErrorCode.DEVICE_BUSY,
                "Device is already cooking",
            )

        # Validate required fields
        try:
            target_temp = float(payload.get("targetTemperature", 0))
            timer = int(payload.get("timer", 0))
            unit = payload.get("unit", "C")
        except (TypeError, ValueError) as e:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_PAYLOAD,
                f"Invalid payload: {e}",
            )

        # Convert temperature if needed
        if unit == "F":
            target_temp = (target_temp - 32) * 5 / 9

        # Validate temperature
        if target_temp < self.config.min_temp_celsius:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TEMPERATURE,
                f"Temperature {target_temp}°C is below minimum {self.config.min_temp_celsius}°C",
            )

        if target_temp > self.config.max_temp_celsius:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TEMPERATURE,
                f"Temperature {target_temp}°C is above maximum {self.config.max_temp_celsius}°C",
            )

        # Validate timer
        if timer < self.config.min_timer_seconds:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TIMER,
                f"Timer {timer}s is below minimum {self.config.min_timer_seconds}s",
            )

        if timer > self.config.max_timer_seconds:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TIMER,
                f"Timer {timer}s is above maximum {self.config.max_timer_seconds}s",
            )

        # Start cooking
        self.state.job.id = generate_cook_id()
        self.state.job.mode = "COOK"
        self.state.job.target_temperature = target_temp
        self.state.job.cook_time_seconds = timer
        self.state.job_status.cook_time_remaining = timer
        self.state.job_status.state = DeviceState.PREHEATING
        self.state.heater_control.duty_cycle = 100.0
        self.state.motor_control.duty_cycle = 100.0
        self.state.motor_info.rpm = 1200

        logger.info(f"Started cook: {target_temp}°C for {timer}s")
        return build_success_response(request_id)

    async def _handle_stop(self, request_id: str, payload: dict) -> dict:
        """
        Handle CMD_APC_STOP command.

        Stops current cooking session.
        """
        if self.state.job_status.state == DeviceState.IDLE:
            return build_error_response(
                request_id,
                ErrorCode.NO_ACTIVE_COOK,
                "No active cook to stop",
            )

        # Stop cooking
        self.state.job_status.state = DeviceState.IDLE
        self.state.job.mode = "IDLE"
        self.state.heater_control.duty_cycle = 0.0
        self.state.motor_control.duty_cycle = 0.0
        self.state.motor_info.rpm = 0

        logger.info("Stopped cook")
        return build_success_response(request_id)

    async def _handle_set_temp(self, request_id: str, payload: dict) -> dict:
        """
        Handle CMD_APC_SET_TARGET_TEMP command.

        Updates target temperature.
        """
        try:
            target_temp = float(payload.get("targetTemperature", 0))
            unit = payload.get("unit", "C")
        except (TypeError, ValueError) as e:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_PAYLOAD,
                f"Invalid payload: {e}",
            )

        # Convert temperature if needed
        if unit == "F":
            target_temp = (target_temp - 32) * 5 / 9

        # Validate temperature
        if target_temp < self.config.min_temp_celsius:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TEMPERATURE,
                f"Temperature {target_temp}°C is below minimum {self.config.min_temp_celsius}°C",
            )

        if target_temp > self.config.max_temp_celsius:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TEMPERATURE,
                f"Temperature {target_temp}°C is above maximum {self.config.max_temp_celsius}°C",
            )

        self.state.job.target_temperature = target_temp
        logger.info(f"Set target temperature: {target_temp}°C")
        return build_success_response(request_id)

    async def _handle_set_timer(self, request_id: str, payload: dict) -> dict:
        """
        Handle CMD_APC_SET_TIMER command.

        Updates cook timer.
        """
        try:
            timer = int(payload.get("timer", 0))
        except (TypeError, ValueError) as e:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_PAYLOAD,
                f"Invalid payload: {e}",
            )

        # Validate timer
        if timer < self.config.min_timer_seconds:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TIMER,
                f"Timer {timer}s is below minimum {self.config.min_timer_seconds}s",
            )

        if timer > self.config.max_timer_seconds:
            return build_error_response(
                request_id,
                ErrorCode.INVALID_TIMER,
                f"Timer {timer}s is above maximum {self.config.max_timer_seconds}s",
            )

        self.state.job.cook_time_seconds = timer
        self.state.job_status.cook_time_remaining = timer
        logger.info(f"Set timer: {timer}s")
        return build_success_response(request_id)

    # =========================================================================
    # PHYSICS SIMULATION
    # =========================================================================

    async def _physics_loop(self):
        """
        Background task for physics simulation.

        Updates temperature and timer based on state.
        """
        tick_interval = 1.0  # 1 second ticks
        last_tick = asyncio.get_event_loop().time()

        while self._running:
            try:
                await asyncio.sleep(tick_interval / self.config.time_scale)

                current_time = asyncio.get_event_loop().time()
                dt = (current_time - last_tick) * self.config.time_scale
                last_tick = current_time

                self._update_physics(dt)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Physics error: {e}")

    def _update_physics(self, dt: float):
        """
        Update physics for one time step.

        Args:
            dt: Time delta in seconds (simulated time)
        """
        state = self.state.job_status.state

        if state == DeviceState.PREHEATING:
            self._update_preheating(dt)
        elif state == DeviceState.COOKING:
            self._update_cooking(dt)
        elif state == DeviceState.DONE:
            self._update_done(dt)
        elif state == DeviceState.IDLE:
            self._update_idle(dt)

    def _update_preheating(self, dt: float):
        """Update physics during preheating."""
        # Heat water
        target = self.state.job.target_temperature
        current = self.state.temperature_info.water_temperature
        rate = self.config.heating_rate / 60.0  # Convert to per-second

        new_temp = current + rate * dt
        self.state.temperature_info.water_temperature = min(new_temp, target)

        # Check if reached target
        if new_temp >= target - self.config.temp_tolerance:
            self.state.job_status.state = DeviceState.COOKING
            self.state.temperature_info.water_temperature = target
            logger.info(f"Reached target temperature: {target}°C, starting timer")

    def _update_cooking(self, dt: float):
        """Update physics during cooking."""
        import random

        # Maintain temperature with small oscillation
        target = self.state.job.target_temperature
        oscillation = random.uniform(
            -self.config.temp_oscillation,
            self.config.temp_oscillation,
        )
        self.state.temperature_info.water_temperature = target + oscillation

        # Count down timer
        remaining = self.state.job_status.cook_time_remaining
        new_remaining = max(0, remaining - dt)
        self.state.job_status.cook_time_remaining = int(new_remaining)

        # Check if timer expired
        if new_remaining <= 0:
            self.state.job_status.state = DeviceState.DONE
            self.state.job_status.cook_time_remaining = 0
            logger.info("Cook complete, timer expired")

    def _update_done(self, dt: float):
        """Update physics while done (maintaining temp)."""
        import random

        # Continue maintaining temperature
        target = self.state.job.target_temperature
        oscillation = random.uniform(
            -self.config.temp_oscillation,
            self.config.temp_oscillation,
        )
        self.state.temperature_info.water_temperature = target + oscillation

    def _update_idle(self, dt: float):
        """Update physics while idle (cooling)."""
        current = self.state.temperature_info.water_temperature
        ambient = self.config.ambient_temp

        if current > ambient:
            rate = self.config.cooling_rate / 60.0  # Per second
            new_temp = current - rate * dt
            self.state.temperature_info.water_temperature = max(new_temp, ambient)

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def ws_port(self) -> int:
        """WebSocket server port."""
        return self.config.ws_port

    @property
    def cooker_id(self) -> str:
        """Device cooker ID."""
        return self.state.cooker_id


async def main():
    """Main entry point when run as script."""
    config = Config.load()
    simulator = AnovaSimulator(config=config)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown():
        logger.info("Shutdown signal received")
        asyncio.create_task(simulator.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    # Start simulator
    await simulator.start()

    # Keep running until stopped
    try:
        while simulator._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

    logger.info("Simulator exited")


if __name__ == "__main__":
    asyncio.run(main())
