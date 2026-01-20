"""
Authentication, logging, and request/response middleware.

This module provides:
- API key authentication (constant-time comparison)
- Request/response logging (without exposing secrets)
- Error handling middleware

Security principles:
- Use constant-time comparison to prevent timing attacks
- NEVER log credentials, tokens, or API keys
- Treat all logs as potentially public

Reference: CLAUDE.md Section "Code Patterns > 3. Authentication Pattern"
Reference: CLAUDE.md Section "Code Patterns > 4. Logging Pattern"
"""

import hmac
import logging
import os
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Flask, g, jsonify, request

logger = logging.getLogger(__name__)


# ==============================================================================
# AUTHENTICATION MIDDLEWARE
# ==============================================================================

def require_api_key(f: Callable) -> Callable:
    """
    Decorator to require API key authentication.

    All endpoints except /health require API key authentication.
    Expects: Authorization: Bearer <api_key>

    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    Timing attacks allow attackers to guess API keys character by character by
    measuring how long comparisons take.

    Args:
        f: Route function to protect

    Returns:
        Decorated function that checks API key before executing

    Raises:
        Returns 401 Unauthorized if:
        - Authorization header missing
        - Authorization header format invalid (not "Bearer <token>")
        - API key invalid (doesn't match expected key)

    TODO: Implement from CLAUDE.md lines 360-399
    TODO: Extract Authorization header from request
    TODO: Check header format is "Bearer <token>"
    TODO: Get expected API_KEY from environment (os.getenv('API_KEY'))
    TODO: Use hmac.compare_digest() for constant-time comparison
    TODO: Return 401 with proper error format if auth fails
    TODO: Call wrapped function if auth succeeds

    Example usage:
        @app.route('/start-cook', methods=['POST'])
        @require_api_key
        def start_cook():
            # This function only runs if API key is valid
            pass

    Security notes:
    - MUST use hmac.compare_digest() (not ==) to prevent timing attacks
    - NEVER log the API key or auth header
    - Return same error message for missing/invalid keys (don't leak info)
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        # Get Authorization header
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Missing Authorization header"
            }), 401

        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid Authorization header format. Expected: Bearer <token>"
            }), 401

        provided_key = parts[1]

        # Get API key from Flask config (preferred) or environment
        from flask import current_app
        expected_key = current_app.config.get('API_KEY') or os.getenv('API_KEY')

        # If no API key configured, allow request (dev mode)
        if not expected_key:
            logger.warning("API_KEY not configured - allowing unauthenticated access")
            return f(*args, **kwargs)

        # Constant-time comparison (prevents timing attacks)
        if not hmac.compare_digest(provided_key, expected_key):
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid API key"
            }), 401

        # Authentication successful
        return f(*args, **kwargs)

    return decorated_function


# ==============================================================================
# LOGGING MIDDLEWARE
# ==============================================================================

def setup_request_logging(app: Flask) -> None:
    """
    Configure request/response logging middleware.

    Logs:
    - Request: method, path, remote address
    - Response: status code, duration

    Does NOT log (security risk):
    - Request headers (may contain Authorization)
    - Request body (may contain credentials)
    - Response body (may contain tokens)

    Args:
        app: Flask application instance

    Example log output:
        INFO: POST /start-cook from 192.168.1.100
        INFO: POST /start-cook → 200 (0.234s)

    Security notes:
    - Do NOT log request.headers (contains Authorization)
    - Do NOT log request.json (may contain credentials)
    - Do NOT log response body (may contain tokens)
    - Only log: method, path, remote_addr, status_code, duration
    """
    @app.before_request
    def before_request():
        """Log incoming request and record start time."""
        g.start_time = time.time()
        # Log request safely (no sensitive data)
        logger.info(
            f"{request.method} {request.path} "
            f"from {request.remote_addr}"
        )

    @app.after_request
    def after_request(response):
        """Log response with duration."""
        # Calculate request duration
        duration = time.time() - g.start_time

        # Log response safely (no sensitive data)
        logger.info(
            f"{request.method} {request.path} "
            f"→ {response.status_code} "
            f"({duration:.3f}s)"
        )

        return response


def log_request_safely() -> None:
    """
    DEPRECATED: Logging now handled by setup_request_logging().

    Log request without sensitive data.

    Logs only: method, path, remote address
    NEVER logs: headers, body, query parameters (may contain secrets)
    """
    logger.info(
        f"{request.method} {request.path} "
        f"from {request.remote_addr}"
    )


def log_response_safely(status_code: int) -> None:
    """
    DEPRECATED: Logging now handled by setup_request_logging().

    Log response without sensitive data.

    Logs only: status code
    NEVER logs: response body (may contain tokens)

    Args:
        status_code: HTTP status code of the response
    """
    logger.info(f"Response: {status_code}")


# ==============================================================================
# ERROR HANDLING MIDDLEWARE
# ==============================================================================

def register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for custom exceptions.

    Maps custom exceptions to appropriate HTTP responses:
    - ValidationError → 400 Bad Request
    - DeviceOfflineError → 503 Service Unavailable
    - DeviceBusyError → 409 Conflict
    - NoActiveCookError → 404 Not Found
    - AnovaAPIError → 500 Internal Server Error (or custom status_code)
    - AuthenticationError → 500 Internal Server Error

    Args:
        app: Flask application instance

    Error response format:
        {
            "error": "ERROR_CODE",
            "message": "Human-readable message",
            "retry_after": 60  // optional, for 503 errors
        }

    Reference: CLAUDE.md Section "Code Patterns > 1. Error Handling Pattern" (lines 207-233)
    """
    from .exceptions import (
        AnovaAPIError,
        AuthenticationError,
        DeviceBusyError,
        DeviceOfflineError,
        NoActiveCookError,
        ValidationError,
    )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        """Map ValidationError to 400 Bad Request."""
        logger.warning(f"Validation failed: {error.error_code}")
        return jsonify({
            "error": error.error_code,
            "message": error.message
        }), 400

    @app.errorhandler(DeviceOfflineError)
    def handle_device_offline(error: DeviceOfflineError):
        """Map DeviceOfflineError to 503 Service Unavailable."""
        logger.error(f"Device offline: {error.message}")
        return jsonify({
            "error": "DEVICE_OFFLINE",
            "message": error.message,
            "retry_after": 60  # Suggest retry after 60 seconds
        }), 503

    @app.errorhandler(DeviceBusyError)
    def handle_device_busy(error: DeviceBusyError):
        """Map DeviceBusyError to 409 Conflict."""
        logger.warning(f"Device busy: {error.message}")
        return jsonify({
            "error": "DEVICE_BUSY",
            "message": error.message
        }), 409

    @app.errorhandler(NoActiveCookError)
    def handle_no_active_cook(error: NoActiveCookError):
        """Map NoActiveCookError to 409 Conflict."""
        logger.warning(f"No active cook: {error.message}")
        return jsonify({
            "error": "NO_ACTIVE_COOK",
            "message": error.message
        }), 409

    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(error: AuthenticationError):
        """Map AuthenticationError to 500 Internal Server Error."""
        logger.error(f"Authentication failed: {error.message}")
        return jsonify({
            "error": "AUTHENTICATION_ERROR",
            "message": error.message
        }), 500

    @app.errorhandler(AnovaAPIError)
    def handle_anova_api_error(error: AnovaAPIError):
        """Map generic Anova errors to their status code."""
        logger.error(f"Anova API error: {error.message}")
        return jsonify({
            "error": "ANOVA_API_ERROR",
            "message": error.message
        }), error.status_code


# ==============================================================================
# MIDDLEWARE REGISTRATION
# ==============================================================================

def register_middleware(app: Flask) -> None:
    """
    Register all middleware with Flask application.

    Registers:
    - Request/response logging (setup_request_logging)
    - Error handlers (register_error_handlers)

    Note: Authentication (@require_api_key) is applied per-route as decorator.

    Args:
        app: Flask application instance

    Specification: COMP-MW-01 (docs/03-component-architecture.md Section 4.1.3)
    """
    setup_request_logging(app)
    register_error_handlers(app)
    logger.info("Middleware registered: logging + error handlers")


# ==============================================================================
# SECURITY NOTES
# ==============================================================================
# CRITICAL - What NEVER to log:
# ❌ logger.info(f"Auth header: {request.headers.get('Authorization')}")
# ❌ logger.info(f"Password: {os.getenv('ANOVA_PASSWORD')}")
# ❌ logger.info(f"Request body: {request.json}")
# ❌ logger.info(f"Token: {token}")
#
# What's SAFE to log:
# ✅ logger.info(f"Request: {request.method} {request.path}")
# ✅ logger.info(f"Validation failed: {error.error_code}")
# ✅ logger.info(f"Response: {status_code}")
# ✅ logger.error(f"Anova API error: {error.message}")
#
# Reference: CLAUDE.md Section "Anti-Patterns > 1. Never Log Credentials or Tokens"
