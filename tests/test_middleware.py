"""
Unit tests for middleware (authentication, logging, error handling).

Tests all middleware functionality:
- API key authentication (missing, invalid, valid)
- Constant-time comparison (timing attack prevention)
- Request/response logging (no secrets logged)
- Error handlers (exception → HTTP status mapping)

Test coverage goal: >80%

Reference: CLAUDE.md Section "Code Patterns > 3. Authentication Pattern"
Reference: docs/03-component-architecture.md Section 4.1.3 (COMP-MW-01)
"""

import time

import pytest
from flask import Flask, request

from server.exceptions import (
    AnovaAPIError,
    AuthenticationError,
    DeviceBusyError,
    DeviceOfflineError,
    NoActiveCookError,
    ValidationError,
)
from server.middleware import register_error_handlers, require_api_key, setup_request_logging

# ==============================================================================
# TEST FIXTURES
# ==============================================================================


@pytest.fixture
def test_app():
    """Create Flask app for testing middleware."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["API_KEY"] = "test-api-key-12345"

    # Register middleware
    register_error_handlers(app)

    return app


@pytest.fixture
def client(test_app):
    """Create Flask test client."""
    return test_app.test_client()


@pytest.fixture
def app_with_logging(test_app):
    """App with request logging enabled."""
    setup_request_logging(test_app)
    return test_app


@pytest.fixture
def app_with_protected_route(test_app):
    """App with a protected route for testing @require_api_key."""

    @test_app.route("/protected", methods=["GET"])
    @require_api_key
    def protected_route():
        return {"message": "success"}, 200

    return test_app


# ==============================================================================
# AUTHENTICATION TESTS
# ==============================================================================


def test_require_api_key_missing_header(app_with_protected_route):
    """TC-MW-01: Request without Authorization header returns 401."""
    client = app_with_protected_route.test_client()

    response = client.get("/protected")

    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "UNAUTHORIZED"
    assert "Authorization" in data["message"] or "Missing" in data["message"]


def test_require_api_key_invalid_format(app_with_protected_route):
    """TC-MW-02: Request with invalid Authorization format returns 401."""
    client = app_with_protected_route.test_client()

    # Test various invalid formats
    invalid_headers = [
        {"Authorization": "test-api-key-12345"},  # Missing "Bearer"
        {"Authorization": "Basic test-api-key-12345"},  # Wrong scheme
        {"Authorization": "Bearer"},  # No token
        {"Authorization": ""},  # Empty
    ]

    for headers in invalid_headers:
        response = client.get("/protected", headers=headers)
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "UNAUTHORIZED"


def test_require_api_key_wrong_key(app_with_protected_route):
    """TC-MW-03: Request with wrong API key returns 401."""
    client = app_with_protected_route.test_client()

    headers = {"Authorization": "Bearer wrong-key"}
    response = client.get("/protected", headers=headers)

    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "UNAUTHORIZED"


def test_require_api_key_correct_key(app_with_protected_route):
    """TC-MW-04: Request with correct API key succeeds."""
    client = app_with_protected_route.test_client()

    headers = {"Authorization": "Bearer test-api-key-12345"}
    response = client.get("/protected", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "success"


def test_require_api_key_constant_time_comparison():
    """TC-MW-05: API key comparison uses constant-time algorithm.

    This test verifies timing attack prevention by measuring
    comparison times for keys that match/mismatch at different positions.

    While not a perfect test (system variance exists), significantly
    different timings would indicate non-constant-time comparison.
    """
    app = Flask(__name__)
    app.config["API_KEY"] = "correct-key-1234567890"

    @app.route("/test")
    @require_api_key
    def test_route():
        return {"ok": True}

    client = app.test_client()

    # Keys that mismatch at different positions
    early_mismatch = "Bearer x" + "orrect-key-1234567890"[1:]  # First char wrong
    late_mismatch = "Bearer correct-key-123456789x"  # Last char wrong

    # Measure timing for early mismatch
    start = time.perf_counter()
    for _ in range(100):
        client.get("/test", headers={"Authorization": early_mismatch})
    early_time = time.perf_counter() - start

    # Measure timing for late mismatch
    start = time.perf_counter()
    for _ in range(100):
        client.get("/test", headers={"Authorization": late_mismatch})
    late_time = time.perf_counter() - start

    # If using constant-time comparison (hmac.compare_digest),
    # timings should be similar regardless of mismatch position
    # Allow 50% variance for system noise
    ratio = max(early_time, late_time) / min(early_time, late_time)
    assert ratio < 1.5, f"Timing attack vulnerability detected: {ratio:.2f}x difference"


# ==============================================================================
# LOGGING TESTS
# ==============================================================================


def test_request_logging_no_secrets(app_with_logging, caplog):
    """TC-MW-06: Request logging does not log sensitive data."""

    @app_with_logging.route("/test", methods=["POST"])
    def test_route():
        return {"ok": True}

    client = app_with_logging.test_client()

    # Send request with sensitive data
    headers = {"Authorization": "Bearer secret-token-12345", "X-Custom": "some-value"}
    data = {"password": "secret-password", "email": "user@example.com"}

    with caplog.at_level("INFO"):
        response = client.post("/test", headers=headers, json=data)

    # Verify request was logged
    assert any("POST" in record.message and "/test" in record.message for record in caplog.records)

    # Verify sensitive data NOT logged
    log_output = " ".join(record.message for record in caplog.records)
    assert "secret-token-12345" not in log_output
    assert "secret-password" not in log_output
    assert "Authorization" not in log_output
    assert "Bearer" not in log_output


def test_response_logging_includes_duration(app_with_logging, caplog):
    """TC-MW-07: Response logging includes request duration."""

    @app_with_logging.route("/test")
    def test_route():
        time.sleep(0.01)  # Small delay to ensure measurable duration
        return {"ok": True}

    client = app_with_logging.test_client()

    with caplog.at_level("INFO"):
        response = client.get("/test")

    # Find response log entry
    response_logs = [r.message for r in caplog.records if "200" in r.message]
    assert len(response_logs) > 0

    # Verify duration is logged (format: "→ 200 (0.XXXs)")
    assert any("s)" in log or "duration" in log.lower() for log in response_logs)


def test_logging_safe_on_error(app_with_logging, caplog):
    """TC-MW-08: Logging doesn't expose secrets even on errors."""

    @app_with_logging.route("/error")
    def error_route():
        # Simulate error with sensitive data in context
        raise ValidationError("TEST_ERROR", "Test error message")

    client = app_with_logging.test_client()
    headers = {"Authorization": "Bearer secret-key"}

    with caplog.at_level("WARNING"):
        response = client.get("/error", headers=headers)

    log_output = " ".join(record.message for record in caplog.records)
    assert "secret-key" not in log_output
    assert "Authorization" not in log_output


# ==============================================================================
# ERROR HANDLER TESTS
# ==============================================================================


def test_validation_error_returns_400(test_app):
    """TC-MW-09: ValidationError mapped to 400 Bad Request."""

    @test_app.route("/test")
    def test_route():
        raise ValidationError("TEMPERATURE_TOO_LOW", "Temperature below minimum")

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "TEMPERATURE_TOO_LOW"
    assert data["message"] == "Temperature below minimum"


def test_device_offline_returns_503(test_app):
    """TC-MW-10: DeviceOfflineError mapped to 503 Service Unavailable."""

    @test_app.route("/test")
    def test_route():
        raise DeviceOfflineError("Device is not reachable")

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 503
    data = response.get_json()
    assert data["error"] == "DEVICE_OFFLINE"
    assert data["message"] == "Device is not reachable"
    assert "retry_after" in data
    assert data["retry_after"] == 60


def test_device_busy_returns_409(test_app):
    """TC-MW-11: DeviceBusyError mapped to 409 Conflict."""

    @test_app.route("/test")
    def test_route():
        raise DeviceBusyError("Device is already cooking")

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 409
    data = response.get_json()
    assert data["error"] == "DEVICE_BUSY"
    assert data["message"] == "Device is already cooking"


def test_no_active_cook_returns_409(test_app):
    """TC-MW-12: NoActiveCookError mapped to 409 Conflict.

    Updated from 404 to 409 per API spec (05-api-specification.md line 266).
    409 Conflict is more accurate than 404 Not Found because the endpoint exists,
    but the request conflicts with the current state (no active cook to stop).
    """

    @test_app.route("/test")
    def test_route():
        raise NoActiveCookError("No active cook session")

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 409
    data = response.get_json()
    assert data["error"] == "NO_ACTIVE_COOK"
    assert data["message"] == "No active cook session"


def test_authentication_error_returns_500(test_app):
    """TC-MW-13: AuthenticationError mapped to 500 Internal Server Error."""

    @test_app.route("/test")
    def test_route():
        raise AuthenticationError("Firebase auth failed")

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 500
    data = response.get_json()
    assert data["error"] == "AUTHENTICATION_ERROR"
    assert data["message"] == "Firebase auth failed"


def test_anova_api_error_returns_custom_status(test_app):
    """TC-MW-14: AnovaAPIError uses custom status code."""

    @test_app.route("/test")
    def test_route():
        raise AnovaAPIError("API timeout", status_code=502)

    client = test_app.test_client()
    response = client.get("/test")

    assert response.status_code == 502
    data = response.get_json()
    assert data["error"] == "ANOVA_API_ERROR"
    assert data["message"] == "API timeout"


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================


def test_middleware_integration(app_with_logging):
    """TC-MW-15: All middleware components work together."""

    @app_with_logging.route("/integrated", methods=["POST"])
    @require_api_key
    def integrated_route():
        # Validate input (raises ValidationError on failure)
        data = request.get_json()
        if data.get("temp", 0) < 40:
            raise ValidationError("TEMPERATURE_TOO_LOW", "Too cold")
        return {"status": "ok"}

    client = app_with_logging.test_client()

    # Test 1: No auth → 401
    response = client.post("/integrated", json={"temp": 65})
    assert response.status_code == 401

    # Test 2: Auth + validation error → 400
    headers = {"Authorization": "Bearer test-api-key-12345"}
    response = client.post("/integrated", headers=headers, json={"temp": 30})
    assert response.status_code == 400
    assert response.get_json()["error"] == "TEMPERATURE_TOO_LOW"

    # Test 3: Auth + valid data → 200
    response = client.post("/integrated", headers=headers, json={"temp": 65})
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
