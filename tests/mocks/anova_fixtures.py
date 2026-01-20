"""
Pytest fixtures for mocking Anova Cloud API.

Provides reusable, composable mock fixtures for integration tests.
All fixtures use @responses.activate to ensure isolation.

Usage:
    def test_something(client, auth_headers, mock_anova_api_success):
        mock_anova_api_success()  # Activate mock
        response = client.post('/start-cook', headers=auth_headers, json={...})
        assert response.status_code == 200

Reference: tests/mocks/anova_responses.py for mock data
"""

import pytest
import responses

from tests.mocks.anova_responses import (
    DEVICE_STATUS_COOKING,
    DEVICE_STATUS_COOKING_ALMOST_DONE,
    DEVICE_STATUS_DONE,
    DEVICE_STATUS_IDLE,
    DEVICE_STATUS_OFFLINE_404,
    DEVICE_STATUS_PREHEATING,
    FIREBASE_AUTH_SUCCESS,
    FIREBASE_AUTH_URL,
    FIREBASE_REFRESH_URL,
    FIREBASE_TOKEN_EXPIRED,
    FIREBASE_TOKEN_REFRESH_SUCCESS,
    START_COOK_ALREADY_COOKING,
    START_COOK_DEVICE_OFFLINE,
    START_COOK_SUCCESS,
    STOP_COOK_NOT_COOKING,
    STOP_COOK_SUCCESS,
    anova_device_url,
)

# ==============================================================================
# ATOMIC MOCK FIXTURES (Building blocks)
# ==============================================================================


@pytest.fixture
def mock_firebase_auth_success():
    """Mock successful Firebase authentication."""

    def _add_mock():
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

    return _add_mock


@pytest.fixture
def mock_firebase_token_refresh():
    """Mock successful token refresh."""

    def _add_mock():
        responses.add(
            responses.POST, FIREBASE_REFRESH_URL, json=FIREBASE_TOKEN_REFRESH_SUCCESS, status=200
        )

    return _add_mock


@pytest.fixture
def mock_device_status_idle():
    """Mock device in idle state."""

    def _add_mock():
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

    return _add_mock


@pytest.fixture
def mock_device_status_preheating():
    """Mock device in preheating state."""

    def _add_mock():
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_PREHEATING,
            status=200,
        )

    return _add_mock


@pytest.fixture
def mock_device_status_cooking():
    """Mock device in cooking state."""

    def _add_mock():
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

    return _add_mock


@pytest.fixture
def mock_device_start_cook_success():
    """Mock successful start cook command."""

    def _add_mock():
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_SUCCESS,
            status=200,
        )

    return _add_mock


@pytest.fixture
def mock_device_stop_cook_success():
    """Mock successful stop cook command."""

    def _add_mock():
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "stop"),
            json=STOP_COOK_SUCCESS,
            status=200,
        )

    return _add_mock


# ==============================================================================
# COMPOSITE MOCK FIXTURES (Complete scenarios)
# ==============================================================================


@pytest.fixture
def mock_anova_api_success():
    """
    Mock complete successful cook start flow.

    Includes:
    - Firebase auth success
    - Device idle status
    - Start cook success
    - Stop cook success

    Use for: Happy path integration tests (INT-01)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # Device idle
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

        # Device status after start (cooking)
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

        # Start cook success
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_SUCCESS,
            status=200,
        )

        # Stop cook success
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "stop"),
            json=STOP_COOK_SUCCESS,
            status=200,
        )

        # Device idle after stop
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

    return _mock


@pytest.fixture
def mock_anova_api_offline():
    """
    Mock device offline scenario.

    Includes:
    - Firebase auth success (cloud works)
    - Device offline (404)

    Use for: Device offline tests (INT-03, INT-ST-04)
    """

    @responses.activate
    def _mock():
        # Firebase auth still works
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # Device offline
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_OFFLINE_404,
            status=404,
        )

        # Start cook also fails
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_DEVICE_OFFLINE,
            status=503,
        )

    return _mock


@pytest.fixture
def mock_anova_api_busy():
    """
    Mock device already cooking scenario.

    Includes:
    - Firebase auth success
    - Device cooking status
    - Start cook rejected (409)

    Use for: Device busy tests (INT-04)
    """

    @responses.activate
    def _mock():
        # Firebase auth succeeds
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # Device status shows cooking
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

        # Start cook rejected
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_ALREADY_COOKING,
            status=409,
        )

    return _mock


@pytest.fixture
def mock_anova_api_stop_without_cook():
    """
    Mock stop cook when device is idle.

    Includes:
    - Firebase auth success
    - Device idle status
    - Stop cook rejected (409)

    Use for: Edge case tests (INT-06)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # Device idle
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

        # Stop rejected (no active cook)
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "stop"),
            json=STOP_COOK_NOT_COOKING,
            status=409,
        )

    return _mock


@pytest.fixture
def mock_token_expired_then_refreshed():
    """
    Mock token expiry with automatic refresh.

    Sequence:
    1. Initial auth succeeds (but token will expire)
    2. First API call returns 401 (token expired)
    3. Token refresh succeeds
    4. Retry API call succeeds

    Use for: Token refresh tests (INT-07)
    """

    @responses.activate
    def _mock():
        # Initial auth (token will expire)
        responses.add(
            responses.POST,
            FIREBASE_AUTH_URL,
            json={**FIREBASE_AUTH_SUCCESS, "expiresIn": "0"},  # Expired immediately
            status=200,
        )

        # First API call fails (token expired)
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=FIREBASE_TOKEN_EXPIRED,
            status=401,
        )

        # Token refresh succeeds
        responses.add(
            responses.POST, FIREBASE_REFRESH_URL, json=FIREBASE_TOKEN_REFRESH_SUCCESS, status=200
        )

        # Retry succeeds
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_SUCCESS,
            status=200,
        )

    return _mock


@pytest.fixture
def mock_state_progression_idle_to_cooking():
    """
    Mock state progression: idle → preheating → cooking.

    Sequence:
    1. Status: idle
    2. Start cook: preheating
    3. Status: preheating (heating up)
    4. Status: cooking (reached temperature)

    Use for: State transition tests (INT-ST-01, INT-ST-02)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # First status: idle
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

        # Start cook command
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "start"),
            json=START_COOK_SUCCESS,
            status=200,
        )

        # Second status: preheating
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_PREHEATING,
            status=200,
        )

        # Third status: cooking (reached temp)
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

    return _mock


@pytest.fixture
def mock_state_progression_cooking_to_done():
    """
    Mock state progression: cooking → done.

    Sequence:
    1. Status: cooking (time remaining)
    2. Status: done (timer expired)

    Use for: State transition tests (INT-ST-03)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # First status: cooking with time remaining
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING_ALMOST_DONE,
            status=200,
        )

        # Second status: done
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_DONE,
            status=200,
        )

    return _mock


@pytest.fixture
def mock_state_progression_cooking_to_idle():
    """
    Mock state progression: cooking → idle (stop cook).

    Sequence:
    1. Status: cooking
    2. Stop cook command
    3. Status: idle

    Use for: State transition tests (INT-ST-05)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # First status: cooking
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

        # Stop cook
        responses.add(
            responses.POST,
            anova_device_url("test-device-123", "stop"),
            json=STOP_COOK_SUCCESS,
            status=200,
        )

        # Second status: idle
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_IDLE,
            status=200,
        )

    return _mock


@pytest.fixture
def mock_connection_lost_during_cook():
    """
    Mock connection loss: cooking → offline.

    Sequence:
    1. Status: cooking (online)
    2. Status: offline (404)

    Use for: State transition tests (INT-ST-04)
    """

    @responses.activate
    def _mock():
        # Firebase auth
        responses.add(responses.POST, FIREBASE_AUTH_URL, json=FIREBASE_AUTH_SUCCESS, status=200)

        # First status: cooking
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_COOKING,
            status=200,
        )

        # Second status: offline
        responses.add(
            responses.GET,
            anova_device_url("test-device-123", "status"),
            json=DEVICE_STATUS_OFFLINE_404,
            status=404,
        )

    return _mock
