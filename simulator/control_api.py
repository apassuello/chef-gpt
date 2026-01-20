"""
Test Control API for the Anova Simulator.

Provides HTTP endpoints for test setup and state inspection:
- POST /reset - Reset simulator to initial state
- POST /set-state - Set specific device state
- POST /set-offline - Simulate device going offline
- POST /set-time-scale - Change time acceleration
- POST /trigger-error - Trigger error conditions
- POST /clear-error - Clear error conditions
- GET /state - Get current device state
- GET /messages - Get message history
- GET /errors - Get active errors

Reference: docs/SIMULATOR-SPECIFICATION.md Section 9
"""

import json
import logging
from typing import TYPE_CHECKING

from aiohttp import web

from .config import Config
from .errors import ErrorSimulator, ErrorType
from .types import DeviceState

if TYPE_CHECKING:
    from .server import AnovaSimulator

logger = logging.getLogger(__name__)


class ControlAPI:
    """
    Test Control HTTP API.

    Provides endpoints for test setup, state manipulation, and inspection.
    """

    def __init__(
        self,
        config: Config,
        simulator: "AnovaSimulator",
        error_simulator: ErrorSimulator | None = None,
    ):
        """
        Initialize Control API.

        Args:
            config: Simulator configuration
            simulator: Reference to the simulator instance
            error_simulator: Error simulator (creates new one if None)
        """
        self.config = config
        self.simulator = simulator
        self.error_simulator = error_simulator or ErrorSimulator(simulator=simulator)

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

    async def start(self, host: str = "localhost"):
        """
        Start the Control API server.

        Args:
            host: Host to bind to
        """
        self._app = web.Application()
        self._setup_routes()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, host, self.config.control_port)
        await self._site.start()

        self._running = True
        logger.info(f"Control API started on http://{host}:{self.config.control_port}")

    async def stop(self):
        """Stop the Control API server."""
        self._running = False

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

        logger.info("Control API stopped")

    def _setup_routes(self):
        """Setup HTTP routes."""
        self._app.router.add_post("/reset", self._handle_reset)
        self._app.router.add_post("/set-state", self._handle_set_state)
        self._app.router.add_post("/set-offline", self._handle_set_offline)
        self._app.router.add_post("/set-time-scale", self._handle_set_time_scale)
        self._app.router.add_post("/trigger-error", self._handle_trigger_error)
        self._app.router.add_post("/clear-error", self._handle_clear_error)
        self._app.router.add_get("/state", self._handle_get_state)
        self._app.router.add_get("/messages", self._handle_get_messages)
        self._app.router.add_get("/errors", self._handle_get_errors)
        self._app.router.add_get("/health", self._handle_health)

    async def _handle_reset(self, request: web.Request) -> web.Response:
        """
        Reset simulator to initial state.

        POST /reset

        Returns:
            {"status": "reset", "state": "IDLE"}
        """
        try:
            self.simulator.reset()

            return web.json_response({
                "status": "reset",
                "state": self.simulator.state.job_status.state.value,
                "temperature": self.simulator.state.temperature_info.water_temperature,
            })

        except Exception as e:
            logger.error(f"Reset error: {e}")
            return self._error_response("RESET_FAILED", str(e), 500)

    async def _handle_set_state(self, request: web.Request) -> web.Response:
        """
        Set specific device state.

        POST /set-state
        Body: {
            "state": "COOKING",  // IDLE, PREHEATING, COOKING, DONE
            "temperature": 65.0,
            "target_temperature": 65.0,
            "timer": 3600,
            "timer_remaining": 1800
        }

        All fields are optional. Only provided fields will be updated.
        """
        try:
            data = await request.json()

            # Update state
            if "state" in data:
                state_str = data["state"].upper()
                try:
                    new_state = DeviceState(state_str)
                    self.simulator.state.job_status.state = new_state
                    self.simulator.state.job.mode = new_state.value  # Keep job.mode in sync
                except ValueError:
                    return self._error_response(
                        "INVALID_STATE",
                        f"Invalid state: {state_str}. Must be one of: IDLE, PREHEATING, COOKING, DONE",
                        400,
                    )

            # Update temperature
            if "temperature" in data:
                self.simulator.state.temperature_info.water_temperature = float(
                    data["temperature"]
                )

            # Update target temperature
            if "target_temperature" in data:
                self.simulator.state.job.target_temperature = float(
                    data["target_temperature"]
                )

            # Update timer
            if "timer" in data:
                self.simulator.state.job.cook_time_seconds = int(data["timer"])

            # Update timer remaining
            if "timer_remaining" in data:
                self.simulator.state.job_status.cook_time_remaining = int(
                    data["timer_remaining"]
                )

            # Broadcast state update
            await self.simulator.ws_server._broadcast_state()

            return web.json_response({
                "status": "updated",
                "state": self.simulator.state.job_status.state.value,
                "temperature": self.simulator.state.temperature_info.water_temperature,
                "target_temperature": self.simulator.state.job.target_temperature,
                "timer_remaining": self.simulator.state.job_status.cook_time_remaining,
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Set state error: {e}")
            return self._error_response("SET_STATE_FAILED", str(e), 500)

    async def _handle_set_offline(self, request: web.Request) -> web.Response:
        """
        Simulate device going offline/online.

        POST /set-offline
        Body: {"offline": true}  // or {"offline": false}
        """
        try:
            data = await request.json()
            offline = data.get("offline", True)

            if offline:
                # Disconnect all clients
                await self.simulator.ws_server.disconnect_all(
                    code=1006, reason="Device offline"
                )
                self.simulator.state.online = False
                logger.info("Simulator set to offline mode")
            else:
                self.simulator.state.online = True
                logger.info("Simulator set to online mode")

            return web.json_response({
                "status": "offline" if offline else "online",
                "clients_disconnected": len(self.simulator.ws_server.clients) == 0,
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Set offline error: {e}")
            return self._error_response("SET_OFFLINE_FAILED", str(e), 500)

    async def _handle_set_time_scale(self, request: web.Request) -> web.Response:
        """
        Change time acceleration factor.

        POST /set-time-scale
        Body: {"time_scale": 60.0}
        """
        try:
            data = await request.json()
            time_scale = data.get("time_scale")

            if time_scale is None:
                return self._error_response(
                    "MISSING_TIME_SCALE", "time_scale is required", 400
                )

            time_scale = float(time_scale)
            if time_scale <= 0:
                return self._error_response(
                    "INVALID_TIME_SCALE", "time_scale must be positive", 400
                )

            self.simulator.config.time_scale = time_scale
            logger.info(f"Time scale set to {time_scale}")

            return web.json_response({
                "status": "updated",
                "time_scale": time_scale,
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except ValueError:
            return self._error_response(
                "INVALID_TIME_SCALE", "time_scale must be a number", 400
            )
        except Exception as e:
            logger.error(f"Set time scale error: {e}")
            return self._error_response("SET_TIME_SCALE_FAILED", str(e), 500)

    async def _handle_get_state(self, request: web.Request) -> web.Response:
        """
        Get current device state.

        GET /state

        Returns full state as JSON.
        """
        try:
            state = self.simulator.state

            return web.json_response({
                "cooker_id": state.cooker_id,
                "device_type": state.device_type,
                "firmware_version": state.firmware_version,
                "online": state.online,
                "job": {
                    "id": state.job.id,
                    "mode": state.job.mode,
                    "target_temperature": state.job.target_temperature,
                    "temperature_unit": state.job.temperature_unit.value,
                    "cook_time_seconds": state.job.cook_time_seconds,
                },
                "job_status": {
                    "state": state.job_status.state.value,
                    "cook_time_remaining": state.job_status.cook_time_remaining,
                },
                "temperature_info": {
                    "water_temperature": state.temperature_info.water_temperature,
                    "heater_temperature": state.temperature_info.heater_temperature,
                    "triac_temperature": state.temperature_info.triac_temperature,
                },
                "heater_control": {
                    "duty_cycle": state.heater_control.duty_cycle,
                },
                "motor_control": {
                    "duty_cycle": state.motor_control.duty_cycle,
                },
                "motor_info": {
                    "rpm": state.motor_info.rpm,
                },
                "pin_info": {
                    "device_safe": state.pin_info.device_safe,
                    "water_leak": state.pin_info.water_leak,
                    "water_level_low": state.pin_info.water_level_low,
                    "water_level_critical": state.pin_info.water_level_critical,
                    "motor_stuck": state.pin_info.motor_stuck,
                },
                "network_info": {
                    "connection_status": state.network_info.connection_status,
                    "mac_address": state.network_info.mac_address,
                    "ssid": state.network_info.ssid,
                },
                "time_scale": self.simulator.config.time_scale,
            })

        except Exception as e:
            logger.error(f"Get state error: {e}")
            return self._error_response("GET_STATE_FAILED", str(e), 500)

    async def _handle_get_messages(self, request: web.Request) -> web.Response:
        """
        Get message history.

        GET /messages
        Query params:
            - limit: Max messages to return (default: 100)
            - direction: "inbound", "outbound", or "all" (default: "all")

        Returns list of message records.
        """
        try:
            # Parse query params
            limit = int(request.query.get("limit", "100"))
            direction = request.query.get("direction", "all")

            # Get message history
            messages = self.simulator.ws_server.message_history

            # Filter by direction
            if direction != "all":
                messages = [m for m in messages if m.get("direction") == direction]

            # Apply limit (most recent)
            messages = messages[-limit:]

            return web.json_response({
                "count": len(messages),
                "messages": messages,
            })

        except ValueError:
            return self._error_response("INVALID_LIMIT", "limit must be a number", 400)
        except Exception as e:
            logger.error(f"Get messages error: {e}")
            return self._error_response("GET_MESSAGES_FAILED", str(e), 500)

    async def _handle_trigger_error(self, request: web.Request) -> web.Response:
        """
        Trigger an error condition.

        POST /trigger-error
        Body: {
            "error_type": "device_offline",  // See ErrorType enum
            "duration": 10.0,  // Optional: auto-clear after seconds
            "latency_ms": 1000,  // For network_latency
            "failure_rate": 0.3  // For intermittent_failure
        }

        Valid error_types:
        - device_offline: Disconnect all clients
        - water_level_low: Set water-level-low warning
        - water_level_critical: Set critical warning, stop cooking
        - motor_stuck: Set motor stuck error
        - network_latency: Add delay to responses
        - intermittent_failure: Random command failures
        """
        try:
            data = await request.json()
            error_type_str = data.get("error_type")

            if not error_type_str:
                return self._error_response(
                    "MISSING_ERROR_TYPE", "error_type is required", 400
                )

            # Convert to ErrorType enum
            try:
                error_type = ErrorType(error_type_str)
            except ValueError:
                valid_types = [e.value for e in ErrorType]
                return self._error_response(
                    "INVALID_ERROR_TYPE",
                    f"Invalid error_type. Must be one of: {valid_types}",
                    400,
                )

            # Get optional parameters
            duration = data.get("duration")
            kwargs = {}
            if "latency_ms" in data:
                kwargs["latency_ms"] = int(data["latency_ms"])
            if "failure_rate" in data:
                kwargs["failure_rate"] = float(data["failure_rate"])

            # Trigger the error
            result = await self.error_simulator.trigger_error(
                error_type, duration=duration, **kwargs
            )

            return web.json_response({
                "status": "triggered",
                **result,
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Trigger error failed: {e}")
            return self._error_response("TRIGGER_ERROR_FAILED", str(e), 500)

    async def _handle_clear_error(self, request: web.Request) -> web.Response:
        """
        Clear an error condition.

        POST /clear-error
        Body: {"error_type": "device_offline"}
        """
        try:
            data = await request.json()
            error_type_str = data.get("error_type")

            if not error_type_str:
                return self._error_response(
                    "MISSING_ERROR_TYPE", "error_type is required", 400
                )

            # Convert to ErrorType enum
            try:
                error_type = ErrorType(error_type_str)
            except ValueError:
                valid_types = [e.value for e in ErrorType]
                return self._error_response(
                    "INVALID_ERROR_TYPE",
                    f"Invalid error_type. Must be one of: {valid_types}",
                    400,
                )

            # Clear the error
            result = await self.error_simulator.clear_error(error_type)

            return web.json_response({
                "status": "cleared",
                **result,
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Clear error failed: {e}")
            return self._error_response("CLEAR_ERROR_FAILED", str(e), 500)

    async def _handle_get_errors(self, request: web.Request) -> web.Response:
        """
        Get active errors.

        GET /errors

        Returns list of active error conditions.
        """
        try:
            active_errors = self.error_simulator.get_active_errors()

            errors_info = []
            for error_type in active_errors:
                config = self.error_simulator.get_error_config(error_type)
                info = {
                    "error_type": error_type.value,
                    "duration": config.duration,
                }
                if error_type == ErrorType.NETWORK_LATENCY:
                    info["latency_ms"] = config.latency_ms
                elif error_type == ErrorType.INTERMITTENT_FAILURE:
                    info["failure_rate"] = config.failure_rate
                errors_info.append(info)

            return web.json_response({
                "active_errors": [e.value for e in active_errors],
                "errors": errors_info,
            })

        except Exception as e:
            logger.error(f"Get errors failed: {e}")
            return self._error_response("GET_ERRORS_FAILED", str(e), 500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "service": "control-api",
            "simulator_state": self.simulator.state.job_status.state.value,
            "clients_connected": len(self.simulator.ws_server.clients),
        })

    def _error_response(
        self, error_code: str, message: str, status: int
    ) -> web.Response:
        """Build error response."""
        return web.json_response(
            {
                "error": error_code,
                "message": message,
            },
            status=status,
        )
