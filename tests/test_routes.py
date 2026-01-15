"""
Integration tests for Flask routes with WebSocket client mocks.

Tests all HTTP endpoints with mocked WebSocket client to avoid actual connections.
Tests both success and error scenarios, authentication, and error handling.

Endpoints tested:
- GET /health (no auth)
- POST /start-cook (auth required)
- GET /status (auth required)
- POST /stop-cook (auth required)

Testing Strategy:
- Use mock_websocket_client fixtures from conftest.py
- Inject mocks into app.config['ANOVA_CLIENT']
- Test authentication with valid/invalid headers
- Test validation error propagation
- Test Anova client error propagation (offline, busy, etc.)
- Verify response formats match API specification

Reference: CLAUDE.md Section "API Endpoints Reference"
Reference: CLAUDE.md Section "Testing Strategy > Integration tests for routes"
Reference: docs/05-api-specification.md
"""

import pytest
import json
from unittest.mock import Mock

from server.exceptions import (
    ValidationError,
    DeviceOfflineError,
    DeviceBusyError,
    NoActiveCookError,
    AnovaAPIError
)


# ==============================================================================
# HEALTH CHECK ENDPOINT TESTS
# ==============================================================================

def test_health_endpoint_success(client):
    """Test /health endpoint returns 200 without authentication."""
    response = client.get('/health')

    # Verify response
    assert response.status_code == 200

    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'version' in data
    assert 'timestamp' in data


def test_health_endpoint_no_auth_required(client):
    """Test /health endpoint works without authentication header."""
    # No Authorization header
    response = client.get('/health')

    # Should still work
    assert response.status_code == 200


# ==============================================================================
# START COOK ENDPOINT TESTS
# ==============================================================================

def test_start_cook_success(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test successful cook start with valid parameters."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Valid request
    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90,
        'food_type': 'chicken'
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Verify response
    assert response.status_code == 200

    data = response.get_json()
    assert data['success'] is True
    assert data['target_temp_celsius'] == 65.0
    assert data['time_minutes'] == 90
    assert 'cook_id' in data
    assert 'estimated_completion' in data

    # Verify client was called
    mock_websocket_client.start_cook.assert_called_once_with(
        temperature_c=65.0,
        time_minutes=90
    )


def test_start_cook_missing_auth(client, mock_websocket_client, monkeypatch):
    """Test start cook fails without authentication."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    # No Authorization header
    response = client.post('/start-cook', json=request_data)

    # Should return 401
    assert response.status_code == 401

    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'


def test_start_cook_invalid_auth(client, invalid_auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook fails with invalid API key."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=invalid_auth_headers, json=request_data)

    # Should return 401
    assert response.status_code == 401

    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'


def test_start_cook_validation_error_temp_too_low(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with temperature below minimum."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Invalid temperature (below 40°C)
    request_data = {
        'temperature_celsius': 35.0,
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should return 400 validation error
    assert response.status_code == 400

    data = response.get_json()
    assert data['error'] == 'TEMPERATURE_TOO_LOW'
    assert 'message' in data


def test_start_cook_validation_error_unsafe_poultry(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with unsafe poultry temperature."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Unsafe poultry temperature
    request_data = {
        'temperature_celsius': 56.0,
        'time_minutes': 90,
        'food_type': 'chicken'
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should return 400 validation error
    assert response.status_code == 400

    data = response.get_json()
    assert data['error'] == 'POULTRY_TEMP_UNSAFE'


def test_start_cook_device_offline(client, auth_headers, mock_websocket_client_offline, monkeypatch):
    """Test start cook when device is offline."""
    # Inject mock client (offline)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_offline)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should return 503 device offline
    assert response.status_code == 503

    data = response.get_json()
    assert data['error'] == 'DEVICE_OFFLINE'


def test_start_cook_device_busy(client, auth_headers, mock_websocket_client_busy, monkeypatch):
    """Test start cook when device is already cooking."""
    # Inject mock client (busy)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_busy)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should return 409 device busy
    assert response.status_code == 409

    data = response.get_json()
    assert data['error'] == 'DEVICE_BUSY'


def test_start_cook_missing_temperature(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with missing required field."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Missing temperature_celsius
    request_data = {
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should return 400 validation error
    assert response.status_code == 400

    data = response.get_json()
    assert data['error'] == 'MISSING_TEMPERATURE'


def test_start_cook_empty_body(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with empty request body."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Empty body
    response = client.post('/start-cook', headers=auth_headers, json={})

    # Should return 400 validation error
    assert response.status_code == 400

    data = response.get_json()
    assert 'error' in data


# ==============================================================================
# GET STATUS ENDPOINT TESTS
# ==============================================================================

def test_get_status_success_idle(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test successful status retrieval for idle device."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    response = client.get('/status', headers=auth_headers)

    # Verify response
    assert response.status_code == 200

    data = response.get_json()
    assert data['device_online'] is True
    assert data['state'] == 'idle'
    assert data['current_temp_celsius'] == 20.0
    assert data['target_temp_celsius'] is None
    assert data['time_remaining_minutes'] is None
    assert data['time_elapsed_minutes'] is None
    assert data['is_running'] is False

    # Verify client was called
    mock_websocket_client.get_status.assert_called_once()


def test_get_status_success_cooking(client, auth_headers, mock_websocket_client_busy, monkeypatch):
    """Test successful status retrieval for cooking device."""
    # Inject mock client (busy = cooking)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_busy)

    response = client.get('/status', headers=auth_headers)

    # Verify response
    assert response.status_code == 200

    data = response.get_json()
    assert data['device_online'] is True
    assert data['state'] == 'cooking'
    assert data['current_temp_celsius'] == 64.8
    assert data['target_temp_celsius'] == 65.0
    assert data['time_remaining_minutes'] == 45
    assert data['time_elapsed_minutes'] == 45
    assert data['is_running'] is True


def test_get_status_missing_auth(client, mock_websocket_client, monkeypatch):
    """Test status retrieval fails without authentication."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # No Authorization header
    response = client.get('/status')

    # Should return 401
    assert response.status_code == 401

    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'


def test_get_status_device_offline(client, auth_headers, mock_websocket_client_offline, monkeypatch):
    """Test status retrieval when device is offline."""
    # Inject mock client (offline)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_offline)

    response = client.get('/status', headers=auth_headers)

    # Should return 503 device offline
    assert response.status_code == 503

    data = response.get_json()
    assert data['error'] == 'DEVICE_OFFLINE'


# ==============================================================================
# STOP COOK ENDPOINT TESTS
# ==============================================================================

def test_stop_cook_success(client, auth_headers, mock_websocket_client_busy, monkeypatch):
    """Test successful cook stop."""
    # Inject mock client (busy = has active cook)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_busy)

    response = client.post('/stop-cook', headers=auth_headers)

    # Verify response
    assert response.status_code == 200

    data = response.get_json()
    assert data['success'] is True
    assert data['device_state'] == 'idle'
    assert 'final_temp_celsius' in data

    # Verify client was called
    mock_websocket_client_busy.stop_cook.assert_called_once()


def test_stop_cook_missing_auth(client, mock_websocket_client, monkeypatch):
    """Test stop cook fails without authentication."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # No Authorization header
    response = client.post('/stop-cook')

    # Should return 401
    assert response.status_code == 401

    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'


def test_stop_cook_no_active_cook(client, auth_headers, mock_websocket_client_no_active_cook, monkeypatch):
    """Test stop cook when no cook is active."""
    # Inject mock client (no active cook)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_no_active_cook)

    response = client.post('/stop-cook', headers=auth_headers)

    # Should return 409 no active cook
    assert response.status_code == 409

    data = response.get_json()
    assert data['error'] == 'NO_ACTIVE_COOK'


def test_stop_cook_device_offline(client, auth_headers, mock_websocket_client_offline, monkeypatch):
    """Test stop cook when device is offline."""
    # Inject mock client (offline)
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client_offline)

    response = client.post('/stop-cook', headers=auth_headers)

    # Should return 503 device offline
    assert response.status_code == 503

    data = response.get_json()
    assert data['error'] == 'DEVICE_OFFLINE'


# ==============================================================================
# ERROR FORMAT TESTS
# ==============================================================================

def test_error_response_format(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test that error responses have consistent format."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Trigger validation error
    request_data = {
        'temperature_celsius': 35.0,  # Too low
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Verify error format
    data = response.get_json()
    assert 'error' in data  # Error code
    assert 'message' in data  # Human-readable message
    assert isinstance(data['error'], str)
    assert isinstance(data['message'], str)


def test_success_response_format(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test that success responses have consistent format."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Verify success format
    data = response.get_json()
    assert isinstance(data, dict)
    assert 'success' in data or 'status' in data  # Has success indicator
    # No 'error' key in success response
    assert 'error' not in data


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

def test_start_cook_with_edge_case_temperatures(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with boundary temperatures."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Test minimum temperature (40.0°C)
    request_data = {
        'temperature_celsius': 40.0,
        'time_minutes': 60
    }
    response = client.post('/start-cook', headers=auth_headers, json=request_data)
    assert response.status_code == 200

    # Test maximum temperature (100.0°C)
    request_data = {
        'temperature_celsius': 100.0,
        'time_minutes': 60
    }
    response = client.post('/start-cook', headers=auth_headers, json=request_data)
    assert response.status_code == 200


def test_start_cook_with_edge_case_times(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with boundary times."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # Test minimum time (1 minute)
    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 1
    }
    response = client.post('/start-cook', headers=auth_headers, json=request_data)
    assert response.status_code == 200

    # Test maximum time (5999 minutes)
    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 5999
    }
    response = client.post('/start-cook', headers=auth_headers, json=request_data)
    assert response.status_code == 200


def test_start_cook_with_float_time(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with float time gets truncated to int."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90.7  # Float
    }

    response = client.post('/start-cook', headers=auth_headers, json=request_data)

    # Should succeed
    assert response.status_code == 200

    # Verify time was truncated (client called with int)
    mock_websocket_client.start_cook.assert_called_once()
    call_args = mock_websocket_client.start_cook.call_args
    assert call_args.kwargs['time_minutes'] == 90  # Truncated to int


# ==============================================================================
# CONTENT TYPE TESTS
# ==============================================================================

def test_start_cook_with_json_content_type(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook with explicit JSON content type."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    request_data = {
        'temperature_celsius': 65.0,
        'time_minutes': 90
    }

    # Add Content-Type header
    headers = {**auth_headers, 'Content-Type': 'application/json'}

    response = client.post('/start-cook', headers=headers, json=request_data)

    # Should succeed
    assert response.status_code == 200


def test_start_cook_without_json_body(client, auth_headers, mock_websocket_client, monkeypatch):
    """Test start cook without JSON body."""
    # Inject mock client
    monkeypatch.setitem(client.application.config, 'ANOVA_CLIENT', mock_websocket_client)

    # No JSON body
    response = client.post('/start-cook', headers=auth_headers)

    # Should return 400 validation error
    assert response.status_code == 400


# ==============================================================================
# IMPLEMENTATION NOTES
# ==============================================================================
# Route integration tests complete!
#
# All tests implemented:
# - Health check endpoint (no auth, always works)
# - Start cook endpoint:
#   - Success with valid parameters
#   - Authentication (missing, invalid)
#   - Validation errors (temp too low, unsafe poultry, missing fields, empty body)
#   - Device errors (offline, busy)
#   - Edge cases (boundary temps, boundary times, float time)
#   - Content type handling
# - Get status endpoint:
#   - Success (idle, cooking)
#   - Authentication (missing)
#   - Device offline
# - Stop cook endpoint:
#   - Success
#   - Authentication (missing)
#   - No active cook
#   - Device offline
# - Error/success response format consistency
#
# Coverage:
# - All endpoints tested
# - Authentication enforcement
# - Validation error propagation
# - WebSocket client error propagation
# - Response format validation
# - Edge cases and boundary conditions
#
# Reference: CLAUDE.md Section "API Endpoints Reference"
# Reference: WebSocket migration plan Section "Testing Strategy"
