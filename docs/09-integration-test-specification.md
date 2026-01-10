# 09 - Integration Test Specification

> **Document Type:** Integration Test Specification
> **Status:** Draft
> **Version:** 1.0
> **Last Updated:** 2025-01-10
> **Depends On:** 01-System Context, 03-Component Architecture, 05-API Specification
> **Blocks:** Implementation, TDD Development

---

## 1. Overview

### 1.1 Purpose

This document specifies comprehensive integration tests for the Anova AI Sous Vide Assistant. Integration tests validate end-to-end flows through the system, ensuring components work correctly together from HTTP request to device command.

**Integration testing validates:**
- Request/response flows through all layers (API → Service → Integration)
- Component interactions and data transformations
- Error propagation from lower layers to HTTP responses
- State transitions and consistency
- API contract compliance

**Key Principles:**
- **Test behavior, not implementation** - Focus on inputs/outputs, not internal mechanics
- **Mock external dependencies** - Avoid real Anova API calls; use controlled mocks
- **Isolate failures** - Each test should identify exactly what failed
- **Deterministic execution** - Tests must produce same results every run
- **Fast feedback** - Full integration suite should complete in < 30 seconds

### 1.2 Scope

**In Scope:**
- End-to-end HTTP request → response flows
- Validation integration with route handlers
- Anova client integration with routes
- Error handling across component boundaries
- State machine transitions (device states)
- API response schema validation
- Authentication middleware integration
- Concurrent request handling

**Out of Scope:**
- Unit tests for individual functions (see test_validators.py, etc.)
- Manual/exploratory testing
- Performance/load testing (separate specification)
- Real Anova API integration (manual testing only)
- UI/frontend testing (no UI in MVP)

### 1.3 Integration Points

| Integration Point | Components Involved | Test Focus |
|-------------------|---------------------|------------|
| **API → Validator** | routes.py → validators.py | Input validation before processing |
| **API → Client** | routes.py → anova_client.py | Device command execution |
| **Validator → Routes** | validators.py → routes.py (error handling) | Validation errors mapped to HTTP 400 |
| **Client → Routes** | anova_client.py → routes.py (error handling) | Anova errors mapped to HTTP 503/502 |
| **Middleware → Routes** | middleware.py → routes.py | Authentication enforcement |
| **Config → Components** | config.py → all components | Configuration injection |

### 1.4 Test Environment Requirements

**Software Requirements:**
- Python 3.11+
- pytest 7+
- pytest-flask 1+
- responses 0.24+ (HTTP mocking)
- Flask test client

**Test Infrastructure:**
- In-memory Flask application (no persistent storage needed)
- Mocked Anova Cloud API (no real API calls)
- Test configuration (separate from production)
- Pytest fixtures for setup/teardown

**Test Data Requirements:**
- Valid cook requests (chicken, steak, salmon)
- Invalid cook requests (unsafe temps, out-of-range values)
- Anova API mock responses (success, errors, offline)
- Authentication tokens (valid/invalid)

---

## 2. Test Environment Setup

### 2.1 Test Configuration

```python
# tests/test_config.py

TEST_CONFIG = {
    "TESTING": True,
    "DEBUG": True,
    "ANOVA_EMAIL": "test@example.com",
    "ANOVA_PASSWORD": "test-password",
    "DEVICE_ID": "test-device-123",
    "API_KEY": "test-api-key-12345",
    "HOST": "127.0.0.1",
    "PORT": 5000,
}
```

### 2.2 Flask App Fixture

```python
# tests/conftest.py

import pytest
from server.app import create_app
from server.config import Config

@pytest.fixture
def app():
    """Create Flask application configured for testing."""
    # Create test configuration
    config = Config(**TEST_CONFIG)

    # Create app with test config
    app = create_app(config)

    # Additional test setup
    app.config['TESTING'] = True

    yield app

    # Cleanup after tests (if needed)

@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()
```

### 2.3 Authentication Fixtures

```python
# tests/conftest.py

@pytest.fixture
def auth_headers():
    """Valid authentication headers for testing."""
    return {
        "Authorization": "Bearer test-api-key-12345",
        "Content-Type": "application/json"
    }

@pytest.fixture
def invalid_auth_headers():
    """Invalid authentication headers for testing."""
    return {
        "Authorization": "Bearer wrong-key",
        "Content-Type": "application/json"
    }
```

### 2.4 Test Data Fixtures

```python
# tests/conftest.py

@pytest.fixture
def valid_cook_requests():
    """Collection of valid cook requests for testing."""
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
    """Collection of invalid cook requests for testing validation."""
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
```

### 2.5 Anova API Mock Strategy

**Mocking Approach:**
- Use `responses` library to mock HTTP requests to Anova Cloud
- Mock Firebase authentication endpoints
- Mock Anova device API endpoints
- Provide fixtures for different scenarios (success, offline, busy, auth failure)

```python
# tests/conftest.py

import responses
import pytest

@pytest.fixture
def mock_anova_api_success():
    """Mock successful Anova API responses."""
    @responses.activate
    def _mock():
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

        # Mock device status (idle)
        responses.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "idle",
                "current_temperature": 22.5,
                "target_temperature": None,
                "timer_remaining": None
            },
            status=200
        )

        # Mock start cook command
        responses.add(
            responses.POST,
            "https://anovaculinary.io/api/v1/devices/test-device-123/start",
            json={
                "success": True,
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

    return _mock

@pytest.fixture
def mock_anova_api_offline():
    """Mock device offline scenario."""
    @responses.activate
    def _mock():
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

    return _mock

@pytest.fixture
def mock_anova_api_busy():
    """Mock device already cooking scenario."""
    @responses.activate
    def _mock():
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

    return _mock
```

---

## 3. Integration Test Scenarios

### 3.1 Happy Path Scenarios

#### INT-01: Complete Cook Cycle Success

**Component ID:** INT-01
**Validates Requirements:** FR-01, FR-02, FR-03, QR-01
**Test Type:** Happy path

**Scenario Description:**
User successfully starts a cook, checks status, and stops the cook. This validates the entire workflow from start to finish with all components working correctly.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API returning success responses
3. Valid authentication headers
4. Valid cook request data (chicken at 65°C for 90 minutes)

**Test Steps:**
```python
def test_int_01_complete_cook_cycle_success(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """INT-01: Complete cook cycle from start to stop."""

    # Step 1: Start cook
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["target_temp_celsius"] == 65.0
    assert data["time_minutes"] == 90
    assert data["device_state"] in ["preheating", "cooking"]
    assert "cook_id" in data

    # Step 2: Check status
    response = client.get('/status', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["device_online"] is True
    assert data["is_running"] is True
    assert data["current_temp_celsius"] > 0

    # Step 3: Stop cook
    response = client.post('/stop-cook', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["device_state"] == "idle"
```

**Expected Results:**
- All three operations succeed with 200 status
- Start cook returns success with cook metadata
- Status returns running state with temperature info
- Stop cook transitions device to idle state
- No exceptions raised
- Response schemas match API specification

**Failure Criteria:**
- Any HTTP status other than 200
- Missing required fields in responses
- Incorrect state transitions
- Exceptions or crashes

**Cleanup:**
- No cleanup needed (mocks are isolated per test)

---

#### INT-02: Validation Rejection Flow

**Component ID:** INT-02
**Validates Requirements:** FR-04, FR-05, FR-07, FR-08
**Test Type:** Happy path (for validation)

**Scenario Description:**
User attempts to start cook with invalid temperature. Validator rejects the request before any Anova API call is made. This validates that validation happens first and prevents invalid commands.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API configured but should NOT be called
3. Valid authentication headers
4. Invalid cook request (temperature too low)

**Test Steps:**
```python
def test_int_02_validation_rejection_flow(client, auth_headers, invalid_cook_requests, mock_anova_api_success):
    """INT-02: Validation rejects request before calling Anova API."""

    # Attempt to start cook with invalid temperature
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 35.0, "time_minutes": 60}
    )

    # Verify validation rejection
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "TEMPERATURE_TOO_LOW"
    assert "danger zone" in data["message"].lower()

    # Verify Anova API was NOT called
    # (responses library will raise error if unexpected call is made)
```

**Expected Results:**
- HTTP 400 Bad Request returned
- Error code is TEMPERATURE_TOO_LOW
- Message explains why temperature is unsafe
- No call made to Anova API (verified by responses library)

**Failure Criteria:**
- Status code other than 400
- Wrong error code
- Anova API called despite invalid input
- Missing or unclear error message

**Cleanup:**
- No cleanup needed

---

### 3.2 Error Path Scenarios

#### INT-03: Device Offline During Start

**Component ID:** INT-03
**Validates Requirements:** FR-06, QR-13
**Test Type:** Error path

**Scenario Description:**
User attempts to start cook but device is offline. System detects offline status and returns helpful error without crashing.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API returning device offline (404 or online=false)
3. Valid authentication headers
4. Valid cook request data

**Test Steps:**
```python
def test_int_03_device_offline_during_start(client, auth_headers, valid_cook_requests, mock_anova_api_offline):
    """INT-03: Device offline scenario returns 503 error."""

    # Attempt to start cook with device offline
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    # Verify offline error
    assert response.status_code == 503
    data = response.get_json()
    assert data["error"] == "DEVICE_OFFLINE"
    assert "offline" in data["message"].lower() or "wifi" in data["message"].lower()
```

**Expected Results:**
- HTTP 503 Service Unavailable returned
- Error code is DEVICE_OFFLINE
- Message provides actionable guidance (check WiFi)
- Application does not crash

**Failure Criteria:**
- Status code other than 503
- Application crashes or raises unhandled exception
- Error message not helpful

**Cleanup:**
- No cleanup needed

---

#### INT-04: Device Busy (Already Cooking)

**Component ID:** INT-04
**Validates Requirements:** FR-01
**Test Type:** Error path

**Scenario Description:**
User attempts to start cook while device is already cooking. System detects busy state and returns conflict error.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API returning device already cooking (409)
3. Valid authentication headers
4. Valid cook request data

**Test Steps:**
```python
def test_int_04_device_busy_already_cooking(client, auth_headers, valid_cook_requests, mock_anova_api_busy):
    """INT-04: Starting cook when already cooking returns 409."""

    # Attempt to start cook when device is busy
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["steak"]
    )

    # Verify conflict error
    assert response.status_code == 409
    data = response.get_json()
    assert data["error"] == "DEVICE_BUSY"
    assert "already" in data["message"].lower() or "active" in data["message"].lower()
```

**Expected Results:**
- HTTP 409 Conflict returned
- Error code is DEVICE_BUSY
- Message explains device has active session
- Suggests stopping current cook first

**Failure Criteria:**
- Status code other than 409
- Allows multiple simultaneous cooks
- Unclear error message

**Cleanup:**
- No cleanup needed

---

#### INT-05: Authentication Failure

**Component ID:** INT-05
**Validates Requirements:** QR-33, SEC-INV-03
**Test Type:** Error path

**Scenario Description:**
User attempts request with invalid or missing authentication. Middleware rejects before any processing.

**Test Setup:**
1. Flask app with test configuration
2. Invalid or missing authentication headers
3. Valid cook request data

**Test Steps:**
```python
def test_int_05_authentication_failure(client, valid_cook_requests):
    """INT-05: Missing or invalid auth returns 401."""

    # Test 1: Missing Authorization header
    response = client.post(
        '/start-cook',
        json=valid_cook_requests["chicken"]
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "UNAUTHORIZED"

    # Test 2: Invalid API key
    response = client.post(
        '/start-cook',
        headers={"Authorization": "Bearer wrong-key"},
        json=valid_cook_requests["chicken"]
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "UNAUTHORIZED"

    # Test 3: Malformed Authorization header
    response = client.post(
        '/start-cook',
        headers={"Authorization": "InvalidFormat"},
        json=valid_cook_requests["chicken"]
    )
    assert response.status_code == 401
```

**Expected Results:**
- All invalid auth attempts return HTTP 401
- Error code is UNAUTHORIZED
- No processing happens without valid auth
- Health endpoint (/health) still works without auth

**Failure Criteria:**
- Allows requests without authentication
- Status code other than 401
- Health endpoint requires auth (should not)

**Cleanup:**
- No cleanup needed

---

### 3.3 Edge Case Scenarios

#### INT-06: Stop Cook with No Active Session

**Component ID:** INT-06
**Validates Requirements:** FR-03
**Test Type:** Edge case

**Scenario Description:**
User attempts to stop cook when device is idle (no active session). System returns appropriate error without crashing.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API returning idle state
3. Valid authentication headers

**Test Steps:**
```python
def test_int_06_stop_cook_no_active_session(client, auth_headers, mock_anova_api_success):
    """INT-06: Stopping when idle returns 409 NO_ACTIVE_COOK."""

    # Attempt to stop when device is idle
    response = client.post('/stop-cook', headers=auth_headers)

    # Verify appropriate error
    assert response.status_code == 409
    data = response.get_json()
    assert data["error"] == "NO_ACTIVE_COOK"
    assert "no active" in data["message"].lower() or "not cooking" in data["message"].lower()
```

**Expected Results:**
- HTTP 409 Conflict returned
- Error code is NO_ACTIVE_COOK
- Message explains no session to stop
- System remains stable

**Failure Criteria:**
- Status code other than 409
- System crashes
- Confusing error message

**Cleanup:**
- No cleanup needed

---

#### INT-07: Token Refresh During Request

**Component ID:** INT-07
**Validates Requirements:** QR-10, QR-13
**Test Type:** Edge case

**Scenario Description:**
Anova authentication token expires mid-request. Client automatically refreshes token and retries operation transparently.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API that first returns 401 (expired), then succeeds on retry
3. Valid authentication headers
4. Valid cook request

**Test Steps:**
```python
def test_int_07_token_refresh_during_request(client, auth_headers, valid_cook_requests):
    """INT-07: Expired token auto-refreshes transparently."""

    with responses.RequestsMock() as rsps:
        # First auth attempt (expired token)
        rsps.add(
            responses.POST,
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            json={"idToken": "expired-token", "refreshToken": "refresh", "expiresIn": "0"},
            status=200
        )

        # First API call returns 401 (token expired)
        rsps.add(
            responses.POST,
            "https://anovaculinary.io/api/v1/devices/test-device-123/start",
            json={"error": "Unauthorized"},
            status=401
        )

        # Token refresh
        rsps.add(
            responses.POST,
            "https://securetoken.googleapis.com/v1/token",
            json={"id_token": "new-token", "refresh_token": "refresh", "expires_in": "3600"},
            status=200
        )

        # Retry succeeds
        rsps.add(
            responses.POST,
            "https://anovaculinary.io/api/v1/devices/test-device-123/start",
            json={"success": True, "state": "preheating"},
            status=200
        )

        # Execute request
        response = client.post(
            '/start-cook',
            headers=auth_headers,
            json=valid_cook_requests["chicken"]
        )

        # Verify success despite token expiry
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
```

**Expected Results:**
- Request succeeds despite token expiry
- Token refresh happens automatically
- User experiences no error
- Request completes within timeout

**Failure Criteria:**
- Request fails with 401
- Token not refreshed
- Infinite retry loop

**Cleanup:**
- No cleanup needed

---

#### INT-08: Concurrent Requests (Status + Start)

**Component ID:** INT-08
**Validates Requirements:** QR-01, QR-10
**Test Type:** Edge case

**Scenario Description:**
Two simultaneous requests (GET /status and POST /start-cook) are handled correctly without race conditions or crashes.

**Test Setup:**
1. Flask app with test configuration
2. Mock Anova API configured for both requests
3. Valid authentication headers
4. Valid cook request data

**Test Steps:**
```python
import threading

def test_int_08_concurrent_requests_status_and_start(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """INT-08: Concurrent status and start requests both succeed."""

    results = {}

    def get_status():
        response = client.get('/status', headers=auth_headers)
        results['status'] = response

    def start_cook():
        response = client.post(
            '/start-cook',
            headers=auth_headers,
            json=valid_cook_requests["chicken"]
        )
        results['start'] = response

    # Execute concurrently
    t1 = threading.Thread(target=get_status)
    t2 = threading.Thread(target=start_cook)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # Verify both succeeded
    assert results['status'].status_code == 200
    assert results['start'].status_code in [200, 409]  # 409 if already started
```

**Expected Results:**
- Both requests complete successfully
- No race conditions or deadlocks
- Response data is consistent
- No crashes or exceptions

**Failure Criteria:**
- One or both requests fail
- System crashes
- Deadlock or timeout
- Inconsistent data

**Cleanup:**
- No cleanup needed

---

## 4. State Transition Testing

### 4.1 Device State Machine

The device has the following states:
- **idle**: Not cooking, water at ambient temperature
- **preheating**: Heating water to target temperature
- **cooking**: At temperature, timer running
- **done**: Timer complete, maintaining temperature
- **offline**: Device not reachable

### 4.2 State Transition Tests

#### INT-ST-01: IDLE → PREHEATING (Start Cook)

```python
def test_int_st_01_idle_to_preheating(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """INT-ST-01: Starting cook transitions from idle to preheating."""

    # Verify initial state is idle
    response = client.get('/status', headers=auth_headers)
    assert response.get_json()["state"] == "idle"

    # Start cook
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )
    assert response.status_code == 200

    # Verify state is now preheating or cooking
    response = client.get('/status', headers=auth_headers)
    state = response.get_json()["state"]
    assert state in ["preheating", "cooking"]
```

---

#### INT-ST-02: PREHEATING → COOKING (Temperature Reached)

```python
def test_int_st_02_preheating_to_cooking(client, auth_headers):
    """INT-ST-02: Reaching target temp transitions to cooking."""

    # This test requires mock state progression
    # Mock sequence: preheating → preheating → cooking
    with responses.RequestsMock() as rsps:
        # Setup mock responses showing progression
        # First status call: preheating
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "preheating",
                "current_temperature": 50.0,
                "target_temperature": 65.0
            },
            status=200
        )

        # Second status call: cooking
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "cooking",
                "current_temperature": 65.0,
                "target_temperature": 65.0,
                "timer_remaining": 90
            },
            status=200
        )

        # Check status twice
        response1 = client.get('/status', headers=auth_headers)
        assert response1.get_json()["state"] == "preheating"

        response2 = client.get('/status', headers=auth_headers)
        assert response2.get_json()["state"] == "cooking"
```

---

#### INT-ST-03: COOKING → DONE (Timer Expires)

```python
def test_int_st_03_cooking_to_done(client, auth_headers):
    """INT-ST-03: Timer expiring transitions to done."""

    with responses.RequestsMock() as rsps:
        # Status call: cooking with time remaining
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "cooking",
                "current_temperature": 65.0,
                "target_temperature": 65.0,
                "timer_remaining": 5
            },
            status=200
        )

        # Status call: done
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "done",
                "current_temperature": 65.0,
                "target_temperature": 65.0,
                "timer_remaining": 0
            },
            status=200
        )

        # Check progression
        response1 = client.get('/status', headers=auth_headers)
        assert response1.get_json()["time_remaining_minutes"] == 5

        response2 = client.get('/status', headers=auth_headers)
        assert response2.get_json()["state"] == "done"
```

---

#### INT-ST-04: ANY → OFFLINE (Connection Lost)

```python
def test_int_st_04_any_to_offline(client, auth_headers):
    """INT-ST-04: Connection lost transitions to offline state."""

    with responses.RequestsMock() as rsps:
        # First call: device online
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "cooking",
                "current_temperature": 65.0
            },
            status=200
        )

        # Second call: device offline
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={"error": "Device offline"},
            status=404
        )

        # Check progression
        response1 = client.get('/status', headers=auth_headers)
        assert response1.get_json()["device_online"] is True

        response2 = client.get('/status', headers=auth_headers)
        assert response2.status_code == 503
        assert response2.get_json()["error"] == "DEVICE_OFFLINE"
```

---

#### INT-ST-05: COOKING → IDLE (Stop Cook)

```python
def test_int_st_05_cooking_to_idle(client, auth_headers):
    """INT-ST-05: Stopping cook transitions to idle."""

    with responses.RequestsMock() as rsps:
        # Status shows cooking
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "cooking",
                "current_temperature": 65.0
            },
            status=200
        )

        # Stop command succeeds
        rsps.add(
            responses.POST,
            "https://anovaculinary.io/api/v1/devices/test-device-123/stop",
            json={"success": True, "state": "idle"},
            status=200
        )

        # Status now shows idle
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={
                "online": True,
                "state": "idle",
                "current_temperature": 65.0
            },
            status=200
        )

        # Verify state transition
        response1 = client.get('/status', headers=auth_headers)
        assert response1.get_json()["state"] == "cooking"

        response2 = client.post('/stop-cook', headers=auth_headers)
        assert response2.get_json()["device_state"] == "idle"

        response3 = client.get('/status', headers=auth_headers)
        assert response3.get_json()["state"] == "idle"
```

---

## 5. API Contract Verification

### 5.1 Response Schema Validation

All API responses must match the schemas defined in 05-api-specification.md.

#### INT-API-01: Start Cook Response Schema

```python
def test_int_api_01_start_cook_response_schema(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """INT-API-01: Start cook response matches schema."""

    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    assert response.status_code == 200
    data = response.get_json()

    # Required fields
    assert "success" in data
    assert isinstance(data["success"], bool)

    assert "cook_id" in data
    assert isinstance(data["cook_id"], str)

    assert "device_state" in data
    assert data["device_state"] in ["preheating", "cooking"]

    assert "target_temp_celsius" in data
    assert isinstance(data["target_temp_celsius"], (int, float))

    assert "time_minutes" in data
    assert isinstance(data["time_minutes"], int)

    # Optional fields
    if "message" in data:
        assert isinstance(data["message"], str)

    if "estimated_completion" in data:
        assert isinstance(data["estimated_completion"], str)
        # Should be ISO 8601 format
        from datetime import datetime
        datetime.fromisoformat(data["estimated_completion"].replace('Z', '+00:00'))
```

---

#### INT-API-02: Status Response Schema

```python
def test_int_api_02_status_response_schema(client, auth_headers, mock_anova_api_success):
    """INT-API-02: Status response matches schema."""

    response = client.get('/status', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # Required fields
    assert "device_online" in data
    assert isinstance(data["device_online"], bool)

    assert "state" in data
    assert data["state"] in ["idle", "preheating", "cooking", "done", "unknown"]

    assert "current_temp_celsius" in data
    assert isinstance(data["current_temp_celsius"], (int, float))

    # Optional/nullable fields
    assert "target_temp_celsius" in data
    # Can be None or number

    assert "time_remaining_minutes" in data
    # Can be None or int

    assert "time_elapsed_minutes" in data
    # Can be None or int

    assert "is_running" in data
    assert isinstance(data["is_running"], bool)
```

---

#### INT-API-03: Stop Cook Response Schema

```python
def test_int_api_03_stop_cook_response_schema(client, auth_headers, mock_anova_api_success):
    """INT-API-03: Stop cook response matches schema."""

    # First start a cook
    client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 65.0, "time_minutes": 90}
    )

    # Then stop it
    response = client.post('/stop-cook', headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # Required fields
    assert "success" in data
    assert isinstance(data["success"], bool)

    assert "device_state" in data
    assert data["device_state"] == "idle"

    # Optional fields
    if "message" in data:
        assert isinstance(data["message"], str)

    if "final_temp_celsius" in data:
        assert isinstance(data["final_temp_celsius"], (int, float, type(None)))
```

---

#### INT-API-04: Error Response Schema

```python
def test_int_api_04_error_response_schema(client, auth_headers):
    """INT-API-04: Error responses match schema."""

    # Trigger validation error
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 35.0, "time_minutes": 60}
    )

    assert response.status_code == 400
    data = response.get_json()

    # Required error fields
    assert "error" in data
    assert isinstance(data["error"], str)
    assert data["error"] == "TEMPERATURE_TOO_LOW"

    assert "message" in data
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0
```

---

## 6. Error Handling Integration

### 6.1 Error Propagation Tests

#### INT-ERR-01: ValidationError → 400 Response

```python
def test_int_err_01_validation_error_to_400(client, auth_headers):
    """INT-ERR-01: ValidationError from validators.py becomes 400."""

    # Each validation error should map to 400
    invalid_cases = [
        ({"temperature_celsius": 35, "time_minutes": 60}, "TEMPERATURE_TOO_LOW"),
        ({"temperature_celsius": 105, "time_minutes": 60}, "TEMPERATURE_TOO_HIGH"),
        ({"temperature_celsius": 65, "time_minutes": 0}, "TIME_TOO_SHORT"),
        ({"temperature_celsius": 65, "time_minutes": 6000}, "TIME_TOO_LONG"),
        ({"time_minutes": 60}, "MISSING_TEMPERATURE"),
        ({"temperature_celsius": 65}, "MISSING_TIME"),
    ]

    for request_data, expected_error in invalid_cases:
        response = client.post(
            '/start-cook',
            headers=auth_headers,
            json=request_data
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == expected_error
```

---

#### INT-ERR-02: DeviceOfflineError → 503 Response

```python
def test_int_err_02_device_offline_error_to_503(client, auth_headers, mock_anova_api_offline):
    """INT-ERR-02: DeviceOfflineError becomes 503."""

    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 65.0, "time_minutes": 90}
    )

    assert response.status_code == 503
    data = response.get_json()
    assert data["error"] == "DEVICE_OFFLINE"

    # Should have retry_after or helpful message
    assert "retry" in data.get("message", "").lower() or "wifi" in data.get("message", "").lower()
```

---

#### INT-ERR-03: DeviceBusyError → 409 Response

```python
def test_int_err_03_device_busy_error_to_409(client, auth_headers, mock_anova_api_busy):
    """INT-ERR-03: DeviceBusyError becomes 409."""

    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 65.0, "time_minutes": 90}
    )

    assert response.status_code == 409
    data = response.get_json()
    assert data["error"] == "DEVICE_BUSY"
```

---

#### INT-ERR-04: AuthenticationError → 401 Response

```python
def test_int_err_04_authentication_error_to_401(client):
    """INT-ERR-04: Missing/invalid auth becomes 401."""

    # Test missing auth
    response = client.post(
        '/start-cook',
        json={"temperature_celsius": 65.0, "time_minutes": 90}
    )
    assert response.status_code == 401

    # Test invalid auth
    response = client.post(
        '/start-cook',
        headers={"Authorization": "Bearer wrong-key"},
        json={"temperature_celsius": 65.0, "time_minutes": 90}
    )
    assert response.status_code == 401
```

---

## 7. Performance Expectations

Integration tests are not load tests, but they should verify basic performance characteristics.

### 7.1 Response Time Tests

```python
import time

def test_int_perf_01_health_check_fast(client):
    """Health check responds in < 100ms."""

    start = time.time()
    response = client.get('/health')
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.1  # 100ms

def test_int_perf_02_start_cook_reasonable(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """Start cook responds in < 2 seconds."""

    start = time.time()
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 2.0  # 2 seconds

def test_int_perf_03_status_fast(client, auth_headers, mock_anova_api_success):
    """Status query responds in < 500ms."""

    start = time.time()
    response = client.get('/status', headers=auth_headers)
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.5  # 500ms
```

**Note:** These are baseline expectations for mocked tests. Real API latency will be higher and should be measured separately.

---

## 8. Test Data Sets

### 8.1 Valid Cook Requests

```python
VALID_COOK_REQUESTS = {
    "chicken_safe": {
        "temperature_celsius": 65.0,
        "time_minutes": 90,
        "food_type": "chicken breast",
        "expected_state": "preheating"
    },
    "chicken_low_temp_long_time": {
        "temperature_celsius": 57.0,
        "time_minutes": 180,
        "food_type": "chicken",
        "expected_state": "preheating"
    },
    "steak_medium_rare": {
        "temperature_celsius": 54.0,
        "time_minutes": 120,
        "food_type": "ribeye steak",
        "expected_state": "preheating"
    },
    "steak_rare": {
        "temperature_celsius": 52.0,
        "time_minutes": 90,
        "food_type": "beef steak",
        "expected_state": "preheating"
    },
    "salmon": {
        "temperature_celsius": 52.0,
        "time_minutes": 45,
        "food_type": "salmon fillet",
        "expected_state": "preheating"
    },
    "pork_chop": {
        "temperature_celsius": 58.0,
        "time_minutes": 120,
        "food_type": "pork chop",
        "expected_state": "preheating"
    },
    "edge_min_temp": {
        "temperature_celsius": 40.0,
        "time_minutes": 60,
        "expected_state": "preheating"
    },
    "edge_max_temp": {
        "temperature_celsius": 100.0,
        "time_minutes": 60,
        "expected_state": "preheating"
    },
    "edge_min_time": {
        "temperature_celsius": 65.0,
        "time_minutes": 1,
        "expected_state": "preheating"
    },
    "edge_max_time": {
        "temperature_celsius": 65.0,
        "time_minutes": 5999,
        "expected_state": "preheating"
    }
}
```

### 8.2 Invalid Cook Requests

```python
INVALID_COOK_REQUESTS = {
    "temp_too_low": {
        "temperature_celsius": 35.0,
        "time_minutes": 60,
        "expected_error": "TEMPERATURE_TOO_LOW",
        "expected_status": 400
    },
    "temp_way_too_low": {
        "temperature_celsius": 0.0,
        "time_minutes": 60,
        "expected_error": "TEMPERATURE_TOO_LOW",
        "expected_status": 400
    },
    "temp_too_high": {
        "temperature_celsius": 105.0,
        "time_minutes": 60,
        "expected_error": "TEMPERATURE_TOO_HIGH",
        "expected_status": 400
    },
    "temp_boiling": {
        "temperature_celsius": 100.1,
        "time_minutes": 60,
        "expected_error": "TEMPERATURE_TOO_HIGH",
        "expected_status": 400
    },
    "unsafe_poultry_low": {
        "temperature_celsius": 50.0,
        "time_minutes": 90,
        "food_type": "chicken breast",
        "expected_error": "POULTRY_TEMP_UNSAFE",
        "expected_status": 400
    },
    "unsafe_poultry_edge": {
        "temperature_celsius": 56.9,
        "time_minutes": 90,
        "food_type": "turkey",
        "expected_error": "POULTRY_TEMP_UNSAFE",
        "expected_status": 400
    },
    "unsafe_ground_meat_low": {
        "temperature_celsius": 55.0,
        "time_minutes": 60,
        "food_type": "ground beef",
        "expected_error": "GROUND_MEAT_TEMP_UNSAFE",
        "expected_status": 400
    },
    "unsafe_ground_meat_edge": {
        "temperature_celsius": 59.9,
        "time_minutes": 60,
        "food_type": "burger",
        "expected_error": "GROUND_MEAT_TEMP_UNSAFE",
        "expected_status": 400
    },
    "time_zero": {
        "temperature_celsius": 65.0,
        "time_minutes": 0,
        "expected_error": "TIME_TOO_SHORT",
        "expected_status": 400
    },
    "time_negative": {
        "temperature_celsius": 65.0,
        "time_minutes": -10,
        "expected_error": "TIME_TOO_SHORT",
        "expected_status": 400
    },
    "time_too_long": {
        "temperature_celsius": 65.0,
        "time_minutes": 6000,
        "expected_error": "TIME_TOO_LONG",
        "expected_status": 400
    },
    "missing_temperature": {
        "time_minutes": 90,
        "expected_error": "MISSING_TEMPERATURE",
        "expected_status": 400
    },
    "missing_time": {
        "temperature_celsius": 65.0,
        "expected_error": "MISSING_TIME",
        "expected_status": 400
    },
    "missing_both": {
        "expected_error": "MISSING_TEMPERATURE",
        "expected_status": 400
    },
    "invalid_temp_type": {
        "temperature_celsius": "hot",
        "time_minutes": 90,
        "expected_error": "INVALID_TEMPERATURE",
        "expected_status": 400
    },
    "invalid_time_type": {
        "temperature_celsius": 65.0,
        "time_minutes": "long",
        "expected_error": "INVALID_TIME",
        "expected_status": 400
    }
}
```

### 8.3 Anova API Mock Responses

```python
ANOVA_MOCK_RESPONSES = {
    "auth_success": {
        "url": "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        "json": {
            "idToken": "mock-id-token-abc123",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        "status": 200
    },
    "device_idle": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        "json": {
            "online": True,
            "state": "idle",
            "current_temperature": 22.5,
            "target_temperature": None,
            "timer_remaining": None,
            "timer_elapsed": None
        },
        "status": 200
    },
    "device_preheating": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        "json": {
            "online": True,
            "state": "preheating",
            "current_temperature": 45.0,
            "target_temperature": 65.0,
            "timer_remaining": None,
            "timer_elapsed": None
        },
        "status": 200
    },
    "device_cooking": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        "json": {
            "online": True,
            "state": "cooking",
            "current_temperature": 65.0,
            "target_temperature": 65.0,
            "timer_remaining": 45,
            "timer_elapsed": 45
        },
        "status": 200
    },
    "device_offline_404": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        "json": {"error": "Device not found"},
        "status": 404
    },
    "device_offline_online_false": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/status",
        "json": {
            "online": False,
            "state": "unknown"
        },
        "status": 200
    },
    "start_cook_success": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/start",
        "json": {
            "success": True,
            "state": "preheating"
        },
        "status": 200
    },
    "start_cook_busy": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/start",
        "json": {"error": "Device already cooking"},
        "status": 409
    },
    "stop_cook_success": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/stop",
        "json": {
            "success": True,
            "state": "idle"
        },
        "status": 200
    },
    "stop_cook_not_cooking": {
        "url": "https://anovaculinary.io/api/v1/devices/test-device-123/stop",
        "json": {"error": "No active cook session"},
        "status": 409
    }
}
```

---

## 9. Integration Test Implementation Guide

### 9.1 Test File Structure

```
tests/
├── integration/
│   ├── __init__.py
│   ├── test_int_happy_path.py         # INT-01, INT-02
│   ├── test_int_error_paths.py        # INT-03, INT-04, INT-05
│   ├── test_int_edge_cases.py         # INT-06, INT-07, INT-08
│   ├── test_int_state_transitions.py  # INT-ST-01 through INT-ST-05
│   ├── test_int_api_contracts.py      # INT-API-01 through INT-API-04
│   ├── test_int_error_handling.py     # INT-ERR-01 through INT-ERR-04
│   └── test_int_performance.py        # INT-PERF-01 through INT-PERF-03
```

### 9.2 Example Test File Template

```python
# tests/integration/test_int_happy_path.py

"""
Integration tests for happy path scenarios.

Tests:
- INT-01: Complete cook cycle success
- INT-02: Validation rejection flow

Reference: docs/09-integration-test-specification.md
"""

import pytest
import responses


class TestIntegrationHappyPath:
    """Integration tests for successful operation flows."""

    def test_int_01_complete_cook_cycle_success(
        self,
        client,
        auth_headers,
        valid_cook_requests,
        mock_anova_api_success
    ):
        """
        INT-01: Complete cook cycle from start to stop.

        Validates:
        - FR-01: Start cooking session
        - FR-02: Report cooking status
        - FR-03: Stop cooking session
        - QR-01: Response time < 5s

        Steps:
        1. Start cook with valid parameters
        2. Check status (should be running)
        3. Stop cook
        4. Verify final state is idle
        """
        # Implementation as shown in section 3.1
        pass

    def test_int_02_validation_rejection_flow(
        self,
        client,
        auth_headers,
        invalid_cook_requests
    ):
        """
        INT-02: Validation rejects request before calling Anova API.

        Validates:
        - FR-04: Temperature validation
        - FR-05: Time validation
        - FR-07: Poultry safety
        - FR-08: Ground meat safety

        Ensures validation happens BEFORE external API call.
        """
        # Implementation as shown in section 3.1
        pass
```

### 9.3 Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific integration test file
pytest tests/integration/test_int_happy_path.py -v

# Run specific test
pytest tests/integration/test_int_happy_path.py::TestIntegrationHappyPath::test_int_01_complete_cook_cycle_success -v

# Run with coverage
pytest tests/integration/ --cov=server --cov-report=html

# Run with verbose output and show print statements
pytest tests/integration/ -v -s

# Run only tests matching pattern
pytest tests/integration/ -k "happy_path" -v
```

---

## 10. Continuous Integration

### 10.1 GitHub Actions Example

```yaml
# .github/workflows/integration-tests.yml

name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run integration tests
      run: |
        pytest tests/integration/ -v --cov=server --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: integration
        name: integration-tests
```

### 10.2 Test Isolation in CI

Each integration test should:
- Start with clean state (fresh Flask app)
- Not depend on execution order
- Not share state with other tests
- Clean up after itself (if needed)
- Use fixtures for setup/teardown

**Good practices:**
```python
@pytest.fixture
def app():
    """Create fresh app for each test."""
    app = create_app(test_config)
    yield app
    # Cleanup (if needed)

@pytest.fixture(scope="function")  # Explicit function scope
def client(app):
    """New client for each test."""
    return app.test_client()
```

---

## 11. Traceability Matrix

### 11.1 Requirements to Integration Tests

| Requirement | Integration Tests | Unit Tests | Coverage |
|-------------|-------------------|------------|----------|
| FR-01 (Start cook) | INT-01, INT-04, INT-ST-01 | TC-VAL-01 through TC-VAL-16 | High |
| FR-02 (Status) | INT-01, INT-ST-01 through INT-ST-05 | N/A | High |
| FR-03 (Stop cook) | INT-01, INT-06, INT-ST-05 | N/A | High |
| FR-04 (Temp validation) | INT-02, INT-ERR-01 | TC-VAL-02 through TC-VAL-05 | High |
| FR-05 (Time validation) | INT-02, INT-ERR-01 | TC-VAL-06 through TC-VAL-09 | High |
| FR-06 (Device offline) | INT-03, INT-ST-04 | N/A | Medium |
| FR-07 (Poultry safety) | INT-02, INT-ERR-01 | TC-VAL-10, TC-VAL-11 | High |
| FR-08 (Ground meat safety) | INT-02, INT-ERR-01 | TC-VAL-12, TC-VAL-13 | High |
| QR-01 (Performance) | INT-PERF-01 through INT-PERF-03 | N/A | Medium |
| QR-10 (Health check) | All tests using /health | N/A | High |
| QR-33 (Auth required) | INT-05, INT-ERR-04 | N/A | High |

### 11.2 Integration Tests to Components

| Integration Test | Components Tested | Layer Coverage |
|------------------|-------------------|----------------|
| INT-01 | routes.py, validators.py, anova_client.py, middleware.py | API + Service + Integration |
| INT-02 | routes.py, validators.py, middleware.py | API + Service |
| INT-03 | routes.py, anova_client.py, middleware.py | API + Integration |
| INT-04 | routes.py, anova_client.py, middleware.py | API + Integration |
| INT-05 | routes.py, middleware.py | API only |
| INT-06 | routes.py, anova_client.py, middleware.py | API + Integration |
| INT-07 | routes.py, anova_client.py | API + Integration |
| INT-08 | routes.py, anova_client.py, middleware.py | API + Integration |
| INT-ST-* | routes.py, anova_client.py | API + Integration |
| INT-API-* | routes.py, validators.py, anova_client.py | API + Service + Integration |
| INT-ERR-* | routes.py, validators.py, anova_client.py, middleware.py, exceptions.py | All layers |

---

## 12. Test Maintenance Guidelines

### 12.1 When to Update Integration Tests

Update integration tests when:
- API contract changes (new fields, endpoints)
- Component interactions change
- New error scenarios discovered
- Performance requirements change
- Security requirements change
- State machine changes

### 12.2 Test Review Checklist

Before merging new integration tests:
- [ ] Test has clear docstring with scenario description
- [ ] Test validates specific requirements (FR-XX, QR-XX)
- [ ] Test uses appropriate fixtures (no hardcoded values)
- [ ] Test is isolated (doesn't depend on other tests)
- [ ] Test has clear assertions with helpful messages
- [ ] Test includes both positive and negative cases
- [ ] Test cleanup is handled (if needed)
- [ ] Test is documented in traceability matrix
- [ ] Test runs successfully in CI
- [ ] Test completes in < 5 seconds

### 12.3 Anti-Patterns to Avoid

**Don't:**
- Call real Anova API in integration tests
- Share state between tests (global variables)
- Use time.sleep() for timing (use mocks)
- Test implementation details (test behavior)
- Write flaky tests (non-deterministic)
- Skip cleanup (leave test artifacts)
- Use print() for debugging (use logging or pytest -s)
- Hardcode test data (use fixtures)

**Do:**
- Mock external dependencies
- Use fixtures for setup/teardown
- Test behavior, not implementation
- Write deterministic tests
- Use meaningful assertion messages
- Keep tests fast (< 5s each)
- Follow naming conventions (test_int_XX_description)
- Document what you're testing

---

## 13. Summary

### 13.1 Integration Test Coverage

**Total Integration Test Scenarios:** 25+

**By Category:**
- Happy path: 2 scenarios (INT-01, INT-02)
- Error paths: 3 scenarios (INT-03, INT-04, INT-05)
- Edge cases: 3 scenarios (INT-06, INT-07, INT-08)
- State transitions: 5 scenarios (INT-ST-01 through INT-ST-05)
- API contracts: 4 scenarios (INT-API-01 through INT-API-04)
- Error handling: 4 scenarios (INT-ERR-01 through INT-ERR-04)
- Performance: 3 scenarios (INT-PERF-01 through INT-PERF-03)

### 13.2 Success Criteria

Integration test suite is complete when:
- ✅ All critical user flows are tested (start, status, stop)
- ✅ All validation scenarios are tested
- ✅ All error scenarios are tested
- ✅ All state transitions are tested
- ✅ All API contracts are validated
- ✅ All tests pass consistently (no flakiness)
- ✅ Test suite completes in < 30 seconds
- ✅ Coverage > 80% on routes.py, validators.py
- ✅ All requirements have traceability to tests
- ✅ Tests can be written from specification alone

### 13.3 Next Steps

1. **Implement fixtures** - Create all fixtures in conftest.py
2. **Implement happy path tests** - Start with INT-01, INT-02
3. **Implement error path tests** - Add INT-03 through INT-05
4. **Implement edge case tests** - Add INT-06 through INT-08
5. **Implement state transition tests** - Add INT-ST-* series
6. **Implement contract tests** - Add INT-API-* series
7. **Implement error handling tests** - Add INT-ERR-* series
8. **Run full suite** - Verify all tests pass
9. **Measure coverage** - Ensure > 80% coverage
10. **Document any gaps** - Add tests for uncovered scenarios

---

## 14. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-10 | Claude | Initial comprehensive integration test specification |

---

## 15. References

- **01-system-context.md** - System overview and requirements
- **03-component-architecture.md** - Component specifications and contracts
- **05-api-specification.md** - API contracts and response schemas
- **CLAUDE.md** - Implementation patterns and testing strategy
- **pytest documentation** - https://docs.pytest.org/
- **Flask testing documentation** - https://flask.palletsprojects.com/en/latest/testing/
- **responses library** - https://github.com/getsentry/responses
