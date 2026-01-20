"""
Centralized Anova Cloud API mock responses.

All mock response data in one place for easy maintenance.
Reference: Real Anova API behavior (discovered through testing).

Usage:
    from tests.mocks.anova_responses import DEVICE_STATUS_IDLE, anova_device_url

    responses.add(
        responses.GET,
        anova_device_url("test-device-123", "status"),
        json=DEVICE_STATUS_IDLE,
        status=200
    )
"""

# ==============================================================================
# API URLS
# ==============================================================================

FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
ANOVA_API_BASE = "https://anovaculinary.io/api/v1"


def anova_device_url(device_id: str, endpoint: str = "status") -> str:
    """
    Generate Anova device API URL.

    Args:
        device_id: Device ID (e.g., "test-device-123")
        endpoint: API endpoint (e.g., "status", "start", "stop")

    Returns:
        Full API URL
    """
    return f"{ANOVA_API_BASE}/devices/{device_id}/{endpoint}"


# ==============================================================================
# FIREBASE AUTHENTICATION RESPONSES
# ==============================================================================

FIREBASE_AUTH_SUCCESS = {
    "idToken": "mock-id-token-abc123",
    "refreshToken": "mock-refresh-token-xyz789",
    "expiresIn": "3600",
    "localId": "mock-user-id",
    "email": "test@example.com",
}

FIREBASE_AUTH_INVALID_CREDENTIALS = {
    "error": {
        "code": 400,
        "message": "INVALID_PASSWORD",
        "errors": [{"message": "INVALID_PASSWORD", "domain": "global", "reason": "invalid"}],
    }
}

FIREBASE_TOKEN_REFRESH_SUCCESS = {
    "id_token": "mock-new-id-token-def456",
    "refresh_token": "mock-refresh-token-xyz789",
    "expires_in": "3600",
    "token_type": "Bearer",
    "user_id": "mock-user-id",
}

FIREBASE_TOKEN_EXPIRED = {"error": {"code": 401, "message": "TOKEN_EXPIRED"}}


# ==============================================================================
# DEVICE STATUS RESPONSES
# ==============================================================================

DEVICE_STATUS_IDLE = {
    "online": True,
    "state": "idle",
    "current_temperature": 22.5,
    "target_temperature": None,
    "timer_remaining": None,
    "timer_elapsed": None,
    "device_id": "test-device-123",
    "firmware_version": "1.2.3",
}

DEVICE_STATUS_PREHEATING = {
    "online": True,
    "state": "preheating",
    "current_temperature": 45.0,
    "target_temperature": 65.0,
    "timer_remaining": None,
    "timer_elapsed": None,
    "device_id": "test-device-123",
    "firmware_version": "1.2.3",
}

DEVICE_STATUS_COOKING = {
    "online": True,
    "state": "cooking",
    "current_temperature": 65.0,
    "target_temperature": 65.0,
    "timer_remaining": 45,
    "timer_elapsed": 45,
    "device_id": "test-device-123",
    "firmware_version": "1.2.3",
}

DEVICE_STATUS_COOKING_ALMOST_DONE = {
    "online": True,
    "state": "cooking",
    "current_temperature": 65.0,
    "target_temperature": 65.0,
    "timer_remaining": 5,
    "timer_elapsed": 85,
    "device_id": "test-device-123",
    "firmware_version": "1.2.3",
}

DEVICE_STATUS_DONE = {
    "online": True,
    "state": "done",
    "current_temperature": 65.0,
    "target_temperature": 65.0,
    "timer_remaining": 0,
    "timer_elapsed": 90,
    "device_id": "test-device-123",
    "firmware_version": "1.2.3",
}

DEVICE_STATUS_OFFLINE_404 = {"error": "Device not found or offline", "code": "DEVICE_NOT_FOUND"}

DEVICE_STATUS_OFFLINE_FALSE = {"online": False, "state": "unknown", "device_id": "test-device-123"}


# ==============================================================================
# DEVICE COMMAND RESPONSES
# ==============================================================================

START_COOK_SUCCESS = {
    "success": True,
    "state": "preheating",
    "cook_id": "cook-abc123",
    "device_id": "test-device-123",
    "target_temperature": 65.0,
    "timer_duration": 90,
    "message": "Cook started successfully",
}

START_COOK_ALREADY_COOKING = {
    "error": "Device already cooking",
    "code": "DEVICE_BUSY",
    "current_cook": {"cook_id": "cook-xyz789", "target_temp": 65.0, "time_remaining": 45},
}

START_COOK_DEVICE_OFFLINE = {
    "error": "Device is offline",
    "code": "DEVICE_OFFLINE",
    "message": "Please check device WiFi connection",
}

STOP_COOK_SUCCESS = {
    "success": True,
    "state": "idle",
    "device_id": "test-device-123",
    "final_temperature": 65.0,
    "total_time_elapsed": 85,
    "message": "Cook stopped successfully",
}

STOP_COOK_NOT_COOKING = {
    "error": "No active cook session",
    "code": "NO_ACTIVE_COOK",
    "current_state": "idle",
}


# ==============================================================================
# ERROR RESPONSES
# ==============================================================================

ERROR_UNAUTHORIZED = {
    "error": "Unauthorized",
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired authentication token",
}

ERROR_RATE_LIMITED = {
    "error": "Rate limit exceeded",
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please wait before trying again.",
    "retry_after": 60,
}

ERROR_INTERNAL_SERVER = {
    "error": "Internal server error",
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again later.",
}


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================


def get_device_status_at_temp(
    current_temp: float, target_temp: float, state: str = "preheating"
) -> dict:
    """
    Generate device status at specific temperature.

    Args:
        current_temp: Current water temperature
        target_temp: Target temperature
        state: Device state (preheating, cooking, done)

    Returns:
        Device status dict
    """
    return {
        "online": True,
        "state": state,
        "current_temperature": current_temp,
        "target_temperature": target_temp,
        "timer_remaining": 45 if state == "cooking" else None,
        "timer_elapsed": 45 if state == "cooking" else None,
        "device_id": "test-device-123",
        "firmware_version": "1.2.3",
    }


def get_start_cook_response(target_temp: float, time_minutes: int) -> dict:
    """
    Generate start cook success response.

    Args:
        target_temp: Target temperature
        time_minutes: Cook duration in minutes

    Returns:
        Start cook success response
    """
    return {
        "success": True,
        "state": "preheating",
        "cook_id": "cook-abc123",
        "device_id": "test-device-123",
        "target_temperature": target_temp,
        "timer_duration": time_minutes,
        "message": "Cook started successfully",
    }
