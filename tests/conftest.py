"""
Pytest fixtures for integration and unit testing.

This module provides comprehensive test infrastructure including:
- Flask app and client fixtures
- Authentication fixtures (valid/invalid)
- Test data fixtures (valid/invalid cook requests)
- Anova API mock fixtures (success, offline, busy scenarios)

Reference:
- docs/09-integration-test-specification.md (lines 104-382)
- CLAUDE.md Section "Testing Strategy"
"""

import pytest
from flask.testing import FlaskClient

from server.config import Config

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================

TEST_CONFIG = {
    "PERSONAL_ACCESS_TOKEN": "anova-test-token-12345",
    "API_KEY": "test-api-key-12345",
    "HOST": "127.0.0.1",
    "PORT": 5000,
    "DEBUG": True,
}


# ==============================================================================
# CORE FIXTURES
# ==============================================================================


@pytest.fixture
def app(monkeypatch):
    """
    Create Flask application configured for testing.

    Note: WebSocket client is NOT initialized in tests. Routes tests must
    inject mock_websocket_client using monkeypatch.

    Returns:
        Flask app with test configuration

    Reference: Spec Section 2.2 (lines 104-133)
    Reference: WebSocket migration testing strategy
    """
    # Set PERSONAL_ACCESS_TOKEN environment variable (required by config)
    monkeypatch.setenv("PERSONAL_ACCESS_TOKEN", "anova-test-token-12345")
    monkeypatch.setenv("API_KEY", "test-api-key-12345")

    # Create test configuration
    config = Config(**TEST_CONFIG)

    # Create app WITHOUT WebSocket client (tests inject mock)
    # This prevents actual WebSocket connection during tests
    from flask import Flask

    from server.middleware import register_error_handlers, setup_request_logging
    from server.routes import api

    app = Flask(__name__)
    app.config.from_object(config)
    app.config["TESTING"] = True

    # Register blueprint
    app.register_blueprint(api)

    # Setup middleware
    register_error_handlers(app)
    setup_request_logging(app)

    yield app

    # Cleanup after tests (if needed)


@pytest.fixture
def client(app) -> FlaskClient:
    """
    Create Flask test client.

    Args:
        app: Flask application fixture

    Returns:
        Flask test client for making HTTP requests

    Reference: Spec Section 2.2 (lines 130-133)
    """
    return app.test_client()


# ==============================================================================
# AUTHENTICATION FIXTURES
# ==============================================================================


@pytest.fixture
def auth_headers():
    """
    Valid authentication headers for testing.

    Returns:
        Dict with Authorization header containing valid API key

    Reference: Spec Section 2.3 (lines 136-155)
    """
    return {"Authorization": "Bearer test-api-key-12345", "Content-Type": "application/json"}


@pytest.fixture
def invalid_auth_headers():
    """
    Invalid authentication headers for testing.

    Returns:
        Dict with Authorization header containing invalid API key

    Reference: Spec Section 2.3 (lines 148-155)
    """
    return {"Authorization": "Bearer wrong-key", "Content-Type": "application/json"}


# ==============================================================================
# TEST DATA FIXTURES
# ==============================================================================


@pytest.fixture
def valid_cook_requests():
    """
    Collection of valid cook requests for testing.

    Returns:
        Dict mapping scenario names to valid request data

    Scenarios:
    - chicken: Standard chicken breast (65°C, 90 min)
    - steak: Medium-rare ribeye (54°C, 120 min)
    - salmon: Salmon fillet (52°C, 45 min)
    - edge_case_min_temp: Minimum safe temp (40°C)
    - edge_case_max_temp: Maximum temp (100°C)
    - edge_case_max_time: Maximum time (5999 min)

    Reference: Spec Section 2.4 (lines 162-193)
    """
    return {
        "chicken": {"temperature_celsius": 65.0, "time_minutes": 90, "food_type": "chicken breast"},
        "steak": {"temperature_celsius": 54.0, "time_minutes": 120, "food_type": "ribeye steak"},
        "salmon": {"temperature_celsius": 52.0, "time_minutes": 45, "food_type": "salmon fillet"},
        "edge_case_min_temp": {"temperature_celsius": 40.0, "time_minutes": 60},
        "edge_case_max_temp": {"temperature_celsius": 100.0, "time_minutes": 60},
        "edge_case_max_time": {"temperature_celsius": 65.0, "time_minutes": 5999},
    }


@pytest.fixture
def invalid_cook_requests():
    """
    Collection of invalid cook requests for validation testing.

    Returns:
        Dict mapping scenario names to invalid request data with expected errors

    Scenarios:
    - temp_too_low: Below 40°C danger zone
    - temp_too_high: Above 100°C boiling point
    - unsafe_poultry: Chicken below 57°C minimum
    - unsafe_ground_meat: Ground beef below 60°C minimum
    - time_zero: Zero minutes cook time
    - time_too_long: Exceeds 5999 minute limit
    - missing_temperature: Required field missing
    - missing_time: Required field missing

    Reference: Spec Section 2.4 (lines 196-239)
    """
    return {
        "temp_too_low": {
            "temperature_celsius": 35.0,
            "time_minutes": 60,
            "expected_error": "TEMPERATURE_TOO_LOW",
        },
        "temp_too_high": {
            "temperature_celsius": 105.0,
            "time_minutes": 60,
            "expected_error": "TEMPERATURE_TOO_HIGH",
        },
        "unsafe_poultry": {
            "temperature_celsius": 56.0,
            "time_minutes": 90,
            "food_type": "chicken",
            "expected_error": "POULTRY_TEMP_UNSAFE",
        },
        "unsafe_ground_meat": {
            "temperature_celsius": 59.0,
            "time_minutes": 60,
            "food_type": "ground beef",
            "expected_error": "GROUND_MEAT_TEMP_UNSAFE",
        },
        "time_zero": {
            "temperature_celsius": 65.0,
            "time_minutes": 0,
            "expected_error": "TIME_TOO_SHORT",
        },
        "time_too_long": {
            "temperature_celsius": 65.0,
            "time_minutes": 6000,
            "expected_error": "TIME_TOO_LONG",
        },
        "missing_temperature": {"time_minutes": 90, "expected_error": "MISSING_TEMPERATURE"},
        "missing_time": {"temperature_celsius": 65.0, "expected_error": "MISSING_TIME"},
    }


# ==============================================================================
# WEBSOCKET CLIENT MOCK FIXTURES
# ==============================================================================


@pytest.fixture
def mock_websocket_client():
    """
    Create a mock WebSocket client for testing routes without real WebSocket connection.

    Provides a mock AnovaWebSocketClient with standard behavior:
    - get_status() returns idle device
    - start_cook() succeeds
    - stop_cook() succeeds

    Usage:
        def test_route(client, auth_headers, mock_websocket_client, monkeypatch):
            # Inject mock into app
            monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)
            # Make requests
            response = client.post('/start-cook', headers=auth_headers, json={...})

    Returns:
        Mock object with get_status, start_cook, stop_cook methods

    Reference: WebSocket migration testing strategy
    """
    import threading
    from unittest.mock import Mock

    mock = Mock()

    # CRITICAL FIX: Add attributes needed by real implementation
    mock.devices_lock = threading.Lock()
    mock.pending_lock = threading.Lock()
    mock.status_lock = threading.Lock()
    mock.pending_requests = {}
    mock.shutdown_requested = threading.Event()
    mock.devices = {"test-device": {"type": "oven_v2"}}
    mock.selected_device = "test-device"

    # Mock get_status (idle by default)
    mock.get_status.return_value = {
        "device_online": True,
        "state": "idle",
        "current_temp_celsius": 20.0,
        "target_temp_celsius": None,
        "time_remaining_minutes": None,
        "time_elapsed_minutes": None,
        "is_running": False,
    }

    # Mock start_cook (success by default)
    mock.start_cook.return_value = {
        "success": True,
        "message": "Cook started successfully",
        "cook_id": "550e8400-e29b-41d4-a716-446655440000",
        "device_state": "preheating",
        "target_temp_celsius": 65.0,
        "time_minutes": 90,
        "estimated_completion": "2025-01-15T10:30:00Z",
    }

    # Mock stop_cook (success by default)
    mock.stop_cook.return_value = {
        "success": True,
        "message": "Cook stopped successfully",
        "device_state": "idle",
        "final_temp_celsius": 64.9,
    }

    return mock


@pytest.fixture
def mock_websocket_client_offline():
    """
    Mock WebSocket client that simulates device offline scenario.

    All methods raise DeviceOfflineError.

    Usage:
        def test_device_offline(client, auth_headers, mock_websocket_client_offline, monkeypatch):
            monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_offline)
            response = client.post('/start-cook', headers=auth_headers, json={...})
            assert response.status_code == 503

    Returns:
        Mock object that raises DeviceOfflineError

    Reference: WebSocket migration testing strategy
    """
    import threading
    from unittest.mock import Mock

    from server.exceptions import DeviceOfflineError

    mock = Mock()

    # CRITICAL FIX: Add attributes needed by real implementation
    mock.devices_lock = threading.Lock()
    mock.pending_lock = threading.Lock()
    mock.status_lock = threading.Lock()
    mock.pending_requests = {}
    mock.shutdown_requested = threading.Event()
    mock.devices = {}  # Offline - no devices
    mock.selected_device = None  # Offline - no selected device

    # All methods raise DeviceOfflineError
    mock.get_status.side_effect = DeviceOfflineError("No device connected")
    mock.start_cook.side_effect = DeviceOfflineError("No device connected")
    mock.stop_cook.side_effect = DeviceOfflineError("No device connected")

    return mock


@pytest.fixture
def mock_websocket_client_busy():
    """
    Mock WebSocket client that simulates device already cooking scenario.

    get_status returns is_running=True
    start_cook raises DeviceBusyError
    stop_cook succeeds

    Usage:
        def test_device_busy(client, auth_headers, mock_websocket_client_busy, monkeypatch):
            monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_busy)
            response = client.post('/start-cook', headers=auth_headers, json={...})
            assert response.status_code == 409

    Returns:
        Mock object with is_running=True

    Reference: WebSocket migration testing strategy
    """
    import threading
    from unittest.mock import Mock

    from server.exceptions import DeviceBusyError

    mock = Mock()

    # CRITICAL FIX: Add attributes needed by real implementation
    mock.devices_lock = threading.Lock()
    mock.pending_lock = threading.Lock()
    mock.status_lock = threading.Lock()
    mock.pending_requests = {}
    mock.shutdown_requested = threading.Event()
    mock.devices = {"test-device": {"type": "oven_v2"}}
    mock.selected_device = "test-device"

    # get_status shows device is cooking
    mock.get_status.return_value = {
        "device_online": True,
        "state": "cooking",
        "current_temp_celsius": 64.8,
        "target_temp_celsius": 65.0,
        "time_remaining_minutes": 45,
        "time_elapsed_minutes": 45,
        "is_running": True,
    }

    # start_cook raises DeviceBusyError
    mock.start_cook.side_effect = DeviceBusyError(
        "Device is already cooking. Stop current cook first."
    )

    # stop_cook succeeds
    mock.stop_cook.return_value = {
        "success": True,
        "message": "Cook stopped successfully",
        "device_state": "idle",
        "final_temp_celsius": 64.8,
    }

    return mock


@pytest.fixture
def mock_websocket_client_no_active_cook():
    """
    Mock WebSocket client that simulates no active cook scenario.

    get_status returns is_running=False
    start_cook succeeds
    stop_cook raises NoActiveCookError

    Usage:
        def test_no_active_cook(client, auth_headers, mock_websocket_client_no_active_cook, monkeypatch):
            monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_no_active_cook)
            response = client.post('/stop-cook', headers=auth_headers)
            assert response.status_code == 409

    Returns:
        Mock object with is_running=False

    Reference: WebSocket migration testing strategy
    """
    import threading
    from unittest.mock import Mock

    from server.exceptions import NoActiveCookError

    mock = Mock()

    # CRITICAL FIX: Add attributes needed by real implementation
    mock.devices_lock = threading.Lock()
    mock.pending_lock = threading.Lock()
    mock.status_lock = threading.Lock()
    mock.pending_requests = {}
    mock.shutdown_requested = threading.Event()
    mock.devices = {"test-device": {"type": "oven_v2"}}
    mock.selected_device = "test-device"

    # get_status shows device is idle
    mock.get_status.return_value = {
        "device_online": True,
        "state": "idle",
        "current_temp_celsius": 20.0,
        "target_temp_celsius": None,
        "time_remaining_minutes": None,
        "time_elapsed_minutes": None,
        "is_running": False,
    }

    # start_cook succeeds
    mock.start_cook.return_value = {
        "success": True,
        "message": "Cook started successfully",
        "cook_id": "550e8400-e29b-41d4-a716-446655440000",
        "device_state": "preheating",
        "target_temp_celsius": 65.0,
        "time_minutes": 90,
        "estimated_completion": "2025-01-15T10:30:00Z",
    }

    # stop_cook raises NoActiveCookError
    mock.stop_cook.side_effect = NoActiveCookError("No active cook to stop")

    return mock


# ==============================================================================
# BACKWARD COMPATIBILITY (for existing unit tests)
# ==============================================================================


@pytest.fixture
def valid_cook_request():
    """
    Single valid cook request for unit tests.

    DEPRECATED: Use valid_cook_requests["chicken"] instead.
    Kept for backward compatibility with existing unit tests.
    """
    return {"temperature_celsius": 65.0, "time_minutes": 90, "food_type": "chicken"}


@pytest.fixture
def invalid_temp_request():
    """
    Single invalid temperature request for unit tests.

    DEPRECATED: Use invalid_cook_requests["temp_too_low"] instead.
    Kept for backward compatibility with existing unit tests.
    """
    return {"temperature_celsius": 39.9, "time_minutes": 90}


@pytest.fixture
def mock_anova_client(monkeypatch):
    """
    DEPRECATED: This fixture is for unit tests using monkeypatch.

    For integration tests, use mock_anova_api_success, mock_anova_api_offline,
    or mock_anova_api_busy with @responses.activate decorator instead.

    Kept for backward compatibility with existing unit tests.
    """
    # Return None - unit tests should use responses mocks instead
    return None


# ==============================================================================
# FIXTURE VERIFICATION
# ==============================================================================
# Note: Fixture verification happens automatically on import.
# If this file imports without errors, all fixtures are properly defined.


# ==============================================================================
# TESTING NOTES
# ==============================================================================
# Fixture scope:
# - function (default): New instance for each test
# - module: One instance per test file
# - session: One instance for entire test run
#
# Use function scope for most fixtures (isolation between tests)
# Use module/session scope for expensive setup (database, etc.)
#
# Reference: pytest fixtures documentation
