"""
Message type definitions and builders for the Anova Simulator.

Defines all WebSocket message types and provides builder functions
to create properly formatted messages.

Reference: docs/SIMULATOR-SPECIFICATION.md Section 3
"""

from typing import Any

from .types import CookerState

# ==============================================================================
# COMMAND TYPES (Client → Server)
# ==============================================================================

CMD_APC_START = "CMD_APC_START"
CMD_APC_STOP = "CMD_APC_STOP"
CMD_APC_SET_TARGET_TEMP = "CMD_APC_SET_TARGET_TEMP"
CMD_APC_SET_TIMER = "CMD_APC_SET_TIMER"

# All valid command types
VALID_COMMANDS = {
    CMD_APC_START,
    CMD_APC_STOP,
    CMD_APC_SET_TARGET_TEMP,
    CMD_APC_SET_TIMER,
}


# ==============================================================================
# EVENT TYPES (Server → Client)
# ==============================================================================

EVENT_APC_STATE = "EVENT_APC_STATE"
EVENT_APC_WIFI_LIST = "EVENT_APC_WIFI_LIST"

# Response type for command acknowledgments
RESPONSE = "RESPONSE"


# ==============================================================================
# ERROR CODES
# ==============================================================================

class ErrorCode:
    """Error codes returned in RESPONSE messages."""
    DEVICE_BUSY = "DEVICE_BUSY"
    NO_ACTIVE_COOK = "NO_ACTIVE_COOK"
    INVALID_TEMPERATURE = "INVALID_TEMPERATURE"
    INVALID_TIMER = "INVALID_TIMER"
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    AUTH_FAILED = "AUTH_FAILED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    WATER_LEVEL_CRITICAL = "WATER_LEVEL_CRITICAL"
    WATER_LEVEL_LOW = "WATER_LEVEL_LOW"
    HEATER_OVERTEMP = "HEATER_OVERTEMP"
    TRIAC_OVERTEMP = "TRIAC_OVERTEMP"
    WATER_LEAK = "WATER_LEAK"
    MOTOR_STUCK = "MOTOR_STUCK"


# ==============================================================================
# MESSAGE BUILDERS
# ==============================================================================

def build_response(
    request_id: str,
    status: str = "ok",
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """
    Build a RESPONSE message.

    Args:
        request_id: The requestId from the original command
        status: "ok" for success, "error" for failure
        error_code: Error code if status is "error"
        error_message: Human-readable error message

    Returns:
        RESPONSE message dict

    Reference: SIMULATOR-SPECIFICATION.md Section 3.3.1
    """
    payload: dict[str, Any] = {"status": status}

    if status == "error":
        if error_code:
            payload["code"] = error_code
        if error_message:
            payload["message"] = error_message

    return {
        "command": RESPONSE,
        "requestId": request_id,
        "payload": payload,
    }


def build_success_response(request_id: str) -> dict[str, Any]:
    """Build a successful RESPONSE message."""
    return build_response(request_id, status="ok")


def build_error_response(
    request_id: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    """Build an error RESPONSE message."""
    return build_response(
        request_id,
        status="error",
        error_code=error_code,
        error_message=message,
    )


def build_event_apc_state(state: CookerState) -> dict[str, Any]:
    """
    Build an EVENT_APC_STATE message.

    Args:
        state: Current cooker state

    Returns:
        EVENT_APC_STATE message dict

    Reference: SIMULATOR-SPECIFICATION.md Section 3.4.1
    """
    return {
        "command": EVENT_APC_STATE,
        "payload": state.to_event_payload(),
    }


# ==============================================================================
# MESSAGE PARSING
# ==============================================================================

def parse_command(message: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """
    Parse an incoming command message.

    Args:
        message: Raw message dict from WebSocket

    Returns:
        Tuple of (command_type, request_id, payload)

    Raises:
        ValueError: If message format is invalid
    """
    if "command" not in message:
        raise ValueError("Missing 'command' field")

    command = message["command"]

    if command not in VALID_COMMANDS:
        raise ValueError(f"Unknown command: {command}")

    if "requestId" not in message:
        raise ValueError("Missing 'requestId' field")

    if "payload" not in message:
        raise ValueError("Missing 'payload' field")

    return command, message["requestId"], message["payload"]


def validate_start_payload(payload: dict[str, Any]) -> tuple[str, float, str, int]:
    """
    Validate CMD_APC_START payload.

    Args:
        payload: Command payload

    Returns:
        Tuple of (cooker_id, target_temp, unit, timer)

    Raises:
        ValueError: If payload is invalid
    """
    required = ["cookerId", "targetTemperature", "unit", "timer"]
    for field in required:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    cooker_id = payload["cookerId"]
    target_temp = float(payload["targetTemperature"])
    unit = payload["unit"]
    timer = int(payload["timer"])

    return cooker_id, target_temp, unit, timer


def validate_stop_payload(payload: dict[str, Any]) -> str:
    """
    Validate CMD_APC_STOP payload.

    Returns:
        cooker_id
    """
    if "cookerId" not in payload:
        raise ValueError("Missing required field: cookerId")
    return payload["cookerId"]


def validate_set_temp_payload(payload: dict[str, Any]) -> tuple[str, float, str]:
    """
    Validate CMD_APC_SET_TARGET_TEMP payload.

    Returns:
        Tuple of (cooker_id, target_temp, unit)
    """
    required = ["cookerId", "targetTemperature", "unit"]
    for field in required:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    return payload["cookerId"], float(payload["targetTemperature"]), payload["unit"]


def validate_set_timer_payload(payload: dict[str, Any]) -> tuple[str, int]:
    """
    Validate CMD_APC_SET_TIMER payload.

    Returns:
        Tuple of (cooker_id, timer_seconds)
    """
    required = ["cookerId", "timer"]
    for field in required:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    return payload["cookerId"], int(payload["timer"])
