# Anova AI Sous Vide Assistant - Implementation Guide

## Project Overview

This system is an AI-powered sous vide cooking assistant that bridges ChatGPT (via Custom GPT) with an Anova Precision Cooker 3.0. It's designed as a gift with zero recurring costs, enabling natural language control of sous vide cooking with built-in food safety guardrails.

**Architecture Pattern:** API Gateway / Bridge  
**Deployment:** Self-hosted on Raspberry Pi Zero 2 W  
**Key Constraint:** Food safety is paramount - all temperature/time validation happens server-side, not just in the GPT.

---

## Tech Stack

| Technology | Version | Purpose | Why This Choice |
|------------|---------|---------|-----------------|
| **Python** | 3.11+ | Runtime | Modern type hints, pattern matching, AsyncIO support |
| **Flask** | 3.0.* | Web framework | Lightweight, proven, excellent for small APIs |
| **gunicorn** | 21.* | WSGI server | Production-ready, process management, battle-tested |
| **requests** | 2.31.* | HTTP client | Standard library for REST APIs, simple and reliable |
| **python-dotenv** | 1.0.* | Config management | Development environment variables, gitignore-safe |
| **cryptography** | 42.* | Credential encryption | Fernet symmetric encryption for production secrets |
| **pytest** | 7.* | Testing framework | Industry standard, excellent fixtures and plugins |
| **pytest-flask** | 1.* | Flask testing | Flask-specific test utilities and fixtures |
| **responses** | 0.24.* | HTTP mocking | Mock Anova API responses for testing |

---

## Quick Start Commands

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/apassuello/chef-gpt.git
cd chef-gpt

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env and fill in your Anova credentials and generate API key
```

### Development Server

```bash
# Activate venv (if not already active)
source venv/bin/activate

# Run Flask development server
python -m server.app

# Or with auto-reload:
export FLASK_APP=server.app
export FLASK_DEBUG=1
flask run --host=0.0.0.0 --port=5000
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=server --cov-report=html

# Run specific test file
pytest tests/test_validators.py

# Run specific test
pytest tests/test_validators.py::test_temperature_too_low

# Run tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x
```

### Linting (Optional)

```bash
# Install ruff (recommended linter)
pip install ruff

# Check code
ruff check server/

# Format code
ruff format server/

# Type checking with mypy (optional)
pip install mypy
mypy server/
```

---

## File Structure

```
chef-gpt/
├── CLAUDE.md                  # This file - implementation guide
├── IMPLEMENTATION.md          # Phased implementation roadmap
├── README.md                  # Project readme (brief, user-facing)
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Dev dependencies
├── .gitignore                 # Git ignore patterns
├── .env.example               # Environment variable template
│
├── server/                    # Main application code
│   ├── __init__.py           # Package marker
│   ├── app.py                # Flask application factory
│   ├── routes.py             # HTTP route handlers (API Layer)
│   ├── validators.py         # Input & food safety validation (Service Layer)
│   ├── anova_client.py       # Anova Cloud API client (Integration Layer)
│   ├── config.py             # Configuration management
│   ├── middleware.py         # Auth, logging, error handling
│   └── exceptions.py         # Custom exception definitions
│
├── tests/                     # Test suite
│   ├── __init__.py           # Package marker
│   ├── conftest.py           # pytest fixtures
│   ├── test_validators.py    # Validator unit tests
│   ├── test_routes.py        # Route integration tests
│   └── test_anova_client.py  # Client tests with mocks
│
├── deployment/                # Deployment artifacts
│   ├── anova-server.service  # systemd service file
│   └── setup_pi.sh           # Raspberry Pi setup script
│
└── docs/                      # Documentation
    └── README.md              # Links to project knowledge base
```

### Component Responsibilities

| Component | Responsibility | Dependencies |
|-----------|----------------|--------------|
| **app.py** | Bootstrap Flask app, wire components together | routes, middleware, config |
| **routes.py** | Handle HTTP requests, orchestrate responses | validators, anova_client, exceptions |
| **validators.py** | Validate all inputs, enforce food safety | exceptions |
| **anova_client.py** | Communicate with Anova Cloud API | config, exceptions |
| **config.py** | Load and manage configuration | python-dotenv, cryptography |
| **middleware.py** | Authentication, logging, error handling | exceptions |
| **exceptions.py** | Define custom exception hierarchy | (no dependencies) |

---

## Code Patterns

### 1. Error Handling Pattern

**Principle:** All errors flow through custom exceptions that map to HTTP status codes. Never let raw exceptions reach the client.

#### Exception Hierarchy

```python
# exceptions.py

class AnovaServerError(Exception):
    """Base exception for all application errors."""
    pass

class ValidationError(AnovaServerError):
    """Input validation failed."""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)

class AnovaAPIError(AnovaServerError):
    """Anova Cloud API error."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class DeviceOfflineError(AnovaAPIError):
    """Device not reachable."""
    pass

class AuthenticationError(AnovaAPIError):
    """Authentication with Anova failed."""
    pass
```

#### Exception to HTTP Mapping

```python
# routes.py or middleware.py

from flask import jsonify

def handle_validation_error(error: ValidationError):
    """Map ValidationError to 400 Bad Request."""
    return jsonify({
        "error": error.error_code,
        "message": error.message
    }), 400

def handle_device_offline(error: DeviceOfflineError):
    """Map DeviceOfflineError to 503 Service Unavailable."""
    return jsonify({
        "error": "DEVICE_OFFLINE",
        "message": error.message,
        "retry_after": 60  # Suggest retry after 60 seconds
    }), 503

def handle_anova_api_error(error: AnovaAPIError):
    """Map generic Anova errors to 500."""
    return jsonify({
        "error": "ANOVA_API_ERROR",
        "message": error.message
    }), error.status_code

# Register error handlers in app.py
app.register_error_handler(ValidationError, handle_validation_error)
app.register_error_handler(DeviceOfflineError, handle_device_offline)
app.register_error_handler(AnovaAPIError, handle_anova_api_error)
```

---

### 2. Validation Pattern

**Principle:** ALL validation happens in `validators.py`. Food safety rules are enforced at the API level, not just at the GPT level. Validation is the first line of defense.

#### Validation Function Template

```python
# validators.py

from typing import Any, Dict
from .exceptions import ValidationError

# Constants from kb-domain-knowledge.md
MIN_TEMP_CELSIUS = 40.0
MAX_TEMP_CELSIUS = 100.0
POULTRY_MIN_TEMP = 57.0
POULTRY_SAFE_TEMP = 65.0
GROUND_MEAT_MIN_TEMP = 60.0
MIN_TIME_MINUTES = 1
MAX_TIME_MINUTES = 5999

def validate_start_cook(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate cook parameters.
    
    Validation order (fail fast):
    1. Required fields present
    2. Type validation
    3. Range validation (absolute limits)
    4. Food safety validation (context-specific)
    
    Args:
        data: Request data from ChatGPT
        
    Returns:
        Validated and normalized parameters
        
    Raises:
        ValidationError: With specific error code and actionable message
    """
    # 1. Check required fields
    if "temperature_celsius" not in data:
        raise ValidationError(
            "MISSING_TEMPERATURE",
            "temperature_celsius is required"
        )
    
    # 2. Type validation with coercion
    try:
        temp = float(data["temperature_celsius"])
    except (TypeError, ValueError):
        raise ValidationError(
            "INVALID_TEMPERATURE",
            "temperature_celsius must be a number"
        )
    
    # 3. Range validation (absolute limits)
    if temp < MIN_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_LOW",
            f"Temperature {temp}°C is below the safe minimum of {MIN_TEMP_CELSIUS}°C. "
            f"Food below this temperature is in the bacterial danger zone."
        )
    
    if temp > MAX_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_HIGH",
            f"Temperature {temp}°C exceeds the safe maximum of {MAX_TEMP_CELSIUS}°C. "
            f"Water boils at 100°C."
        )
    
    # 4. Food-specific safety validation
    food_type = data.get("food_type", "").lower().strip()
    
    if _is_poultry(food_type) and temp < POULTRY_MIN_TEMP:
        raise ValidationError(
            "POULTRY_TEMP_UNSAFE",
            f"Temperature {temp}°C is not safe for poultry. "
            f"Minimum is {POULTRY_MIN_TEMP}°C with extended time (3+ hours) "
            f"or {POULTRY_SAFE_TEMP}°C for standard cooking."
        )
    
    if _is_ground_meat(food_type) and temp < GROUND_MEAT_MIN_TEMP:
        raise ValidationError(
            "GROUND_MEAT_TEMP_UNSAFE",
            f"Temperature {temp}°C is not safe for ground meat. "
            f"Minimum is {GROUND_MEAT_MIN_TEMP}°C because bacteria are mixed throughout."
        )
    
    # Return validated data
    return {
        "temperature_celsius": round(temp, 1),  # 1 decimal precision
        "time_minutes": int(data["time_minutes"]),
        "food_type": food_type if food_type else None
    }

def _is_poultry(food_type: str) -> bool:
    """Check if food type is poultry."""
    poultry_keywords = ["chicken", "turkey", "duck", "poultry", "hen", "fowl", "goose"]
    return any(kw in food_type for kw in poultry_keywords)

def _is_ground_meat(food_type: str) -> bool:
    """Check if food type is ground meat."""
    ground_keywords = ["ground", "mince", "burger", "sausage"]
    return any(kw in food_type for kw in ground_keywords)
```

---

### 3. Authentication Pattern

**Principle:** All endpoints except `/health` require API key authentication. Use constant-time comparison to prevent timing attacks.

#### Middleware Decorator

```python
# middleware.py

import hmac
import os
from functools import wraps
from flask import request, jsonify

def require_api_key(f):
    """
    Decorator to require API key authentication.
    
    Expects: Authorization: Bearer <api_key>
    
    Uses constant-time comparison to prevent timing attacks.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Missing Authorization header"
            }), 401
        
        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid Authorization header format. Expected: Bearer <token>"
            }), 401
        
        provided_key = parts[1]
        expected_key = os.getenv('API_KEY')
        
        # Constant-time comparison (prevents timing attacks)
        if not hmac.compare_digest(provided_key, expected_key):
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid API key"
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function
```

#### Usage in Routes

```python
# routes.py

from flask import Blueprint, request, jsonify
from .middleware import require_api_key
from .validators import validate_start_cook
from .anova_client import AnovaClient

api = Blueprint('api', __name__)

@api.route('/health', methods=['GET'])
def health():
    """Health check - no auth required."""
    return jsonify({"status": "ok"}), 200

@api.route('/start-cook', methods=['POST'])
@require_api_key  # Auth required
def start_cook():
    """Start a cooking session."""
    try:
        # Validate input
        validated = validate_start_cook(request.json)
        
        # Call Anova API
        client = AnovaClient()
        result = client.start_cook(**validated)
        
        return jsonify(result), 200
    except ValidationError as e:
        # Handled by error handler
        raise
```

---

### 4. Logging Pattern

**Principle:** Log what's useful for debugging. NEVER log credentials, tokens, or API keys. Treat logs as potentially public.

#### What to Log

```python
import logging

logger = logging.getLogger(__name__)

# DO log:
logger.info(f"Received request: {request.method} {request.path}")
logger.info(f"Starting cook: {temp}°C for {time} minutes")
logger.warning(f"Validation failed: {error.error_code}")
logger.error(f"Anova API error: {error.message}")

# DO NOT log (examples of what to avoid):
# logger.info(f"Auth header: {request.headers.get('Authorization')}")  # NO!
# logger.info(f"Anova password: {os.getenv('ANOVA_PASSWORD')}")        # NO!
# logger.info(f"Request body: {request.json}")                         # NO! (may contain sensitive data)
# logger.info(f"Token: {token}")                                       # NO!
```

#### Safe Logging Helper

```python
# middleware.py

def log_request_safely():
    """Log request without sensitive data."""
    logger.info(
        f"Request: {request.method} {request.path} "
        f"from {request.remote_addr}"
    )
    # Do NOT log headers (may contain auth)
    # Do NOT log body (may contain credentials)

def log_response_safely(status_code: int):
    """Log response without sensitive data."""
    logger.info(f"Response: {status_code}")
    # Do NOT log response body (may contain tokens)
```

#### Request/Response Logging Middleware

```python
# middleware.py

from flask import request, g
import time

def setup_request_logging(app):
    """Configure request/response logging middleware."""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
        # Log request (safely)
        logger.info(
            f"{request.method} {request.path} "
            f"from {request.remote_addr}"
        )
    
    @app.after_request
    def after_request(response):
        # Calculate request duration
        duration = time.time() - g.start_time
        
        # Log response (safely)
        logger.info(
            f"{request.method} {request.path} "
            f"→ {response.status_code} "
            f"({duration:.3f}s)"
        )
        
        return response
```

---

### 5. Response Format Pattern

**Principle:** Consistent JSON response format for all endpoints. Clients should always know what to expect.

#### Success Response Format

```json
{
  "field1": "value1",
  "field2": 123,
  "nested": {
    "field3": true
  }
}
```

#### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable explanation of what went wrong",
  "details": {
    "optional": "additional context"
  }
}
```

#### Example Implementations

```python
# routes.py

@api.route('/start-cook', methods=['POST'])
@require_api_key
def start_cook():
    """
    Success response example:
    {
      "status": "started",
      "target_temp_celsius": 65.0,
      "time_minutes": 90,
      "device_id": "abc123"
    }
    """
    # ... implementation
    return jsonify({
        "status": "started",
        "target_temp_celsius": validated["temperature_celsius"],
        "time_minutes": validated["time_minutes"],
        "device_id": client.device_id
    }), 200

@api.route('/status', methods=['GET'])
@require_api_key
def get_status():
    """
    Success response example:
    {
      "device_online": true,
      "state": "cooking",
      "current_temp_celsius": 64.8,
      "target_temp_celsius": 65.0,
      "time_remaining_minutes": 47,
      "time_elapsed_minutes": 43,
      "is_running": true
    }
    """
    # ... implementation
    return jsonify({
        "device_online": status["online"],
        "state": status["state"],
        "current_temp_celsius": status["current_temp"],
        "target_temp_celsius": status["target_temp"],
        "time_remaining_minutes": status["time_remaining"],
        "time_elapsed_minutes": status["time_elapsed"],
        "is_running": status["is_running"]
    }), 200
```

---

## Food Safety Rules

**CRITICAL:** These rules are NON-NEGOTIABLE. The system must enforce them at the API level, regardless of what the GPT suggests.

### Absolute Temperature Limits

| Limit | Value | Reason |
|-------|-------|--------|
| **Minimum** | 40.0°C (104°F) | Below this is the bacterial danger zone (4-60°C) where bacteria multiply rapidly |
| **Maximum** | 100.0°C (212°F) | Water boils above this; device cannot maintain higher temperatures |

### Food-Specific Minimum Safe Temperatures

| Food Type | Minimum Temp | Notes |
|-----------|--------------|-------|
| **Chicken/Turkey/Poultry** | 57.0°C | With 3+ hours cook time for pasteurization |
| **Chicken/Turkey/Poultry** | 65.0°C | Standard safe temperature (1-2 hour cook) |
| **Ground Meat** | 60.0°C | Bacteria mixed throughout during grinding |
| **Pork (whole muscle)** | 57.0°C | Modern pork is safe with pink center |
| **Beef/Lamb (whole muscle)** | 52.0°C | Rare is safe for whole muscle cuts (bacteria only on surface) |

### Time Limits

| Limit | Value | Reason |
|-------|-------|--------|
| **Minimum** | 1 minute | Practical minimum |
| **Maximum** | 5999 minutes (99h 59m) | Device limit |

### Danger Zone Warnings

**The Danger Zone:** 4°C - 60°C is where bacteria multiply rapidly.

**Rule:** If food will be below 60°C for more than 4 hours total (including heat-up time):
- Warn the user
- Suggest higher temperature
- Still allow if user confirms (edge case for advanced users)

### Validation Error Codes

These error codes MUST match the API specification (05-api-specification.md):

| Error Code | Condition | HTTP Status |
|------------|-----------|-------------|
| `TEMPERATURE_TOO_LOW` | temp < 40.0°C | 400 |
| `TEMPERATURE_TOO_HIGH` | temp > 100.0°C | 400 |
| `POULTRY_TEMP_UNSAFE` | Poultry AND temp < 57.0°C | 400 |
| `GROUND_MEAT_TEMP_UNSAFE` | Ground meat AND temp < 60.0°C | 400 |
| `TIME_TOO_SHORT` | time < 1 minute | 400 |
| `TIME_TOO_LONG` | time > 5999 minutes | 400 |

### Implementation Checklist

When implementing validators:
- [ ] Define all constants from this section
- [ ] Implement `_is_poultry()` helper function
- [ ] Implement `_is_ground_meat()` helper function
- [ ] Check absolute temperature limits FIRST
- [ ] Check food-specific limits SECOND
- [ ] Return actionable error messages
- [ ] Write tests for ALL edge cases (see test section)

---

## Anti-Patterns (What NOT to Do)

### 1. Never Log Credentials or Tokens

**BAD:**
```python
logger.info(f"Authenticating with password: {password}")  # NEVER!
logger.debug(f"Token received: {token}")                  # NEVER!
logger.info(f"Request headers: {request.headers}")        # NEVER! (contains auth)
logger.info(f"Request body: {request.json}")              # RISKY! (may contain secrets)
```

**GOOD:**
```python
logger.info("Authenticating with Anova Cloud")
logger.info("Token refresh successful")
logger.info(f"Request: {request.method} {request.path}")
# Log error codes/types, not values
logger.warning(f"Validation failed: {error.error_code}")
```

### 2. Never Trust Input Without Validation

**BAD:**
```python
@app.route('/start-cook', methods=['POST'])
def start_cook():
    # Direct use without validation!
    temp = request.json['temperature_celsius']
    client.start_cook(temp)  # What if temp is 1000°C or "abc"?
```

**GOOD:**
```python
@app.route('/start-cook', methods=['POST'])
def start_cook():
    # Validate FIRST
    validated = validate_start_cook(request.json)
    # Now safe to use
    client.start_cook(**validated)
```

### 3. Never Bypass Server-Side Safety Checks

**BAD:**
```python
# Don't trust the GPT to enforce safety
if request.json.get('override_safety'):
    # Skip validation! NO!
    pass
```

**GOOD:**
```python
# ALWAYS validate, even if GPT says it's safe
validated = validate_start_cook(request.json)
# Safety checks are non-negotiable
```

### 4. Never Hardcode Credentials

**BAD:**
```python
ANOVA_EMAIL = "user@example.com"  # Hardcoded!
ANOVA_PASSWORD = "secret123"      # In code!
API_KEY = "sk-anova-abc123"       # Committed to git!
```

**GOOD:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file (gitignored)

ANOVA_EMAIL = os.getenv('ANOVA_EMAIL')
ANOVA_PASSWORD = os.getenv('ANOVA_PASSWORD')
API_KEY = os.getenv('API_KEY')

# Validate they're set
if not all([ANOVA_EMAIL, ANOVA_PASSWORD, API_KEY]):
    raise RuntimeError("Missing required environment variables")
```

### 5. Never Use f-strings with Secrets in Logs

**BAD:**
```python
# If this gets logged, secret is exposed!
error_msg = f"Auth failed with key: {api_key}"
logger.error(error_msg)
```

**GOOD:**
```python
# Generic message, no secrets
logger.error("Authentication failed")
# Or mask the secret
logger.error(f"Auth failed with key: {api_key[:8]}...")
```

### 6. Never Catch-All Without Logging

**BAD:**
```python
try:
    result = dangerous_operation()
except Exception:
    pass  # Silent failure! Debugging nightmare!
```

**GOOD:**
```python
try:
    result = dangerous_operation()
except SpecificError as e:
    logger.error(f"Specific error occurred: {e}")
    raise  # Re-raise or handle appropriately
except Exception as e:
    logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
    raise  # Don't swallow unexpected errors
```

### 7. Never Return Raw Exception Messages to Client

**BAD:**
```python
try:
    client.start_cook(temp)
except Exception as e:
    # Raw exception might expose internal details!
    return jsonify({"error": str(e)}), 500
```

**GOOD:**
```python
try:
    client.start_cook(temp)
except AnovaAPIError as e:
    # Controlled, user-friendly message
    return jsonify({
        "error": "ANOVA_API_ERROR",
        "message": "Unable to communicate with device. Please check connection."
    }), 503
```

---

## Testing Strategy

### Testing Philosophy

1. **Unit tests for validators** - Test ALL food safety rules, edge cases, boundary conditions
2. **Integration tests for routes** - Test full request/response cycle
3. **Mock external dependencies** - Don't call real Anova API in tests
4. **Coverage requirement** - Aim for >80% coverage on validators, >60% overall

### Critical Test Cases for Validators

Reference: 03-component-architecture.md Section 7.1

| Test ID | Scenario | Input | Expected Outcome |
|---------|----------|-------|------------------|
| TC-VAL-01 | Valid parameters | temp=65, time=90 | Pass |
| TC-VAL-02 | Temp below minimum | temp=39.9 | ValidationError: TEMPERATURE_TOO_LOW |
| TC-VAL-03 | Temp above maximum | temp=100.1 | ValidationError: TEMPERATURE_TOO_HIGH |
| TC-VAL-04 | Temp exactly minimum | temp=40.0 | Pass |
| TC-VAL-05 | Temp exactly maximum | temp=100.0 | Pass |
| TC-VAL-06 | Time zero | time=0 | ValidationError: TIME_TOO_SHORT |
| TC-VAL-07 | Time negative | time=-1 | ValidationError: TIME_TOO_SHORT |
| TC-VAL-08 | Time exactly maximum | time=5999 | Pass |
| TC-VAL-09 | Time above maximum | time=6000 | ValidationError: TIME_TOO_LONG |
| TC-VAL-10 | Chicken at 56°C | temp=56, food="chicken" | ValidationError: POULTRY_TEMP_UNSAFE |
| TC-VAL-11 | Chicken at 57°C | temp=57, food="chicken" | Pass |
| TC-VAL-12 | Ground beef at 59°C | temp=59, food="ground beef" | ValidationError: GROUND_MEAT_TEMP_UNSAFE |
| TC-VAL-13 | Ground beef at 60°C | temp=60, food="ground beef" | Pass |
| TC-VAL-14 | Float time truncation | temp=65, time=90.7 | Pass (time=90) |
| TC-VAL-15 | Missing temperature | time=90 | ValidationError: MISSING_TEMPERATURE |
| TC-VAL-16 | Missing time | temp=65 | ValidationError: MISSING_TIME |

### Test File Template

```python
# tests/test_validators.py

import pytest
from server.validators import validate_start_cook
from server.exceptions import ValidationError

def test_valid_parameters():
    """TC-VAL-01: Valid parameters should pass."""
    data = {
        "temperature_celsius": 65.0,
        "time_minutes": 90
    }
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 65.0
    assert result["time_minutes"] == 90

def test_temperature_too_low():
    """TC-VAL-02: Temperature below 40°C should fail."""
    data = {
        "temperature_celsius": 39.9,
        "time_minutes": 90
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    
    assert exc_info.value.error_code == "TEMPERATURE_TOO_LOW"
    assert "danger zone" in exc_info.value.message.lower()

def test_poultry_temp_unsafe():
    """TC-VAL-10: Chicken below 57°C should fail."""
    data = {
        "temperature_celsius": 56.0,
        "time_minutes": 90,
        "food_type": "chicken"
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    
    assert exc_info.value.error_code == "POULTRY_TEMP_UNSAFE"

# ... implement all test cases from table above
```

### Mocking Anova API

```python
# tests/test_anova_client.py

import responses
import pytest
from server.anova_client import AnovaClient
from server.exceptions import DeviceOfflineError

@responses.activate
def test_start_cook_success():
    """Test successful cook start."""
    # Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-token",
            "refreshToken": "mock-refresh"
        },
        status=200
    )
    
    # Mock Anova start cook
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/abc123/start",
        json={"status": "started"},
        status=200
    )
    
    client = AnovaClient()
    result = client.start_cook(temperature=65.0, time=90)
    
    assert result["status"] == "started"

@responses.activate
def test_device_offline():
    """Test device offline scenario."""
    # Mock device status returning offline
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/abc123/status",
        json={"online": False},
        status=200
    )
    
    client = AnovaClient()
    
    with pytest.raises(DeviceOfflineError):
        client.start_cook(temperature=65.0, time=90)
```

---

## API Endpoints Reference

### POST /start-cook

**Purpose:** Start a cooking session with specified temperature and time.

**Authentication:** Required (Bearer token)

**Request Body:**
```json
{
  "temperature_celsius": 65.0,
  "time_minutes": 90,
  "food_type": "chicken"  // optional, helps with safety validation
}
```

**Success Response (200):**
```json
{
  "status": "started",
  "target_temp_celsius": 65.0,
  "time_minutes": 90,
  "device_id": "abc123"
}
```

**Error Responses:**
- 400: Validation error (TEMPERATURE_TOO_LOW, POULTRY_TEMP_UNSAFE, etc.)
- 401: Missing or invalid API key
- 409: Device already cooking (DEVICE_BUSY)
- 503: Device offline (DEVICE_OFFLINE)

---

### GET /status

**Purpose:** Get current cooking status.

**Authentication:** Required (Bearer token)

**Success Response (200):**
```json
{
  "device_online": true,
  "state": "cooking",  // idle, preheating, cooking, done
  "current_temp_celsius": 64.8,
  "target_temp_celsius": 65.0,
  "time_remaining_minutes": 47,
  "time_elapsed_minutes": 43,
  "is_running": true
}
```

**Error Responses:**
- 401: Missing or invalid API key
- 503: Device offline

---

### POST /stop-cook

**Purpose:** Stop the current cooking session.

**Authentication:** Required (Bearer token)

**Success Response (200):**
```json
{
  "status": "stopped",
  "final_temp_celsius": 64.9,
  "total_time_minutes": 85
}
```

**Error Responses:**
- 401: Missing or invalid API key
- 404: No active cook (NO_ACTIVE_COOK)
- 503: Device offline

---

### GET /health

**Purpose:** Health check for monitoring.

**Authentication:** NOT required

**Success Response (200):**
```json
{
  "status": "ok"
}
```

---

## Configuration Management

### Development (.env file)

```bash
# .env (gitignored)

ANOVA_EMAIL=your-email@example.com
ANOVA_PASSWORD=your-password
DEVICE_ID=your-device-id
API_KEY=sk-anova-your-generated-key
DEBUG=true
```

### Production (Encrypted File)

**Reference:** 02-security-architecture.md Section 4.3

Production uses an encrypted JSON file to persist credentials across reboots:

```python
# config.py (production)

from cryptography.fernet import Fernet
import json
import os

def load_encrypted_config(filepath: str) -> dict:
    """Load encrypted configuration file."""
    # Encryption key derived from hardware or environment
    key = os.getenv('ENCRYPTION_KEY')
    fernet = Fernet(key)
    
    with open(filepath, 'rb') as f:
        encrypted = f.read()
    
    decrypted = fernet.decrypt(encrypted)
    return json.loads(decrypted)

def save_encrypted_config(filepath: str, config: dict):
    """Save configuration as encrypted file."""
    key = os.getenv('ENCRYPTION_KEY')
    fernet = Fernet(key)
    
    plaintext = json.dumps(config).encode()
    encrypted = fernet.encrypt(plaintext)
    
    with open(filepath, 'wb') as f:
        f.write(encrypted)
    
    # Set restrictive permissions (owner read/write only)
    os.chmod(filepath, 0o600)
```

---

## Implementation Phases

See `IMPLEMENTATION.md` for detailed phase breakdown.

**Quick Summary:**

1. **Phase 1: Core Server** - Flask app, validators, mock responses (2-4 hours)
2. **Phase 2: Anova Integration** - Real device control (4-8 hours)
3. **Phase 3: Security & Polish** - API key auth, logging (2-4 hours)
4. **Phase 4: Deployment** - Raspberry Pi, Cloudflare Tunnel (2-4 hours)

---

## Common Gotchas

### 1. Token Expiration

Firebase tokens expire. Implement token refresh logic:

```python
# anova_client.py

def _ensure_valid_token(self):
    """Refresh token if expired."""
    if self._token_expired():
        self._refresh_token()
```

### 2. Device State Management

Always check device state before operations:

```python
def start_cook(self, temp, time):
    status = self.get_status()
    if status['is_running']:
        raise DeviceAlreadyCookingError()
```

### 3. Type Coercion

ChatGPT might send `"65"` (string) instead of `65` (number). Validators must handle this:

```python
try:
    temp = float(data["temperature_celsius"])
except (TypeError, ValueError):
    raise ValidationError("INVALID_TEMPERATURE", "Must be a number")
```

### 4. Cloudflare Tunnel URL

The tunnel URL is auto-generated. Update Custom GPT Actions when it changes.

---

## References

- **API Specification:** See project knowledge base `05-api-specification.md`
- **Component Architecture:** See `03-component-architecture.md`
- **Security Architecture:** See `02-security-architecture.md`
- **Food Safety Rules:** See `kb-domain-knowledge.md`
- **Deployment Guide:** See `07-deployment-architecture.md`

---

## Getting Help

If you encounter issues during implementation:

1. Check the relevant specification document in the knowledge base
2. Verify configuration (.env file)
3. Check logs for error details
4. Review this file for patterns and anti-patterns
5. Ensure food safety rules are being enforced

**Remember:** Food safety is paramount. When in doubt, reject the request with a clear error message.
