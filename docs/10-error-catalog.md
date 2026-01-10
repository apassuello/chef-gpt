# 10 - Error Catalog

> **Document Type:** Error Code Reference
> **Status:** Complete
> **Version:** 1.0
> **Last Updated:** 2026-01-10
> **Depends On:** server/exceptions.py, COMPONENT-IMPLEMENTATIONS.md
> **Blocks:** None (reference document)

---

## 1. Purpose

This document provides a **central registry** of all error codes used throughout the Anova AI Sous Vide Assistant system. Each error code maps to specific conditions, HTTP status codes, and handling strategies.

**Use this catalog for:**
- API client error handling
- Test case specification
- Error message consistency
- Troubleshooting and debugging
- Integration documentation

---

## 2. Error Code Categories

### 2.1 Category Overview

| Category | Error Codes | HTTP Status Range | Component |
|----------|-------------|-------------------|-----------|
| **Validation Errors** | 11 codes | 400 Bad Request | validators.py |
| **Authentication Errors** | 1 code | 401 Unauthorized | middleware.py |
| **Device State Errors** | 2 codes | 404, 409 | anova_client.py |
| **External Service Errors** | 2 codes | 500, 503 | anova_client.py |

**Total Error Codes:** 16 unique codes

---

## 3. Validation Errors (HTTP 400)

### 3.1 Missing Fields

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **MISSING_BODY** | Request body is null or empty | 400 | middleware.py | "Request body is required" | Send valid JSON body |
| **MISSING_TEMPERATURE** | temperature_celsius field absent from request | 400 | validators.py | "temperature_celsius is required" | Include temperature_celsius in request |
| **MISSING_TIME** | time_minutes field absent from request | 400 | validators.py | "time_minutes is required" | Include time_minutes in request |

**When to Use:** Request validation before type checking

**Example Request:**
```json
{
  "time_minutes": 90
  // Missing: temperature_celsius
}
```

**Error Response:**
```json
{
  "error": "MISSING_TEMPERATURE",
  "message": "temperature_celsius is required"
}
```

### 3.2 Invalid Types

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **INVALID_TEMPERATURE** | temperature_celsius is not a number (cannot coerce to float) | 400 | validators.py | "temperature_celsius must be a number" | Send numeric value for temperature |
| **INVALID_TIME** | time_minutes is not an integer (cannot coerce to int) | 400 | validators.py | "time_minutes must be an integer" | Send integer value for time |

**When to Use:** Type validation after field presence check

**Example Request:**
```json
{
  "temperature_celsius": "hot",  // Invalid: not a number
  "time_minutes": 90
}
```

**Error Response:**
```json
{
  "error": "INVALID_TEMPERATURE",
  "message": "temperature_celsius must be a number"
}
```

### 3.3 Range Violations

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **TEMPERATURE_TOO_LOW** | temperature_celsius < 40.0°C | 400 | validators.py | "Temperature 35°C is below the safe minimum of 40°C. Food below this temperature is in the bacterial danger zone." | Use temperature >= 40.0°C |
| **TEMPERATURE_TOO_HIGH** | temperature_celsius > 100.0°C | 400 | validators.py | "Temperature 105°C exceeds the safe maximum of 100°C. Water boils at 100°C." | Use temperature <= 100.0°C |
| **TIME_TOO_SHORT** | time_minutes < 1 | 400 | validators.py | "Time must be at least 1 minute" | Use time >= 1 minute |
| **TIME_TOO_LONG** | time_minutes > 5999 | 400 | validators.py | "Time 6000 minutes exceeds device maximum of 5999 minutes (99h 59m)" | Use time <= 5999 minutes (99h 59m) |

**When to Use:** Range validation after type check

**Example Request:**
```json
{
  "temperature_celsius": 35.0,  // Too low (< 40°C)
  "time_minutes": 90
}
```

**Error Response:**
```json
{
  "error": "TEMPERATURE_TOO_LOW",
  "message": "Temperature 35.0°C is below the safe minimum of 40.0°C. Food below this temperature is in the bacterial danger zone (4-60°C) where bacteria multiply rapidly."
}
```

### 3.4 Food Safety Violations

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **POULTRY_TEMP_UNSAFE** | food_type indicates poultry AND temperature < 57.0°C | 400 | validators.py | "Temperature 55°C is not safe for poultry. Minimum is 57°C with extended time (3+ hours) or 65°C for standard cooking." | Use temp >= 57°C (extended) or >= 65°C (standard) |
| **GROUND_MEAT_TEMP_UNSAFE** | food_type indicates ground meat AND temperature < 60.0°C | 400 | validators.py | "Temperature 58°C is not safe for ground meat. Minimum is 60°C because bacteria are mixed throughout." | Use temperature >= 60°C |

**When to Use:** Food-specific safety validation after range check

**Poultry Keywords:** chicken, turkey, duck, poultry, hen, fowl, goose

**Ground Meat Keywords:** ground, mince, burger, sausage

**Example Request:**
```json
{
  "temperature_celsius": 56.0,  // Too low for chicken
  "time_minutes": 90,
  "food_type": "chicken breast"
}
```

**Error Response:**
```json
{
  "error": "POULTRY_TEMP_UNSAFE",
  "message": "Temperature 56.0°C is not safe for poultry. Minimum is 57.0°C with extended time (3+ hours) or 65.0°C for standard cooking. This ensures Salmonella is reduced to safe levels."
}
```

**Traceability:**
- FR-07: Poultry temperature validation
- FR-08: Ground meat temperature validation
- TC-VAL-10, TC-VAL-11: Poultry test cases
- TC-VAL-12, TC-VAL-13: Ground meat test cases

---

## 4. Authentication Errors (HTTP 401)

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **UNAUTHORIZED** | Missing, invalid, or malformed Authorization header | 401 | middleware.py | "Invalid API key" or "Missing Authorization header" or "Invalid Authorization header format. Expected: Bearer <token>" | Provide valid Authorization: Bearer <api_key> header |

**When to Use:** All endpoints except `/health`

**Valid Format:** `Authorization: Bearer <api_key>`

**Example Error Scenarios:**

1. **Missing header:**
   ```http
   GET /status
   # No Authorization header
   ```
   Response:
   ```json
   {
     "error": "UNAUTHORIZED",
     "message": "Missing Authorization header"
   }
   ```

2. **Invalid format:**
   ```http
   GET /status
   Authorization: sk-anova-abc123  # Missing "Bearer" prefix
   ```
   Response:
   ```json
   {
     "error": "UNAUTHORIZED",
     "message": "Invalid Authorization header format. Expected: Bearer <token>"
   }
   ```

3. **Wrong API key:**
   ```http
   GET /status
   Authorization: Bearer wrong-api-key
   ```
   Response:
   ```json
   {
     "error": "UNAUTHORIZED",
     "message": "Invalid API key"
   }
   ```

**Security Note:** Uses constant-time comparison (`hmac.compare_digest`) to prevent timing attacks

**Traceability:**
- SEC-REQ-01: API key authentication
- SEC-01: Authentication test cases
- QR-33: API key requirement

---

## 5. Device State Errors (HTTP 404, 409)

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **DEVICE_BUSY** | Attempt to start cook while device already cooking | 409 | anova_client.py | "Device is already cooking" | Stop current cook first, or wait for completion |
| **NO_ACTIVE_COOK** | Attempt to stop cook when no cook is running | 404 | anova_client.py | "No active cooking session" | No action needed (idempotent stop) |

**When to Use:** Device state machine violations

**State Machine:**
```
IDLE → start_cook() → PREHEATING → COOKING → DONE
           ↑ (stop_cook)              ↑ (stop_cook)
           └──────────────────────────┘
```

**DEVICE_BUSY Example:**
```
Current State: COOKING
Action: POST /start-cook
Result: HTTP 409 Conflict
```

**NO_ACTIVE_COOK Example:**
```
Current State: IDLE
Action: POST /stop-cook
Result: HTTP 404 Not Found (but safe/idempotent)
```

**Traceability:**
- FR-01: Start cook requirement
- FR-03: Stop cook requirement
- INT-05: Concurrent cook attempt test
- Device state specification: docs/03-component-architecture.md Section 4.3.1

---

## 6. External Service Errors (HTTP 500, 503)

| Error Code | Condition | HTTP | Component | Example Message | Recovery |
|------------|-----------|------|-----------|-----------------|----------|
| **DEVICE_OFFLINE** | Anova device is not reachable via Anova Cloud API | 503 | anova_client.py | "Device is offline or unreachable" | Check device WiFi connection, retry after 60 seconds |
| **ANOVA_API_ERROR** | Generic Anova Cloud API error (network, auth, unknown) | 500 | anova_client.py | "Unable to communicate with Anova Cloud API" | Check server logs, verify Anova Cloud status, retry |

**When to Use:** External dependency failures

**DEVICE_OFFLINE:**
- Device is powered off
- Device WiFi disconnected
- Anova Cloud cannot reach device
- Suggested retry: 60 seconds

**ANOVA_API_ERROR:**
- Network connectivity issues
- Firebase authentication failure
- Anova Cloud API downtime
- Unknown API errors

**Response Headers:**
```http
HTTP/1.1 503 Service Unavailable
Retry-After: 60
Content-Type: application/json

{
  "error": "DEVICE_OFFLINE",
  "message": "Device is offline or unreachable",
  "retry_after": 60
}
```

**Traceability:**
- FR-06: Device offline status requirement
- QR-13: Graceful handling of Anova Cloud outage
- INT-08: Device offline test scenario

---

## 7. Error Response Format

### 7.1 Standard Error Response

**All errors use consistent JSON format:**

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable explanation of what went wrong",
  "details": {
    "optional_field": "additional context"
  }
}
```

**Fields:**
- `error` (string, required): Machine-readable error code (ALL_CAPS_SNAKE_CASE)
- `message` (string, required): Human-readable explanation for end user or developer
- `details` (object, optional): Additional context (rarely used)

### 7.2 Validation Error Example

```json
{
  "error": "TEMPERATURE_TOO_LOW",
  "message": "Temperature 35.0°C is below the safe minimum of 40.0°C. Food below this temperature is in the bacterial danger zone (4-60°C) where bacteria multiply rapidly."
}
```

### 7.3 Service Error Example

```json
{
  "error": "DEVICE_OFFLINE",
  "message": "Device is offline or unreachable",
  "retry_after": 60
}
```

---

## 8. Error Handling Flow

### 8.1 Error Propagation

```
validators.py          →  ValidationError
  ↓                         ↓
routes.py (catches)    →  HTTP 400 + JSON error response

anova_client.py        →  AnovaAPIError / DeviceOfflineError
  ↓                         ↓
routes.py (catches)    →  HTTP 500/503 + JSON error response

middleware.py          →  401 response (directly)
  ↓
Client receives HTTP 401 + JSON error response
```

### 8.2 Exception Hierarchy

```
AnovaServerError (base)
├── ValidationError (400)
│   ├── MISSING_* errors
│   ├── INVALID_* errors
│   ├── *_TOO_* errors
│   └── *_UNSAFE errors
│
└── AnovaAPIError (5xx)
    ├── DeviceOfflineError (503)
    ├── DeviceBusyError (409)
    ├── NoActiveCookError (404)
    └── AuthenticationError (500)
```

**Reference:** `server/exceptions.py` for complete exception definitions

---

## 9. Client Error Handling Guide

### 9.1 Retry Strategy

| Error Code | Retry? | Strategy | Max Attempts | Backoff |
|------------|--------|----------|--------------|---------|
| **Validation Errors (400)** | ❌ No | Fix request data | N/A | N/A |
| **UNAUTHORIZED (401)** | ❌ No | Fix API key | N/A | N/A |
| **DEVICE_BUSY (409)** | ✅ Yes | Wait for cook to finish | 3 | 30s, 60s, 90s |
| **NO_ACTIVE_COOK (404)** | ❌ No | Idempotent (safe) | N/A | N/A |
| **ANOVA_API_ERROR (500)** | ✅ Yes | Exponential backoff | 3 | 1s, 2s, 4s |
| **DEVICE_OFFLINE (503)** | ✅ Yes | Linear backoff | 3 | 60s, 60s, 60s |

### 9.2 Error Handling Pseudocode

```python
def call_api(endpoint, data):
    try:
        response = requests.post(endpoint, json=data, headers=auth_headers)
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as e:
        error_data = e.response.json()
        error_code = error_data.get("error")

        # Validation errors - fix request and retry
        if e.response.status_code == 400:
            log_error(f"Validation failed: {error_code}")
            raise ValidationError(error_data["message"])

        # Auth errors - fix API key
        elif e.response.status_code == 401:
            log_error("Authentication failed - check API key")
            raise AuthError()

        # Device busy - wait and retry
        elif error_code == "DEVICE_BUSY":
            log_info("Device busy, retrying in 30s...")
            time.sleep(30)
            return call_api(endpoint, data)  # Retry

        # Device offline - wait longer and retry
        elif error_code == "DEVICE_OFFLINE":
            log_warning("Device offline, retrying in 60s...")
            time.sleep(60)
            return call_api(endpoint, data)  # Retry

        # Generic API error - exponential backoff
        elif error_code == "ANOVA_API_ERROR":
            log_error("Anova API error, retrying with backoff...")
            return retry_with_exponential_backoff(endpoint, data)
```

---

## 10. Error Code Summary Table

| Error Code | HTTP | Category | Component | Retry? | FR/QR Link |
|------------|------|----------|-----------|--------|------------|
| MISSING_BODY | 400 | Validation | middleware.py | ❌ No | FR-01, FR-02, FR-03 |
| MISSING_TEMPERATURE | 400 | Validation | validators.py | ❌ No | FR-04 |
| MISSING_TIME | 400 | Validation | validators.py | ❌ No | FR-05 |
| INVALID_TEMPERATURE | 400 | Validation | validators.py | ❌ No | FR-04 |
| INVALID_TIME | 400 | Validation | validators.py | ❌ No | FR-05 |
| TEMPERATURE_TOO_LOW | 400 | Validation | validators.py | ❌ No | FR-04 |
| TEMPERATURE_TOO_HIGH | 400 | Validation | validators.py | ❌ No | FR-04 |
| TIME_TOO_SHORT | 400 | Validation | validators.py | ❌ No | FR-05 |
| TIME_TOO_LONG | 400 | Validation | validators.py | ❌ No | FR-05 |
| POULTRY_TEMP_UNSAFE | 400 | Food Safety | validators.py | ❌ No | FR-07 |
| GROUND_MEAT_TEMP_UNSAFE | 400 | Food Safety | validators.py | ❌ No | FR-08 |
| UNAUTHORIZED | 401 | Authentication | middleware.py | ❌ No | SEC-REQ-01, QR-33 |
| NO_ACTIVE_COOK | 404 | Device State | anova_client.py | ❌ No | FR-03 |
| DEVICE_BUSY | 409 | Device State | anova_client.py | ✅ Yes | FR-01 |
| ANOVA_API_ERROR | 500 | External Service | anova_client.py | ✅ Yes | QR-13 |
| DEVICE_OFFLINE | 503 | External Service | anova_client.py | ✅ Yes | FR-06, QR-13 |

**Total:** 16 unique error codes

---

## 11. Testing Error Codes

### 11.1 Unit Tests

**File:** `tests/test_validators.py`

**Coverage:** 16 test cases (TC-VAL-01 through TC-VAL-16) covering all validation error codes

**Example:**
```python
def test_temperature_too_low():
    """TC-VAL-02: Temperature below 40°C should fail."""
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook({"temperature_celsius": 39.9, "time_minutes": 90})

    assert exc_info.value.error_code == "TEMPERATURE_TOO_LOW"
    assert "danger zone" in exc_info.value.message.lower()
```

### 11.2 Integration Tests

**File:** `docs/09-integration-test-specification.md`

**Coverage:** Full request/response cycle for all error scenarios

**Example:**
```python
def test_start_cook_with_invalid_temperature():
    """INT-02: Invalid temperature should return 400."""
    response = client.post("/start-cook", json={
        "temperature_celsius": 35.0,  # Too low
        "time_minutes": 90
    }, headers=auth_headers)

    assert response.status_code == 400
    assert response.json["error"] == "TEMPERATURE_TOO_LOW"
```

### 11.3 Security Tests

**File:** `docs/11-security-test-specification.md`

**Coverage:** Authentication bypass attempts, injection attacks on error messages

**Example:**
```python
def test_unauthorized_access():
    """SEC-01: Missing API key should return 401."""
    response = client.get("/status")  # No auth header

    assert response.status_code == 401
    assert response.json["error"] == "UNAUTHORIZED"
```

---

## 12. Document References

### 12.1 Source Files

- **server/exceptions.py** - Exception class definitions
- **server/validators.py** - Validation logic and error raising
- **server/middleware.py** - Authentication error handling
- **server/anova_client.py** - External service error handling

### 12.2 Specification Documents

- **docs/01-system-context.md** - Functional requirements (FR-XX)
- **docs/03-component-architecture.md** - Component behavioral contracts
- **docs/05-api-specification.md** - OpenAPI error response schemas
- **docs/06-food-safety-requirements.md** - Food safety validation rules

### 12.3 Test Documents

- **tests/test_validators.py** - Unit tests for validation errors
- **docs/09-integration-test-specification.md** - Integration test scenarios
- **docs/11-security-test-specification.md** - Security test cases

### 12.4 Implementation Guide

- **CLAUDE.md** - Error handling patterns and anti-patterns
- **docs/COMPONENT-IMPLEMENTATIONS.md** - Complete component implementations

---

## 13. Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Claude | Initial error catalog creation |

---

## 14. Usage Examples

### 14.1 Custom GPT Integration

The Custom GPT should handle errors gracefully:

**Good Error Handling:**
```
User: "Cook chicken at 50°C for 2 hours"

GPT: "I can't start that cook because 50°C is too low for chicken. For
food safety, chicken needs to be cooked at minimum 57°C for 3+ hours,
or 65°C for standard cooking (1-2 hours). This ensures Salmonella is
reduced to safe levels.

Would you like me to start the cook at 65°C for 90 minutes instead?"
```

**Error Code Used:** POULTRY_TEMP_UNSAFE

### 14.2 API Client Integration

```python
from anova_api_client import AnovaClient, ValidationError, DeviceOfflineError

client = AnovaClient(api_key="sk-anova-...")

try:
    result = client.start_cook(temperature=65.0, time=90, food_type="chicken")
    print(f"Cook started: {result}")

except ValidationError as e:
    if e.error_code == "POULTRY_TEMP_UNSAFE":
        print("Temperature too low for chicken. Using 65°C instead.")
        result = client.start_cook(temperature=65.0, time=90, food_type="chicken")
    else:
        print(f"Validation failed: {e.message}")

except DeviceOfflineError:
    print("Device is offline. Please check WiFi connection.")
    # Schedule retry in 60 seconds
```

---

**This catalog is complete and covers all 16 error codes used in the system.**
