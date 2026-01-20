"""
WebSocket client for Anova Cloud API.

Uses official Anova WebSocket API with Personal Access Tokens.
Implements threading bridge to provide synchronous interface for Flask routes.

Handles:
- WebSocket connection with Personal Access Token
- Automatic device discovery
- Device control (start cook, stop cook, get status)
- Real-time status updates via events
- Thread-safe command/response queuing

API Flow:
1. Connect to WebSocket with Personal Access Token
2. Receive EVENT_APC_WIFI_LIST for device discovery
3. Send commands via WebSocket (CMD_APC_START, CMD_APC_STOP)
4. Receive real-time status updates via events
5. Cache status for instant retrieval

Reference: Official Anova WebSocket API documentation
Reference: https://github.com/anova-culinary/developer-project-wifi
Reference: docs/03-component-architecture.md Section 4.3
"""

import asyncio
import json
import logging
import queue
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

import websockets

from .config import Config
from .exceptions import (
    AnovaAPIError,
    AuthenticationError,
    DeviceBusyError,
    DeviceOfflineError,
    NoActiveCookError,
)

logger = logging.getLogger(__name__)


class AnovaWebSocketClient:
    """
    WebSocket client for Anova WiFi devices.

    Uses official Anova WebSocket API with Personal Access Tokens.
    Runs WebSocket connection in background thread to bridge with synchronous Flask.

    Architecture:
    - Background thread runs async event loop
    - WebSocket connection maintained in background
    - Commands sent via thread-safe queue
    - Responses received via another queue
    - Device status cached and updated in real-time

    Attributes:
        config: Configuration with Personal Access Token
        token: Personal Access Token for authentication
        websocket: WebSocket connection (in background thread)
        event_loop: Async event loop (in background thread)
        background_thread: Thread running the event loop
        command_queue: Queue for sending commands to background thread
        response_queue: Queue for receiving responses from background thread
        devices: Dictionary of discovered devices {cookerId: device_info}
        device_status: Cached device status {cookerId: status}
        selected_device: Currently selected device cookerId
        connected: Flag indicating WebSocket connection status

    Example usage:
        config = Config.from_env()
        client = AnovaWebSocketClient(config)
        # Wait for connection and device discovery
        time.sleep(2)
        # Use synchronous API
        client.start_cook(temperature_c=65.0, time_minutes=90)
        status = client.get_status()
        client.stop_cook()

    Reference: Migration plan Section "Component Rewrites > 1. server/anova_client.py"
    """

    # Connection timeout
    CONNECTION_TIMEOUT = 30

    # Command timeout
    COMMAND_TIMEOUT = 10

    def __init__(self, config: Config):
        """
        Initialize WebSocket client and start background thread.

        Args:
            config: Configuration with PERSONAL_ACCESS_TOKEN

        Raises:
            AuthenticationError: If connection fails

        Reference: Migration plan threading bridge pattern
        """
        self.config = config
        self.token = config.PERSONAL_ACCESS_TOKEN
        self.websocket_url = config.ANOVA_WEBSOCKET_URL

        # Threading infrastructure
        self.event_loop: asyncio.AbstractEventLoop | None = None
        self.background_thread: threading.Thread | None = None
        self.websocket: websockets.WebSocketClientProtocol | None = None

        # Connection state
        self.connected = threading.Event()
        self.connection_error: Exception | None = None

        # Thread-safe queues for communication
        self.command_queue: queue.Queue = queue.Queue()
        # CRITICAL FIX: Use per-request queues instead of single response_queue
        # This prevents response mis-matching when multiple commands are in flight
        self.pending_requests: dict[str, queue.Queue] = {}
        self.pending_lock = threading.Lock()

        # Device state cache (updated by event stream)
        self.devices: dict[str, dict[str, Any]] = {}
        self.device_status: dict[str, dict[str, Any]] = {}
        self.selected_device: str | None = None

        # Locks for thread-safe access
        self.status_lock = threading.Lock()
        self.devices_lock = threading.Lock()  # CRITICAL FIX: Protect devices dict

        # Shutdown flag for graceful cleanup
        self.shutdown_requested = threading.Event()

        # Start background thread
        self._start_background_thread()

        # Wait for initial connection (with timeout)
        if not self.connected.wait(timeout=self.CONNECTION_TIMEOUT):
            error_msg = "WebSocket connection timeout"
            if self.connection_error:
                error_msg = f"WebSocket connection failed: {self.connection_error}"
            raise AuthenticationError(error_msg)

        logger.info("AnovaWebSocketClient initialized successfully")

    def _start_background_thread(self):
        """Start background thread running async event loop."""
        self.background_thread = threading.Thread(
            target=self._run_event_loop, daemon=True, name="AnovaWebSocketThread"
        )
        self.background_thread.start()
        logger.debug("Background WebSocket thread started")

    def _run_event_loop(self):
        """Run async event loop in background thread."""
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)

        try:
            self.event_loop.run_until_complete(self._websocket_handler())
        except Exception as e:
            logger.error(f"WebSocket event loop error: {e}")
            self.connection_error = e
            self.connected.set()  # Unblock init even on error
        finally:
            self.event_loop.close()
            logger.debug("WebSocket event loop closed")

    async def _websocket_handler(self):
        """Main WebSocket connection handler with auto-reconnect."""
        url = f"{self.websocket_url}?token={self.token}&supportedAccessories=APC"

        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                logger.info(
                    f"Connecting to Anova WebSocket (attempt {retry_count + 1}/{max_retries})..."
                )
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as websocket:
                    self.websocket = websocket
                    self.connected.set()  # Signal successful connection
                    logger.info("WebSocket connected successfully")

                    # Start concurrent tasks for send and receive
                    receive_task = asyncio.create_task(self._receive_messages())
                    send_task = asyncio.create_task(self._send_commands())

                    # Wait for both tasks (runs until disconnect)
                    await asyncio.gather(receive_task, send_task)

            except websockets.exceptions.WebSocketException as e:
                retry_count += 1
                logger.error(f"WebSocket connection error: {e}")
                self.connection_error = e

                if retry_count < max_retries:
                    wait_time = 2**retry_count  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached, giving up")
                    self.connected.set()  # Unblock init to raise error
                    raise AuthenticationError(
                        f"Failed to connect after {max_retries} attempts: {e}"
                    ) from e

            except Exception as e:
                logger.error(f"Unexpected error in WebSocket handler: {e}")
                self.connection_error = e
                self.connected.set()
                raise

    async def _receive_messages(self):
        """Receive and process WebSocket messages."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    command = data.get("command", "")

                    logger.debug(f"Received message: {command}")

                    if command == "EVENT_APC_WIFI_LIST":
                        # Device discovery
                        self._handle_device_list(data.get("payload", []))

                    elif command.startswith("EVENT_"):
                        # Status update event
                        self._handle_status_update(data)

                    elif command.startswith("RESPONSE_") or command.startswith("CMD_"):
                        # CRITICAL FIX: Route response to correct caller using requestId
                        request_id = data.get("requestId")
                        if request_id:
                            with self.pending_lock:
                                if request_id in self.pending_requests:
                                    self.pending_requests[request_id].put(data)
                                    logger.debug(
                                        f"Routed response {command} to request {request_id}"
                                    )
                                else:
                                    logger.warning(
                                        f"Received response for unknown request {request_id}"
                                    )
                        else:
                            logger.warning(f"Response missing requestId: {command}")

                    else:
                        logger.debug(f"Unhandled message type: {command}")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")

    async def _send_commands(self):
        """Send commands from queue to WebSocket."""
        try:
            while True:
                # Check queue periodically (non-blocking)
                await asyncio.sleep(0.1)

                try:
                    command = self.command_queue.get_nowait()
                    await self.websocket.send(json.dumps(command))
                    logger.debug(f"Sent command: {command.get('command')}")
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error sending command: {e}")

        except Exception as e:
            logger.error(f"Error in send loop: {e}")

    def _handle_device_list(self, devices: list):
        """
        Handle device discovery message.

        Stores discovered devices and auto-selects first device.

        Args:
            devices: List of device objects from EVENT_APC_WIFI_LIST
        """
        with self.status_lock:
            for device in devices:
                cooker_id = device.get("cookerId")
                if cooker_id:
                    self.devices[cooker_id] = device
                    logger.info(f"Discovered device: {device.get('name')} ({cooker_id})")

                    # Auto-select first device if none selected
                    if self.selected_device is None:
                        self.selected_device = cooker_id
                        logger.info(f"Auto-selected device: {cooker_id}")

                        # Initialize status cache for selected device
                        self.device_status[cooker_id] = {
                            "state": "idle",
                            "currentTemperature": 0,
                            "targetTemperature": None,
                            "timeRemaining": None,
                            "timeElapsed": None,
                        }

    def _handle_status_update(self, data: dict[str, Any]):
        """
        Handle device status update event.

        Updates cached status from real-time events.

        Args:
            data: Event data with status information
        """
        # Extract cookerId from event (structure varies by event type)
        payload = data.get("payload", {})
        cooker_id = payload.get("cookerId")

        if cooker_id and cooker_id in self.devices:
            with self.status_lock:
                # Update cached status
                # Event structure: varies by type, extract relevant fields
                if "state" in payload:
                    self.device_status[cooker_id]["state"] = payload["state"]
                if "currentTemperature" in payload:
                    self.device_status[cooker_id]["currentTemperature"] = payload[
                        "currentTemperature"
                    ]
                if "targetTemperature" in payload:
                    self.device_status[cooker_id]["targetTemperature"] = payload[
                        "targetTemperature"
                    ]
                if "timeRemaining" in payload:
                    self.device_status[cooker_id]["timeRemaining"] = payload["timeRemaining"]
                if "timeElapsed" in payload:
                    self.device_status[cooker_id]["timeElapsed"] = payload["timeElapsed"]

                logger.debug(f"Updated status for {cooker_id}: {self.device_status[cooker_id]}")

    def _map_state(self, state: str) -> str:
        """
        Map device state to standardized state names.

        Args:
            state: State from Anova WebSocket

        Returns:
            Normalized state: "idle", "preheating", "cooking", or "done"
        """
        state_map = {
            "idle": "idle",
            "preheating": "preheating",
            "cooking": "cooking",
            "maintaining": "cooking",  # Maintaining temp = cooking
            "done": "done",
            "stopped": "idle",
            "": "idle",  # Default empty state
        }

        normalized = state.lower() if state else ""
        return state_map.get(normalized, "idle")

    # Public API (synchronous, called from Flask routes)

    def get_status(self) -> dict[str, Any]:
        """
        Get current device status from cache.

        Returns cached status that's updated in real-time by WebSocket events.
        This is instant (no network request needed).

        Returns:
            Dict with current status:
                {
                    "device_online": bool,
                    "state": str,  # idle, preheating, cooking, done
                    "current_temp_celsius": float,
                    "target_temp_celsius": float|None,
                    "time_remaining_minutes": int|None,
                    "time_elapsed_minutes": int|None,
                    "is_running": bool
                }

        Raises:
            DeviceOfflineError: If no device is connected

        Reference: Same API as old REST client for compatibility
        """
        if self.selected_device is None:
            raise DeviceOfflineError("No device connected")

        with self.status_lock:
            # Return cached status (updated by event stream)
            status = self.device_status.get(self.selected_device, {})

            state = self._map_state(status.get("state", "idle"))
            is_running = state in ["preheating", "cooking"]

            # Convert times from seconds to minutes
            time_remaining = status.get("timeRemaining")
            time_elapsed = status.get("timeElapsed")

            return {
                "device_online": True,  # If we have status, device is online
                "state": state,
                "current_temp_celsius": float(status.get("currentTemperature", 0)),
                "target_temp_celsius": float(status["targetTemperature"])
                if status.get("targetTemperature")
                else None,
                "time_remaining_minutes": int(time_remaining // 60) if time_remaining else None,
                "time_elapsed_minutes": int(time_elapsed // 60) if time_elapsed else None,
                "is_running": is_running,
            }

    def start_cook(self, temperature_c: float, time_minutes: int) -> dict[str, Any]:
        """
        Start a cooking session.

        Args:
            temperature_c: Target temperature in Celsius (validated by caller)
            time_minutes: Cook time in minutes (validated by caller)

        Returns:
            Dict with cook start confirmation:
                {
                    "success": bool,
                    "message": str,
                    "cook_id": str,
                    "device_state": str,
                    "target_temp_celsius": float,
                    "time_minutes": int,
                    "estimated_completion": str  # ISO8601 timestamp
                }

        Raises:
            DeviceOfflineError: If device is not connected
            DeviceBusyError: If device is already cooking
            AnovaAPIError: For other API errors or timeout

        Reference: CMD_APC_START from official API
        """
        if self.selected_device is None:
            raise DeviceOfflineError("No device connected")

        # Check if device is already cooking
        status = self.get_status()
        if status["is_running"]:
            raise DeviceBusyError("Device is already cooking. Stop current cook first.")

        # CRITICAL FIX: Get device type with thread-safe access
        with self.devices_lock:
            device_info = self.devices.get(self.selected_device, {})
            device_type = device_info.get("type", "oven_v2")  # Default type

        # Build WebSocket command with unique requestId
        request_id = str(uuid.uuid4())
        command = {
            "command": "CMD_APC_START",
            "requestId": request_id,
            "payload": {
                "cookerId": self.selected_device,
                "type": device_type,
                "targetTemperature": temperature_c,
                "unit": "C",
                "timer": time_minutes * 60,  # Convert to seconds
            },
        }

        # CRITICAL FIX: Create per-request queue for response
        response_queue = queue.Queue()
        with self.pending_lock:
            self.pending_requests[request_id] = response_queue

        try:
            # Send command via queue
            self.command_queue.put(command)
            logger.info(f"Starting cook: {temperature_c}°C for {time_minutes} minutes")

            # Wait for response (with timeout) - we use _ to indicate the response
            # is intentionally unused since we construct our response from inputs
            _ = response_queue.get(timeout=self.COMMAND_TIMEOUT)

            # Generate cook_id from requestId
            cook_id = command["requestId"]

            # Calculate estimated completion
            estimated_completion = datetime.now() + timedelta(minutes=time_minutes)

            return {
                "success": True,
                "message": "Cook started successfully",
                "cook_id": cook_id,
                "device_state": "preheating",
                "target_temp_celsius": temperature_c,
                "time_minutes": time_minutes,
                "estimated_completion": estimated_completion.isoformat() + "Z",
            }

        except queue.Empty:
            logger.error("Start cook command timeout")
            raise AnovaAPIError("Start cook command timeout", 504) from None
        finally:
            # CRITICAL FIX: Clean up pending request queue
            with self.pending_lock:
                self.pending_requests.pop(request_id, None)

    def stop_cook(self) -> dict[str, Any]:
        """
        Stop the current cooking session.

        Returns:
            Dict with stop confirmation:
                {
                    "success": bool,
                    "message": str,
                    "device_state": str,
                    "final_temp_celsius": float | None
                }

        Raises:
            DeviceOfflineError: If device is not connected
            NoActiveCookError: If no cook is active
            AnovaAPIError: For other API errors or timeout

        Reference: CMD_APC_STOP from official API
        """
        if self.selected_device is None:
            raise DeviceOfflineError("No device connected")

        # Check if there's an active cook and capture final temperature
        status = self.get_status()
        if not status["is_running"]:
            raise NoActiveCookError("No active cook to stop")

        # Capture current temperature before stopping
        final_temp = status["current_temp_celsius"]

        # CRITICAL FIX: Get device type with thread-safe access
        with self.devices_lock:
            device_info = self.devices.get(self.selected_device, {})
            device_type = device_info.get("type", "oven_v2")

        # Build WebSocket command with unique requestId
        request_id = str(uuid.uuid4())
        command = {
            "command": "CMD_APC_STOP",
            "requestId": request_id,
            "payload": {"cookerId": self.selected_device, "type": device_type},
        }

        # CRITICAL FIX: Create per-request queue for response
        response_queue = queue.Queue()
        with self.pending_lock:
            self.pending_requests[request_id] = response_queue

        try:
            # Send command via queue
            self.command_queue.put(command)
            logger.info("Stopping cook")

            # Wait for response (with timeout) - we use _ to indicate the response
            # is intentionally unused since we construct our response from inputs
            _ = response_queue.get(timeout=self.COMMAND_TIMEOUT)

            return {
                "success": True,
                "message": "Cook stopped successfully",
                "device_state": "idle",
                "final_temp_celsius": final_temp,
            }

        except queue.Empty:
            logger.error("Stop cook command timeout")
            raise AnovaAPIError("Stop cook command timeout", 504) from None
        finally:
            # CRITICAL FIX: Clean up pending request queue
            with self.pending_lock:
                self.pending_requests.pop(request_id, None)

    def shutdown(self) -> None:
        """
        CRITICAL FIX: Gracefully shutdown WebSocket connection and background thread.

        This method should be called when the Flask app is shutting down to:
        1. Close the WebSocket connection cleanly
        2. Allow the background thread to complete
        3. Clean up resources

        Note: This is registered as an atexit handler in app.py
        """
        logger.info("Shutting down AnovaWebSocketClient")

        # Signal shutdown
        self.shutdown_requested.set()

        # Close WebSocket connection
        if self.websocket and not self.websocket.closed:
            try:
                # Schedule close on the event loop
                if self.event_loop and self.event_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.close(), self.event_loop
                    ).result(timeout=2)
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")

        # Wait for background thread to finish (with timeout)
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(timeout=5)
            if self.background_thread.is_alive():
                logger.warning("Background thread did not stop within timeout")
            else:
                logger.info("Background thread stopped successfully")


# ==============================================================================
# SECURITY NOTES
# ==============================================================================
# CRITICAL - Token handling security:
# ✅ Store token in memory only (never log or persist to disk)
# ✅ Use WebSocket with TLS (wss://)
# ✅ Thread-safe queues prevent race conditions
#
# ❌ NEVER log Personal Access Token
# ❌ NEVER expose token in error messages
# ❌ NEVER send token in command payloads (only in connection URL)
#
# Reference: Migration plan Section "Authentication Changes"
