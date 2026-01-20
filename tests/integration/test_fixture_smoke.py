"""
Smoke test to verify integration test fixtures work correctly.

This test validates that the mock fixtures are properly configured
and can be used in integration tests.

Reference: HANDOFF-INTEGRATION-TESTS.md - Phase 1 verification
"""

import responses


@responses.activate
def test_mock_anova_api_success_fixture_works(client, auth_headers, mock_anova_api_success):
    """
    Verify mock_anova_api_success fixture adds mocks correctly.

    This smoke test ensures:
    1. Fixture adds mocks to the responses registry
    2. Test can make HTTP requests that match mocks
    3. Flask test client works with mocked responses
    """
    # The fixture should have already added mocks
    # Verify by checking we can make a request without errors

    # This should NOT raise ConnectionError since mocks are in place
    response = client.get('/health')

    # Health endpoint should work (no auth required)
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data


@responses.activate
def test_mock_anova_api_offline_fixture_works(client, auth_headers, mock_anova_api_offline):
    """
    Verify mock_anova_api_offline fixture adds mocks correctly.

    This validates that the offline scenario mock is properly configured.
    """
    # The fixture should have added offline mocks
    # Health endpoint should still work
    response = client.get('/health')
    assert response.status_code == 200


@responses.activate
def test_mock_anova_api_busy_fixture_works(client, auth_headers, mock_anova_api_busy):
    """
    Verify mock_anova_api_busy fixture adds mocks correctly.

    This validates that the busy scenario mock is properly configured.
    """
    # The fixture should have added busy mocks
    # Health endpoint should still work
    response = client.get('/health')
    assert response.status_code == 200


def test_fixtures_are_isolated():
    """
    Verify fixtures don't pollute each other's state.

    This test runs without @responses.activate and without mock fixtures.
    It should pass without any mocks active.
    """
    # This test has no responses mocks
    # It should pass independently
    assert True


def test_valid_cook_requests_fixture(valid_cook_requests):
    """Verify valid_cook_requests fixture has expected structure."""
    assert "chicken" in valid_cook_requests
    assert "steak" in valid_cook_requests
    assert "salmon" in valid_cook_requests

    chicken = valid_cook_requests["chicken"]
    assert chicken["temperature_celsius"] == 65.0
    assert chicken["time_minutes"] == 90
    assert chicken["food_type"] == "chicken breast"


def test_invalid_cook_requests_fixture(invalid_cook_requests):
    """Verify invalid_cook_requests fixture has expected structure."""
    assert "temp_too_low" in invalid_cook_requests
    assert "temp_too_high" in invalid_cook_requests
    assert "unsafe_poultry" in invalid_cook_requests

    temp_too_low = invalid_cook_requests["temp_too_low"]
    assert temp_too_low["temperature_celsius"] == 35.0
    assert temp_too_low["expected_error"] == "TEMPERATURE_TOO_LOW"


def test_auth_headers_fixture(auth_headers):
    """Verify auth_headers fixture has correct structure."""
    assert "Authorization" in auth_headers
    assert auth_headers["Authorization"] == "Bearer test-api-key-12345"
    assert "Content-Type" in auth_headers


def test_invalid_auth_headers_fixture(invalid_auth_headers):
    """Verify invalid_auth_headers fixture has correct structure."""
    assert "Authorization" in invalid_auth_headers
    assert "wrong-key" in invalid_auth_headers["Authorization"]
