"""
Custom exception hierarchy for the Anova Server.

All application errors flow through this hierarchy. Never let raw exceptions
reach the client - they should all be caught and mapped to appropriate
HTTP status codes.

Exception hierarchy:
    AnovaServerError (base)
    ├── ValidationError (400)
    └── AnovaAPIError (5xx)
        ├── DeviceOfflineError (503)
        └── AuthenticationError (500)

Reference: CLAUDE.md Section "Code Patterns > 1. Error Handling Pattern"
"""


class AnovaServerError(Exception):
    """
    Base exception for all application errors.

    All custom exceptions should inherit from this base class to allow
    for easy catching of all application-specific errors.
    """
    pass


class ValidationError(AnovaServerError):
    """
    Input validation failed.

    Raised when request data fails validation (type errors, range errors,
    food safety violations, etc.). Maps to HTTP 400 Bad Request.

    Attributes:
        error_code: Machine-readable error code (e.g., "TEMPERATURE_TOO_LOW")
        message: Human-readable explanation of what went wrong

    Example error codes:
        - MISSING_TEMPERATURE
        - TEMPERATURE_TOO_LOW
        - TEMPERATURE_TOO_HIGH
        - POULTRY_TEMP_UNSAFE
        - GROUND_MEAT_TEMP_UNSAFE
        - TIME_TOO_SHORT
        - TIME_TOO_LONG
    """

    def __init__(self, error_code: str, message: str):
        """
        Initialize ValidationError.

        Args:
            error_code: Machine-readable error code (e.g., "TEMPERATURE_TOO_LOW")
            message: Human-readable error message for the user
        """
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class AnovaAPIError(AnovaServerError):
    """
    Error communicating with Anova Cloud API.

    Raised when there's a problem communicating with the Anova Cloud API
    (network errors, authentication failures, device errors, etc.).
    Maps to HTTP 5xx status codes.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code to return (default: 500)
    """

    def __init__(self, message: str, status_code: int = 500):
        """
        Initialize AnovaAPIError.

        Args:
            message: Human-readable error message
            status_code: HTTP status code to return (default: 500)
        """
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DeviceOfflineError(AnovaAPIError):
    """
    Anova device is not reachable.

    Raised when the Anova Precision Cooker is offline or unreachable.
    Maps to HTTP 503 Service Unavailable.

    The client should retry the request after a delay (suggested: 60 seconds).
    """

    def __init__(self, message: str = "Device is offline or unreachable"):
        """
        Initialize DeviceOfflineError.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, status_code=503)


class AuthenticationError(AnovaAPIError):
    """
    Authentication with Anova Cloud API failed.

    Raised when Firebase authentication fails or tokens are invalid.
    Maps to HTTP 500 Internal Server Error (since this is a server config issue,
    not a client problem).

    Common causes:
    - Invalid Anova credentials in environment variables
    - Expired refresh token
    - Firebase API key invalid
    """

    def __init__(self, message: str = "Authentication with Anova Cloud failed"):
        """
        Initialize AuthenticationError.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, status_code=500)


class DeviceBusyError(AnovaAPIError):
    """
    Device is already cooking.

    Raised when attempting to start a cook while the device is already
    running. Maps to HTTP 409 Conflict.
    """

    def __init__(self, message: str = "Device is already cooking"):
        """
        Initialize DeviceBusyError.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, status_code=409)


class NoActiveCookError(AnovaAPIError):
    """
    No active cooking session to stop.

    Raised when attempting to stop a cook when no cook is running.
    Maps to HTTP 409 Conflict (device state violation, not resource not found).
    """

    def __init__(self, message: str = "No active cooking session"):
        """
        Initialize NoActiveCookError.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, status_code=409)
