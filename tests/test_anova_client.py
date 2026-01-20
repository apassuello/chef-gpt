"""
Tests for Anova Cloud API client with HTTP mocking.

Uses the 'responses' library to mock HTTP requests to:
- Firebase authentication API
- Anova Cloud API

Tests cover:
- Authentication flow (email/password → JWT tokens)
- Token refresh logic
- Device control (start, stop, status)
- Error handling (offline, auth failures)

Reference: CLAUDE.md Section "Testing Strategy > Mocking Anova API"
"""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import requests
import responses

from server.anova_client import AnovaClient
from server.config import Config
from server.exceptions import (
    AnovaAPIError,
    AuthenticationError,
    DeviceBusyError,
    DeviceOfflineError,
    NoActiveCookError,
)


# Test fixtures
@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return Config(
        ANOVA_EMAIL="test@example.com",
        ANOVA_PASSWORD="test_password",
        DEVICE_ID="test_device_123",
        API_KEY="test_api_key"
    )


@pytest.fixture
def firebase_api_key():
    """Mock Firebase API key."""
    return "mock_firebase_api_key"


# ==============================================================================
# AUTHENTICATION TESTS
# ==============================================================================

@responses.activate
def test_authentication_success(mock_config, firebase_api_key):
    """Test successful Firebase authentication."""
    # Mock Firebase auth endpoint
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-access-token",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        # Verify tokens were stored
        assert client._access_token == "mock-access-token"
        assert client._refresh_token == "mock-refresh-token"
        assert client._token_expiry is not None

        # Verify expiry is approximately 1 hour from now
        expected_expiry = datetime.now() + timedelta(hours=1)
        time_diff = abs((client._token_expiry - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds


@responses.activate
def test_authentication_invalid_credentials(mock_config, firebase_api_key):
    """Test authentication fails with invalid credentials."""
    # Mock Firebase auth endpoint returning 400 (invalid credentials)
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={"error": {"message": "INVALID_PASSWORD"}},
        status=400
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        with pytest.raises(AuthenticationError) as exc_info:
            AnovaClient(mock_config)

        assert "authentication failed" in str(exc_info.value).lower()


@responses.activate
def test_token_refresh(mock_config, firebase_api_key):
    """Test token refresh when expired."""
    # Mock initial auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "initial-token",
            "refreshToken": "refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock token refresh endpoint
    responses.add(
        responses.POST,
        f"https://securetoken.googleapis.com/v1/token?key={firebase_api_key}",
        json={
            "id_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": "3600"
        },
        status=200
    )

    # Mock device status endpoint (to trigger token check)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "idle",
            "currentTemperature": 20.0,
            "targetTemperature": None
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        # Manually set token to expired (in the past)
        client._token_expiry = datetime.now() - timedelta(minutes=1)

        # Make API call that should trigger refresh
        client.get_status()

        # Verify token was refreshed
        assert client._access_token == "new-access-token"


# ==============================================================================
# START COOK TESTS
# ==============================================================================

@responses.activate
def test_start_cook_success(mock_config, firebase_api_key):
    """Test successful cook start."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status check (to ensure not already cooking)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "idle",
            "currentTemperature": 20.0
        },
        status=200
    )

    # Mock Anova start cook
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test_device_123/cook",
        json={
            "status": "started",
            "cookId": "cook_123"
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)
        result = client.start_cook(temperature_c=65.0, time_minutes=90)

        assert result["success"] is True
        assert result["target_temp_celsius"] == 65.0
        assert result["time_minutes"] == 90
        assert "cook_id" in result


@responses.activate
def test_start_cook_device_offline(mock_config, firebase_api_key):
    """Test start cook fails when device offline."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status returning 404 (device not found/offline)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={"error": "Device not found"},
        status=404
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        with pytest.raises(DeviceOfflineError):
            client.start_cook(temperature_c=65.0, time_minutes=90)


@responses.activate
def test_start_cook_device_busy(mock_config, firebase_api_key):
    """Test start cook fails when device already cooking."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status showing is_running=True (cooking)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "cooking",
            "currentTemperature": 64.5,
            "targetTemperature": 65.0
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        with pytest.raises(DeviceBusyError) as exc_info:
            client.start_cook(temperature_c=65.0, time_minutes=90)

        assert "already cooking" in str(exc_info.value).lower()


# ==============================================================================
# GET STATUS TESTS
# ==============================================================================

@responses.activate
def test_get_status_success(mock_config, firebase_api_key):
    """Test successful status retrieval."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock Anova status endpoint
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "cooking",
            "currentTemperature": 64.8,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 2820,  # 47 minutes in seconds
            "cookTimeElapsed": 2580      # 43 minutes in seconds
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)
        status = client.get_status()

        assert status["device_online"] is True
        assert status["state"] == "cooking"
        assert status["current_temp_celsius"] == 64.8
        assert status["target_temp_celsius"] == 65.0
        assert status["time_remaining_minutes"] == 47
        assert status["time_elapsed_minutes"] == 43
        assert status["is_running"] is True


@responses.activate
def test_get_status_device_offline(mock_config, firebase_api_key):
    """Test get status when device offline."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock status endpoint returning 404 (offline)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={"error": "Device offline"},
        status=404
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        with pytest.raises(DeviceOfflineError):
            client.get_status()


# ==============================================================================
# STOP COOK TESTS
# ==============================================================================

@responses.activate
def test_stop_cook_success(mock_config, firebase_api_key):
    """Test successful cook stop."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status showing is_running=True
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "cooking",
            "currentTemperature": 64.9,
            "targetTemperature": 65.0
        },
        status=200
    )

    # Mock Anova stop endpoint
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test_device_123/stop",
        json={
            "status": "stopped",
            "finalTemperature": 64.9
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)
        result = client.stop_cook()

        assert result["success"] is True
        assert result["device_state"] == "idle"


@responses.activate
def test_stop_cook_no_active_cook(mock_config, firebase_api_key):
    """Test stop cook fails when no cook is active."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock device status showing is_running=False
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "idle",
            "currentTemperature": 20.0
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        with pytest.raises(NoActiveCookError) as exc_info:
            client.stop_cook()

        assert "no active cook" in str(exc_info.value).lower()


# ==============================================================================
# TOKEN MANAGEMENT TESTS
# ==============================================================================

@responses.activate
def test_token_expiry_calculation(mock_config, firebase_api_key):
    """Test token expiry is calculated correctly."""
    # Mock auth with specific expiresIn
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"  # 1 hour
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        before_init = datetime.now()
        client = AnovaClient(mock_config)
        after_init = datetime.now()

        # Token should expire in approximately 1 hour
        expected_min = before_init + timedelta(hours=1) - timedelta(seconds=5)
        expected_max = after_init + timedelta(hours=1) + timedelta(seconds=5)

        assert expected_min <= client._token_expiry <= expected_max


@responses.activate
def test_proactive_token_refresh(mock_config, firebase_api_key):
    """Test token is refreshed before expiration (5 min buffer)."""
    # Mock initial auth
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "initial-token",
            "refreshToken": "refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock token refresh
    responses.add(
        responses.POST,
        f"https://securetoken.googleapis.com/v1/token?key={firebase_api_key}",
        json={
            "id_token": "refreshed-token",
            "refresh_token": "new-refresh-token",
            "expires_in": "3600"
        },
        status=200
    )

    # Mock API call
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={
            "cookerId": "test_device_123",
            "cookerState": "idle"
        },
        status=200
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        # Set token to expire in 4 minutes (within 5-min buffer)
        client._token_expiry = datetime.now() + timedelta(minutes=4)
        client._access_token = "initial-token"

        # Make API call that should trigger refresh
        client.get_status()

        # Verify refresh was triggered
        assert client._access_token == "refreshed-token"


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

def test_network_error_handling(mock_config, firebase_api_key):
    """Test handling of network errors."""
    # Mock auth endpoint with callback that raises connection error
    def connection_error_callback(request):
        raise requests.exceptions.ConnectionError("Network unreachable")

    with responses.RequestsMock() as rsps:
        rsps.add_callback(
            responses.POST,
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
            callback=connection_error_callback
        )

        with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
            with pytest.raises(AuthenticationError) as exc_info:
                AnovaClient(mock_config)

            assert "network" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()


@responses.activate
def test_api_error_handling(mock_config, firebase_api_key):
    """Test handling of Anova API errors."""
    # Mock Firebase auth (success)
    responses.add(
        responses.POST,
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock Anova endpoint returning 500 error
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test_device_123",
        json={"error": "Internal server error"},
        status=500
    )

    with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
        client = AnovaClient(mock_config)

        with pytest.raises(AnovaAPIError) as exc_info:
            client.get_status()

        assert "500" in str(exc_info.value) or "server error" in str(exc_info.value).lower()


# ==============================================================================
# SECURITY TESTS
# ==============================================================================

def test_tokens_not_logged(mock_config, firebase_api_key, caplog):
    """Test that tokens are never logged (security check)."""
    # This test verifies that sensitive tokens don't appear in logs

    with responses.RequestsMock() as rsps:
        # Mock Firebase auth
        rsps.add(
            responses.POST,
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
            json={
                "idToken": "SENSITIVE_ACCESS_TOKEN_12345",
                "refreshToken": "SENSITIVE_REFRESH_TOKEN_67890",
                "expiresIn": "3600"
            },
            status=200
        )

        with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
            with caplog.at_level("DEBUG"):
                client = AnovaClient(mock_config)

                # Check that sensitive tokens don't appear in logs
                log_text = caplog.text
                assert "SENSITIVE_ACCESS_TOKEN_12345" not in log_text
                assert "SENSITIVE_REFRESH_TOKEN_67890" not in log_text


def test_credentials_not_stored_in_memory(mock_config, firebase_api_key):
    """Test that credentials are not unnecessarily stored."""
    with responses.RequestsMock() as rsps:
        # Mock Firebase auth
        rsps.add(
            responses.POST,
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}",
            json={
                "idToken": "mock-token",
                "refreshToken": "mock-refresh",
                "expiresIn": "3600"
            },
            status=200
        )

        with patch.dict(os.environ, {'FIREBASE_API_KEY': firebase_api_key}):
            client = AnovaClient(mock_config)

            # Verify password is stored in config (needed for potential re-auth)
            # but not duplicated in client
            assert not hasattr(client, 'password')
            assert not hasattr(client, '_password')


# ==============================================================================
# IMPLEMENTATION NOTES
# ==============================================================================
# Test implementation complete!
#
# All 16 tests implemented with:
# - @responses.activate decorator for HTTP mocking
# - Mock both Firebase and Anova API endpoints
# - Test success and failure scenarios
# - Verify proper error types are raised
# - Test token refresh logic
# - Verify security (tokens not logged)
#
# Reference: CLAUDE.md Section "Testing Strategy > Mocking Anova API" (lines 890-942)
# Reference: responses library documentation
