"""
HTTP route handlers for the Anova API.

Defines all endpoints:
- GET /health - Health check (no auth)
- POST /start-cook - Start cooking session (auth required)
- GET /status - Get current cooking status (auth required)
- POST /stop-cook - Stop cooking session (auth required)

All routes (except /health) require API key authentication via Bearer token.

Reference: CLAUDE.md Section "API Endpoints Reference"
Reference: CLAUDE.md Section "Code Patterns > 3. Authentication Pattern"
Reference: docs/05-api-specification.md
"""

import logging
from datetime import UTC
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .anova_client import AnovaClient
from .config import Config
from .middleware import require_api_key
from .validators import validate_start_cook

logger = logging.getLogger(__name__)

# Create Blueprint for API routes
api = Blueprint('api', __name__)


# ==============================================================================
# HEALTH CHECK ENDPOINT
# ==============================================================================

@api.route('/health', methods=['GET'])
def health() -> tuple[dict[str, Any], int]:
    """
    Health check endpoint.

    No authentication required. Used by monitoring systems to check
    if the server is alive and responding.

    Returns:
        JSON response: {"status": "ok", "version": "1.0.0", "timestamp": "ISO8601"}
        HTTP status: 200

    Example:
        GET /health
        Response: {
            "status": "ok",
            "version": "1.0.0",
            "timestamp": "2025-01-11T12:00:00Z"
        }

    Reference: CLAUDE.md Section "API Endpoints Reference > GET /health" (lines 1028-1039)
    Reference: docs/05-api-specification.md lines 278-302
    """
    from datetime import datetime

    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    }), 200


# ==============================================================================
# COOKING CONTROL ENDPOINTS
# ==============================================================================

@api.route('/start-cook', methods=['POST'])
@require_api_key
def start_cook() -> tuple[dict[str, Any], int]:
    """
    Start a cooking session.

    Requires:
    - Authorization: Bearer <api_key> header
    - JSON body with temperature_celsius, time_minutes, optional food_type

    Request body:
        {
            "temperature_celsius": 65.0,
            "time_minutes": 90,
            "food_type": "chicken"  // optional
        }

    Success response (200):
        {
            "status": "started",
            "target_temp_celsius": 65.0,
            "time_minutes": 90,
            "device_id": "abc123"
        }

    Error responses:
    - 400: Validation error (TEMPERATURE_TOO_LOW, POULTRY_TEMP_UNSAFE, etc.)
    - 401: Missing or invalid API key
    - 409: Device already cooking (DEVICE_BUSY)
    - 503: Device offline (DEVICE_OFFLINE)

    Flow:
    1. Extract JSON from request
    2. Validate with validators.validate_start_cook()
    3. Create Anova client
    4. Call client.start_cook()
    5. Return success response

    Reference: CLAUDE.md Section "API Endpoints Reference > POST /start-cook" (lines 948-978)
    Reference: CLAUDE.md Section "Code Patterns > 3. Authentication Pattern" (lines 401-434)
    """
    # Validate input (raises ValidationError if invalid)
    validated = validate_start_cook(request.json or {})

    # Get configuration from app context
    config: Config = current_app.config['ANOVA_CONFIG']

    # Create Anova client and start cook
    client = AnovaClient(config)
    result = client.start_cook(
        temperature_c=validated['temperature_celsius'],
        time_minutes=validated['time_minutes']
    )

    # Return success response
    return jsonify(result), 200


@api.route('/status', methods=['GET'])
@require_api_key
def get_status() -> tuple[dict[str, Any], int]:
    """
    Get current cooking status.

    Requires:
    - Authorization: Bearer <api_key> header

    Success response (200):
        {
            "device_online": true,
            "state": "cooking",  // idle, preheating, cooking, done
            "current_temp_celsius": 64.8,
            "target_temp_celsius": 65.0,
            "time_remaining_minutes": 47,
            "time_elapsed_minutes": 43,
            "is_running": true
        }

    Error responses:
    - 401: Missing or invalid API key
    - 503: Device offline (DEVICE_OFFLINE)

    Reference: CLAUDE.md Section "API Endpoints Reference > GET /status" (lines 980-1002)
    """
    # Get configuration from app context
    config: Config = current_app.config['ANOVA_CONFIG']

    # Create Anova client and get status
    client = AnovaClient(config)
    status = client.get_status()

    # Return status response
    return jsonify(status), 200


@api.route('/stop-cook', methods=['POST'])
@require_api_key
def stop_cook() -> tuple[dict[str, Any], int]:
    """
    Stop the current cooking session.

    Requires:
    - Authorization: Bearer <api_key> header

    Success response (200):
        {
            "status": "stopped",
            "final_temp_celsius": 64.9,
            "total_time_minutes": 85
        }

    Error responses:
    - 401: Missing or invalid API key
    - 409: No active cook (NO_ACTIVE_COOK)
    - 503: Device offline (DEVICE_OFFLINE)

    Reference: CLAUDE.md Section "API Endpoints Reference > POST /stop-cook" (lines 1004-1026)
    """
    # Get configuration from app context
    config: Config = current_app.config['ANOVA_CONFIG']

    # Create Anova client and stop cook
    client = AnovaClient(config)
    result = client.stop_cook()

    # Return success response
    return jsonify(result), 200


# ==============================================================================
# ERROR HANDLING NOTES
# ==============================================================================
# All exceptions should propagate to error handlers registered in app.py.
# Do NOT catch ValidationError or AnovaAPIError in route handlers.
#
# Exception → HTTP Status mapping (handled by middleware.py):
# - ValidationError → 400 Bad Request
# - DeviceOfflineError → 503 Service Unavailable
# - DeviceBusyError → 409 Conflict
# - NoActiveCookError → 409 Conflict
# - AnovaAPIError → 500 Internal Server Error
# - AuthenticationError → 500 Internal Server Error
#
# Reference: CLAUDE.md Section "Code Patterns > 1. Error Handling Pattern" (lines 207-233)
