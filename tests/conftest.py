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
import responses
from typing import Dict, Any
from flask.testing import FlaskClient

from server.app import create_app
from server.config import Config


# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================

TEST_CONFIG = {
    "ANOVA_EMAIL": "test@example.com",
    "ANOVA_PASSWORD": "test-password",
    "DEVICE_ID": "test-device-123",
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

    Returns:
        Flask app with test configuration

    Reference: Spec Section 2.2 (lines 104-133)
    """
    # Set FIREBASE_API_KEY environment variable for Anova client
    monkeypatch.setenv("FIREBASE_API_KEY", "test-firebase-api-key-12345")

    # Create test configuration (only Config fields)
    config = Config(**TEST_CONFIG)

    # Create app with test config
    app = create_app(config)

    # Set Flask-specific test configuration
    app.config['TESTING'] = True

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
    return {
        "Authorization": "Bearer test-api-key-12345",
        "Content-Type": "application/json"
    }


@pytest.fixture
def invalid_auth_headers():
    """
    Invalid authentication headers for testing.

    Returns:
        Dict with Authorization header containing invalid API key

    Reference: Spec Section 2.3 (lines 148-155)
    """
    return {
        "Authorization": "Bearer wrong-key",
        "Content-Type": "application/json"
    }


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
        "chicken": {
            "temperature_celsius": 65.0,
            "time_minutes": 90,
            "food_type": "chicken breast"
        },
        "steak": {
            "temperature_celsius": 54.0,
            "time_minutes": 120,
            "food_type": "ribeye steak"
        },
        "salmon": {
            "temperature_celsius": 52.0,
            "time_minutes": 45,
            "food_type": "salmon fillet"
        },
        "edge_case_min_temp": {
            "temperature_celsius": 40.0,
            "time_minutes": 60
        },
        "edge_case_max_temp": {
            "temperature_celsius": 100.0,
            "time_minutes": 60
        },
        "edge_case_max_time": {
            "temperature_celsius": 65.0,
            "time_minutes": 5999
        }
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
            "expected_error": "TEMPERATURE_TOO_LOW"
        },
        "temp_too_high": {
            "temperature_celsius": 105.0,
            "time_minutes": 60,
            "expected_error": "TEMPERATURE_TOO_HIGH"
        },
        "unsafe_poultry": {
            "temperature_celsius": 56.0,
            "time_minutes": 90,
            "food_type": "chicken",
            "expected_error": "POULTRY_TEMP_UNSAFE"
        },
        "unsafe_ground_meat": {
            "temperature_celsius": 59.0,
            "time_minutes": 60,
            "food_type": "ground beef",
            "expected_error": "GROUND_MEAT_TEMP_UNSAFE"
        },
        "time_zero": {
            "temperature_celsius": 65.0,
            "time_minutes": 0,
            "expected_error": "TIME_TOO_SHORT"
        },
        "time_too_long": {
            "temperature_celsius": 65.0,
            "time_minutes": 6000,
            "expected_error": "TIME_TOO_LONG"
        },
        "missing_temperature": {
            "time_minutes": 90,
            "expected_error": "MISSING_TEMPERATURE"
        },
        "missing_time": {
            "temperature_celsius": 65.0,
            "expected_error": "MISSING_TIME"
        }
    }


# ==============================================================================
# ANOVA API MOCK FIXTURES
# ==============================================================================

@pytest.fixture
def mock_anova_api_success():
    """
    Add mock responses for successful Anova API operations (happy path).

    This fixture directly adds mock HTTP responses using the responses library.
    Tests using this fixture must decorate with @responses.activate.

    Mocks added:
    - Firebase authentication (POST signInWithPassword) → 200
    - Device status check (GET /status) → idle, online
    - Start cook command (POST /start) → success, preheating
    - Stop cook command (POST /stop) → success, idle

    Usage:
        @responses.activate
        def test_something(client, auth_headers, mock_anova_api_success):
            # Mocks are already added by the fixture
            response = client.post('/start-cook', headers=auth_headers, json={...})

    Reference: Spec Section 2.5 (lines 256-309)
    """
    # Mock Firebase authentication
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token-12345",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status (idle) - first call before start cook
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "IDLE",
            "currentTemperature": 22.5,
            "targetTemperature": None,
            "cookTimeRemaining": None,
            "cookTimeElapsed": None
        },
        status=200
    )

    # Mock device status (preheating) - subsequent calls after start cook
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "PREHEATING",
            "currentTemperature": 45.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 5400,  # 90 minutes in seconds
            "cookTimeElapsed": 0
        },
        status=200
    )

    # Mock start cook command
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/cook",
        json={
            "success": True,
            "cookId": "550e8400-e29b-41d4-a716-446655440000",  # UUID format
            "state": "preheating"
        },
        status=200
    )

    # Mock stop cook command
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/stop",
        json={
            "success": True,
            "state": "idle"
        },
        status=200
    )


@pytest.fixture
def mock_anova_api_offline():
    """
    Add mock responses for device offline scenario (error testing).

    This fixture directly adds mock HTTP responses using the responses library.
    Tests using this fixture must decorate with @responses.activate.

    Mocks added:
    - Firebase authentication (POST signInWithPassword) → 200 (still works)
    - Device status check (GET /status) → 404 Device not found

    Usage:
        @responses.activate
        def test_device_offline(client, auth_headers, mock_anova_api_offline):
            # Mocks are already added by the fixture
            response = client.post('/start-cook', headers=auth_headers, json={...})
            assert response.status_code == 503

    Reference: Spec Section 2.5 (lines 311-338)
    """
    # Mock Firebase auth (still works)
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token-12345",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device offline (404 or online=false)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        json={
            "error": "Device not found or offline"
        },
        status=404
    )


@pytest.fixture
def mock_anova_api_busy():
    """
    Add mock responses for device already cooking scenario (error testing).

    This fixture directly adds mock HTTP responses using the responses library.
    Tests using this fixture must decorate with @responses.activate.

    Mocks added:
    - Firebase authentication (POST signInWithPassword) → 200
    - Device status check (GET /status) → cooking, online
    - Start cook command (POST /start) → 409 Device already cooking

    Usage:
        @responses.activate
        def test_device_busy(client, auth_headers, mock_anova_api_busy):
            # Mocks are already added by the fixture
            response = client.post('/start-cook', headers=auth_headers, json={...})
            assert response.status_code == 409

    Reference: Spec Section 2.5 (lines 340-382)
    """
    # Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token-12345",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status (already cooking)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        json={
            "online": True,
            "state": "cooking",
            "current_temperature": 65.0,
            "target_temperature": 65.0,
            "timer_remaining": 45
        },
        status=200
    )

    # Mock start cook rejection (409)
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/start",
        json={
            "error": "Device already cooking"
        },
        status=409
    )


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
    return {
        "temperature_celsius": 65.0,
        "time_minutes": 90,
        "food_type": "chicken"
    }


@pytest.fixture
def invalid_temp_request():
    """
    Single invalid temperature request for unit tests.

    DEPRECATED: Use invalid_cook_requests["temp_too_low"] instead.
    Kept for backward compatibility with existing unit tests.
    """
    return {
        "temperature_celsius": 39.9,
        "time_minutes": 90
    }


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
