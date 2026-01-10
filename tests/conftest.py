"""
Pytest fixtures for testing.

Shared fixtures available to all test files:
- app: Flask application instance for testing
- client: Flask test client for making requests
- auth_headers: Valid authentication headers
- valid_cook_request: Valid cook request data
- invalid_temp_request: Invalid temperature data (for testing validation)

Reference: CLAUDE.md Section "Testing Strategy"
"""

import pytest
from typing import Dict, Any
from flask.testing import FlaskClient

# These imports will work once the modules are implemented
# from server.app import create_app


@pytest.fixture
def app():
    """
    Create Flask application for testing.

    Returns:
        Flask app configured for testing

    TODO: Implement from test examples in CLAUDE.md
    TODO: Import create_app from server.app
    TODO: Create app with test config (TESTING=True, DEBUG=True)
    TODO: Set test API_KEY, device config
    TODO: Yield app for tests
    TODO: Teardown after tests complete

    Example:
        def test_something(app):
            assert app.config['TESTING'] is True

    Reference: pytest-flask documentation
    """
    raise NotImplementedError("app fixture not yet implemented")


@pytest.fixture
def client(app) -> FlaskClient:
    """
    Create Flask test client.

    Args:
        app: Flask application fixture

    Returns:
        Flask test client for making HTTP requests

    TODO: Implement test client fixture
    TODO: Return app.test_client()

    Example:
        def test_health(client):
            response = client.get('/health')
            assert response.status_code == 200

    Reference: Flask testing documentation
    """
    raise NotImplementedError("client fixture not yet implemented")


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """
    Valid authentication headers for testing.

    Returns:
        Dict with Authorization header containing valid API key

    TODO: Implement auth headers fixture
    TODO: Return {"Authorization": "Bearer test-api-key"}
    TODO: Ensure API key matches what's configured in app fixture

    Example:
        def test_start_cook(client, auth_headers):
            response = client.post('/start-cook', headers=auth_headers, json={...})
            assert response.status_code == 200
    """
    raise NotImplementedError("auth_headers fixture not yet implemented")


@pytest.fixture
def valid_cook_request() -> Dict[str, Any]:
    """
    Valid cook request data for testing.

    Returns:
        Dict with valid temperature, time, and food_type

    TODO: Implement valid request data
    TODO: Return {"temperature_celsius": 65.0, "time_minutes": 90, "food_type": "chicken"}

    Example:
        def test_validation_passes(valid_cook_request):
            result = validate_start_cook(valid_cook_request)
            assert result['temperature_celsius'] == 65.0
    """
    raise NotImplementedError("valid_cook_request fixture not yet implemented")


@pytest.fixture
def invalid_temp_request() -> Dict[str, Any]:
    """
    Invalid temperature request data (for testing validation failures).

    Returns:
        Dict with temperature below minimum (39.9°C)

    TODO: Implement invalid request data
    TODO: Return {"temperature_celsius": 39.9, "time_minutes": 90}

    Example:
        def test_validation_fails(invalid_temp_request):
            with pytest.raises(ValidationError):
                validate_start_cook(invalid_temp_request)
    """
    raise NotImplementedError("invalid_temp_request fixture not yet implemented")


@pytest.fixture
def mock_anova_client(monkeypatch):
    """
    Mock Anova client to avoid real API calls in tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Mock AnovaClient instance

    TODO: Implement mock client
    TODO: Create mock class with start_cook, get_status, stop_cook methods
    TODO: Patch server.anova_client.AnovaClient with mock
    TODO: Return mock instance

    Example:
        def test_start_cook(client, auth_headers, mock_anova_client):
            # Test will use mock instead of real Anova API
            response = client.post('/start-cook', headers=auth_headers, json={...})

    Reference: CLAUDE.md Section "Testing Strategy > Mocking Anova API"
    """
    raise NotImplementedError("mock_anova_client fixture not yet implemented")


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
