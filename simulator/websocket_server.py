"""
WebSocket server for the Anova Simulator.

Implements the real Anova Cloud API WebSocket protocol at wss://devices.anovaculinary.io

Features:
- Token-based authentication on connection
- Command routing to handlers
- State event broadcasting
- Connection lifecycle management

Reference: docs/SIMULATOR-SPECIFICATION.md Section 3
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Callable, Any
from urllib.parse import urlparse, parse_qs
import websockets
from websockets.asyncio.server import serve, ServerConnection

from .config import Config
from .types import CookerState, DeviceState
from .messages import (
    parse_command,
    build_success_response,
    build_error_response,
    build_event_apc_state,
    ErrorCode,
    CMD_APC_START,
    CMD_APC_STOP,
    CMD_APC_SET_TARGET_TEMP,
    CMD_APC_SET_TIMER,
)

logger = logging.getLogger(__name__)


class WebSocketServer:
    """
    Anova Simulator WebSocket Server.

    Handles:
    - Client connections with token validation
    - Command routing and response
    - State event broadcasting

    Reference: SIMULATOR-SPECIFICATION.md Section 3.1
    """

    def __init__(self, config: Config, state: CookerState):
        """
        Initialize WebSocket server.

        Args:
            config: Simulator configuration
            state: Shared cooker state (mutable)
        """
        self.config = config
        self.state = state
        self.clients: Set[ServerConnection] = set()
        self.server = None
        self._running = False
        self._broadcast_task: Optional[asyncio.Task] = None

        # Command handlers (will be set by device module)
        self._command_handlers: Dict[str, Callable] = {}

        # Message history for debugging
        self.message_history: list = []
        self._max_history = 1000

    def register_handler(self, command: str, handler: Callable):
        """Register a command handler."""
        self._command_handlers[command] = handler

    async def start(self, host: str = "localhost"):
        """
        Start the WebSocket server.

        Args:
            host: Host to bind to
        """
        self.server = await serve(
            self._handle_connection,
            host,
            self.config.ws_port,
            process_request=self._process_request,
        )
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(f"WebSocket server started on ws://{host}:{self.config.ws_port}")

    async def stop(self):
        """Stop the WebSocket server."""
        self._running = False

        # Cancel broadcast task
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all client connections
        for client in list(self.clients):
            await client.close(1001, "Server shutting down")

        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("WebSocket server stopped")

    async def _process_request(self, connection, request):
        """
        Process incoming HTTP request before WebSocket upgrade.

        Validates:
        - Token is present in query string
        - Token is valid

        Args:
            connection: Server connection object
            request: HTTP request object

        Returns None to accept connection, or Response to reject.
        """
        from websockets.http11 import Response

        # Parse query parameters from path
        path = request.path
        parsed = urlparse(path)
        params = parse_qs(parsed.query)

        # Check for token
        token_list = params.get("token", [])
        if not token_list:
            logger.warning("Connection rejected: missing token")
            return Response(401, "Unauthorized", websockets.Headers([("Content-Type", "text/plain")]))

        token = token_list[0]

        # Validate token
        if not self._validate_token(token):
            logger.warning("Connection rejected: invalid token")
            return Response(401, "Unauthorized", websockets.Headers([("Content-Type", "text/plain")]))

        # Check supportedAccessories
        accessories = params.get("supportedAccessories", ["APC"])
        if "APC" not in accessories[0]:
            logger.warning("Connection rejected: APC not in supportedAccessories")
            return Response(400, "Bad Request", websockets.Headers([("Content-Type", "text/plain")]))

        # Accept connection
        return None

    def _validate_token(self, token: str) -> bool:
        """
        Validate authentication token.

        Args:
            token: Token from query string

        Returns:
            True if valid, False otherwise
        """
        # Check against valid test tokens
        if token in self.config.valid_tokens:
            return True

        # Check if it's an expired token
        if token in self.config.expired_tokens:
            return False

        # For production-like behavior, accept tokens starting with expected prefix
        # In test mode, only accept configured tokens
        return False

    async def _handle_connection(self, websocket: ServerConnection):
        """
        Handle a WebSocket connection.

        Lifecycle:
        1. Add to clients set
        2. Send initial state
        3. Process messages until disconnect
        4. Remove from clients set
        """
        self.clients.add(websocket)
        client_id = id(websocket)
        logger.info(f"Client {client_id} connected")

        try:
            # Send initial state
            await self._send_state(websocket)

            # Process messages
            async for message in websocket:
                await self._handle_message(websocket, message)

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Client {client_id} disconnected: {e.code} {e.reason}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client {client_id} removed")

    async def _handle_message(self, websocket: ServerConnection, raw_message: str):
        """
        Handle an incoming WebSocket message.

        Parses the message, routes to appropriate handler, sends response.
        """
        # Record message
        self._record_message("inbound", raw_message)

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
            response = build_error_response(
                "unknown",
                ErrorCode.INVALID_PAYLOAD,
                f"Invalid JSON: {e}",
            )
            await self._send_message(websocket, response)
            return

        try:
            command, request_id, payload = parse_command(message)
        except ValueError as e:
            logger.warning(f"Invalid command format: {e}")
            response = build_error_response(
                message.get("requestId", "unknown"),
                ErrorCode.INVALID_COMMAND,
                str(e),
            )
            await self._send_message(websocket, response)
            return

        # Route to handler
        handler = self._command_handlers.get(command)
        if handler:
            try:
                response = await handler(request_id, payload)
                await self._send_message(websocket, response)
                # Broadcast state update to all clients
                await self._broadcast_state()
            except Exception as e:
                logger.error(f"Handler error for {command}: {e}")
                response = build_error_response(
                    request_id,
                    ErrorCode.INVALID_PAYLOAD,
                    str(e),
                )
                await self._send_message(websocket, response)
        else:
            logger.warning(f"No handler for command: {command}")
            response = build_error_response(
                request_id,
                ErrorCode.INVALID_COMMAND,
                f"Unknown command: {command}",
            )
            await self._send_message(websocket, response)

    async def _send_message(self, websocket: ServerConnection, message: Dict[str, Any]):
        """Send a message to a specific client."""
        raw = json.dumps(message)
        self._record_message("outbound", raw)
        await websocket.send(raw)

    async def _send_state(self, websocket: ServerConnection):
        """Send current state to a specific client."""
        event = build_event_apc_state(self.state)
        await self._send_message(websocket, event)

    async def _broadcast_state(self):
        """Broadcast current state to all connected clients."""
        if not self.clients:
            return

        event = build_event_apc_state(self.state)
        raw = json.dumps(event)
        self._record_message("outbound", raw)

        # Send to all clients concurrently
        await asyncio.gather(
            *[client.send(raw) for client in self.clients],
            return_exceptions=True,
        )

    async def _broadcast_loop(self):
        """
        Background task to broadcast state periodically.

        Frequency depends on device state:
        - IDLE: every 30 seconds
        - Cooking/Preheating: every 2 seconds
        """
        while self._running:
            try:
                # Determine broadcast interval based on state
                if self.state.job_status.state in (DeviceState.COOKING, DeviceState.PREHEATING):
                    interval = self.config.broadcast_interval_cooking
                else:
                    interval = self.config.broadcast_interval_idle

                # Apply time scale (accelerate for testing)
                actual_interval = interval / self.config.time_scale
                await asyncio.sleep(actual_interval)

                # Broadcast state
                await self._broadcast_state()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    def _record_message(self, direction: str, raw: str):
        """Record a message for debugging."""
        from datetime import datetime

        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": direction,
            "raw": raw[:500],  # Truncate for storage
        }

        # Try to extract command/requestId
        try:
            msg = json.loads(raw)
            entry["command"] = msg.get("command")
            entry["requestId"] = msg.get("requestId")
        except json.JSONDecodeError:
            pass

        self.message_history.append(entry)

        # Limit history size
        if len(self.message_history) > self._max_history:
            self.message_history = self.message_history[-self._max_history:]

    async def disconnect_all(self, code: int = 1006, reason: str = "Device offline"):
        """Disconnect all clients (for offline simulation)."""
        for client in list(self.clients):
            try:
                await client.close(code, reason)
            except Exception:
                pass
        self.clients.clear()
