# 03 - Component Architecture

> **Document Type:** C4 Level 2/3 - Component Architecture  
> **Status:** Draft  
> **Version:** 2.0 (Merged)  
> **Last Updated:** 2025-01-08  
> **Depends On:** 01-System Context, 02-Security Architecture  
> **Blocks:** 05-API Specification, Implementation

---

## 1. Overview

This document describes the internal component structure of the Anova Control Server, defining component responsibilities, interfaces, and interactions. The architecture uses a **layered design** with clear separation of concerns.

**Design Principles:**
- Single responsibility per component
- Explicit dependencies (no global state)
- Fail-safe defaults (reject if uncertain)
- Clear error propagation
- Minimal external dependencies

---

## 2. Component Diagram (C4 Level 2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANOVA CONTROL SERVER                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        API LAYER                                     │   │
│  │                                                                      │   │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │   │ /start-cook  │  │ /status      │  │ /stop-cook   │             │   │
│  │   │ Handler      │  │ Handler      │  │ Handler      │             │   │
│  │   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │   │
│  │          │                 │                 │                      │   │
│  │   ┌──────┴─────────────────┴─────────────────┴───────┐             │   │
│  │   │              Request Validator                    │             │   │
│  │   │              (includes Auth Middleware)           │             │   │
│  │   └──────────────────────┬───────────────────────────┘             │   │
│  └──────────────────────────┼───────────────────────────────────────────┘   │
│                             │                                               │
│  ┌──────────────────────────┼───────────────────────────────────────────┐   │
│  │                     SERVICE LAYER                                    │   │
│  │                          │                                           │   │
│  │   ┌──────────────────────▼───────────────────────┐                  │   │
│  │   │              Cook Controller                  │                  │   │
│  │   │                                               │                  │   │
│  │   │  • Orchestrates cooking operations            │                  │   │
│  │   │  • Manages cook session state                 │                  │   │
│  │   │  • Coordinates validation and device calls    │                  │   │
│  │   └──────────────────────┬───────────────────────┘                  │   │
│  │                          │                                           │   │
│  │   ┌──────────────────────┼───────────────────────┐                  │   │
│  │   │                      │                       │                  │   │
│  │   ▼                      ▼                       ▼                  │   │
│  │ ┌────────────┐    ┌────────────┐    ┌────────────────────┐         │   │
│  │ │ Safety     │    │ Session    │    │ Response           │         │   │
│  │ │ Validator  │    │ Manager    │    │ Formatter          │         │   │
│  │ │            │    │            │    │                    │         │   │
│  │ │ • Temp     │    │ • cook_id  │    │ • JSON structure   │         │   │
│  │ │   limits   │    │ • state    │    │ • Error mapping    │         │   │
│  │ │ • Time     │    │            │    │ • Timestamps       │         │   │
│  │ │   limits   │    │            │    │                    │         │   │
│  │ │ • Food     │    │            │    │                    │         │   │
│  │ │   safety   │    │            │    │                    │         │   │
│  │ └────────────┘    └────────────┘    └────────────────────┘         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                               │
│  ┌──────────────────────────┼───────────────────────────────────────────┐   │
│  │                  INTEGRATION LAYER                                   │   │
│  │                          │                                           │   │
│  │   ┌──────────────────────▼───────────────────────┐                  │   │
│  │   │              Anova Client                     │                  │   │
│  │   │                                               │                  │   │
│  │   │  • Authentication with Firebase               │                  │   │
│  │   │  • Device discovery                           │                  │   │
│  │   │  • Command execution                          │                  │   │
│  │   │  • Status polling                             │                  │   │
│  │   └──────────────────────┬───────────────────────┘                  │   │
│  │                          │                                           │   │
│  │   ┌──────────────────────┼───────────────────────┐                  │   │
│  │   │                      │                       │                  │   │
│  │   ▼                      ▼                       ▼                  │   │
│  │ ┌────────────┐    ┌────────────┐    ┌────────────────────┐         │   │
│  │ │ Auth       │    │ Device     │    │ Connection         │         │   │
│  │ │ Manager    │    │ Adapter    │    │ Manager            │         │   │
│  │ │            │    │            │    │                    │         │   │
│  │ │ • Token    │    │ • Commands │    │ • Retry logic      │         │   │
│  │ │   refresh  │    │ • Mapping  │    │ • Timeout          │         │   │
│  │ │ • Creds    │    │ • Parsing  │    │ • Keep-alive       │         │   │
│  │ └────────────┘    └────────────┘    └────────────────────┘         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                             │                                               │
│  ┌──────────────────────────┼───────────────────────────────────────────┐   │
│  │                  INFRASTRUCTURE LAYER                                │   │
│  │                          │                                           │   │
│  │   ┌──────────┐    ┌──────┴─────┐    ┌────────────┐                  │   │
│  │   │ Config   │    │ Logger     │    │ Health     │                  │   │
│  │   │ Manager  │    │            │    │ Monitor    │                  │   │
│  │   └──────────┘    └────────────┘    └────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS
                                    ▼
                          ┌──────────────────┐
                          │   Anova Cloud    │
                          │   (Firebase)     │
                          └──────────────────┘
```

---

## 3. File Structure

```
anova-assistant/
├── server/
│   ├── __init__.py
│   ├── app.py                 # Application factory, entry point
│   ├── routes.py              # HTTP route handlers (API Layer)
│   ├── validators.py          # Input & safety validation (Service Layer)
│   ├── anova_client.py        # Anova Cloud API client (Integration Layer)
│   ├── config.py              # Configuration management (Infrastructure)
│   ├── middleware.py          # Auth, logging, error handling
│   └── exceptions.py          # Custom exception definitions
│
├── config/
│   ├── .env.example           # Template for development
│   └── credentials.enc        # Encrypted production config (gitignored)
│
├── tests/
│   ├── __init__.py
│   ├── test_validators.py     # Validation unit tests
│   ├── test_routes.py         # Route integration tests
│   ├── test_anova_client.py   # Client tests with mocks
│   └── conftest.py            # Pytest fixtures
│
├── deployment/
│   ├── anova-server.service   # systemd service file
│   └── setup_pi.sh            # Raspberry Pi setup script
│
├── .env.example               # Environment template
├── .gitignore                 # Ignore secrets, venv, etc.
├── requirements.txt           # Python dependencies
└── README.md                  # Setup instructions
```

---

## 4. Component Specifications

### 4.1 API Layer

#### 4.1.1 app.py - Application Entry Point

**Component ID:** COMP-APP-01  
**Responsibility:** Bootstrap the Flask application and wire components together.

**Interface:**
```python
# app.py

from flask import Flask
from config import Config
from routes import register_routes
from middleware import register_middleware

def create_app(config: Config | None = None) -> Flask:
    """
    Application factory pattern.
    
    Args:
        config: Optional config override for testing
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    if config is None:
        config = Config.load()
    
    app.config.from_object(config)
    
    register_middleware(app)
    register_routes(app)
    
    return app

# Entry point for development
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
```

**Lifecycle:**
- **Startup:** Load config → Initialize Anova client → Start Flask
- **Shutdown:** Graceful connection cleanup (if any persistent connections)

#### 4.1.2 routes.py - HTTP Route Handlers

**Component ID:** COMP-ROUTE-01  
**Responsibility:** Define API endpoints and orchestrate request handling.

**Dependencies:**
| Dependency | Type | Purpose |
|------------|------|---------|
| validators.py | Internal | Input validation |
| anova_client.py | Internal | Device commands |
| config.py | Internal | Settings |

**Interface Contract:**

| Handler | Input | Output | Errors |
|---------|-------|--------|--------|
| StartCookHandler | HTTP POST with JSON body | HTTP Response (200/400/409/503) | Validation, Device |
| StatusHandler | HTTP GET (no parameters) | HTTP Response (200/503) | Device offline |
| StopCookHandler | HTTP POST (no body required) | HTTP Response (200/409/503) | No active cook, Device |
| HealthHandler | HTTP GET (no parameters) | HTTP Response (200) | None |

**Implementation:**
```python
# routes.py

from flask import Flask, request, jsonify
from validators import validate_cook_params, ValidationError
from anova_client import AnovaClient, AnovaError, DeviceOfflineError, DeviceBusyError
from middleware import require_api_key

def register_routes(app: Flask) -> None:
    """Register all API routes with the Flask app."""
    
    # Dependency: Anova client instance
    anova = AnovaClient(app.config)
    
    @app.route("/health", methods=["GET"])
    def health():
        """
        Health check - no auth required.
        Satisfies: FR-06 (partial), QR-10
        """
        return jsonify({
            "status": "ok", 
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    @app.route("/start-cook", methods=["POST"])
    @require_api_key
    def start_cook():
        """
        Start a cooking session.
        Satisfies: FR-01, FR-04, FR-05, FR-07, FR-08
        """
        data = request.get_json()
        
        # Validate (includes food safety checks)
        try:
            params = validate_cook_params(data)
        except ValidationError as e:
            return jsonify({"error": e.code, "message": e.message}), 400
        
        # Execute
        try:
            result = anova.start_cook(
                temperature_c=params.temperature_celsius,
                time_minutes=params.time_minutes
            )
        except DeviceBusyError as e:
            return jsonify({"error": e.code, "message": e.message}), 409
        except DeviceOfflineError as e:
            return jsonify({"error": e.code, "message": e.message}), 503
        except AnovaError as e:
            return jsonify({"error": e.code, "message": e.message}), e.status_code
        
        return jsonify(result)
    
    @app.route("/status", methods=["GET"])
    @require_api_key
    def get_status():
        """
        Get current cooking status.
        Satisfies: FR-02, FR-06
        """
        try:
            status = anova.get_status()
        except DeviceOfflineError as e:
            return jsonify({"error": e.code, "message": e.message}), 503
        except AnovaError as e:
            return jsonify({"error": e.code, "message": e.message}), e.status_code
        
        return jsonify(status)
    
    @app.route("/stop-cook", methods=["POST"])
    @require_api_key
    def stop_cook():
        """
        Stop current cooking session.
        Satisfies: FR-03, FR-06
        """
        try:
            result = anova.stop_cook()
        except DeviceOfflineError as e:
            return jsonify({"error": e.code, "message": e.message}), 503
        except AnovaError as e:
            return jsonify({"error": e.code, "message": e.message}), e.status_code
        
        return jsonify(result)
```

#### 4.1.3 middleware.py - Cross-Cutting Concerns

**Component ID:** COMP-MW-01  
**Responsibility:** Handle authentication, logging, and error handling.

**Implementation:**
```python
# middleware.py

from flask import Flask, request, g, jsonify
from functools import wraps
import time
import logging
import hmac

logger = logging.getLogger(__name__)

def register_middleware(app: Flask) -> None:
    """Register all middleware with the Flask app."""
    
    @app.before_request
    def before_request():
        """Run before each request."""
        g.start_time = time.time()
        
        # Log request (without sensitive data)
        logger.info(f"Request: {request.method} {request.path}")
    
    @app.after_request
    def after_request(response):
        """Run after each request."""
        duration = time.time() - g.get("start_time", time.time())
        logger.info(f"Response: {response.status_code} ({duration:.3f}s)")
        return response
    
    @app.errorhandler(Exception)
    def handle_error(error):
        """Global error handler."""
        logger.exception("Unhandled exception")
        return jsonify({
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        }), 500

def require_api_key(f):
    """
    Decorator to require API key authentication.
    Satisfies: SEC-REQ-01, QR-33
    
    Usage:
        @app.route("/protected")
        @require_api_key
        def protected_route():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import current_app
        
        api_key = current_app.config.get("API_KEY")
        
        # If no API key configured, allow all requests (dev mode)
        if not api_key:
            logger.warning("API key not configured - allowing unauthenticated access")
            return f(*args, **kwargs)
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Missing or invalid Authorization header"
            }), 401
        
        provided_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # Constant-time comparison to prevent timing attacks (SEC-REQ-06)
        if not hmac.compare_digest(provided_key, api_key):
            logger.warning("Invalid API key attempt")
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid API key"
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated
```

---

### 4.2 Service Layer

#### 4.2.1 validators.py - Input & Safety Validation

**Component ID:** COMP-VAL-01  
**Responsibility:** Validate all inputs. This is a SECURITY BOUNDARY.

**This component satisfies:** FR-04, FR-05, FR-07, FR-08, SEC-REQ-05

**Implementation:**
```python
# validators.py

from dataclasses import dataclass
from typing import Any

class ValidationError(Exception):
    """Raised when input validation fails."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

@dataclass
class CookParams:
    """Validated cooking parameters."""
    temperature_celsius: float
    time_minutes: int
    food_type: str | None = None

# Safety constants (from kb-domain-knowledge.md)
MIN_TEMP_CELSIUS = 40.0      # Below: danger zone
MAX_TEMP_CELSIUS = 100.0     # Above: water boils
MIN_TIME_MINUTES = 1
MAX_TIME_MINUTES = 5999      # 99h 59m (Anova limit)

# Food-specific minimums (CRITICAL SAFETY RULES)
POULTRY_MIN_TEMP = 57.0      # With extended time (3+ hours)
POULTRY_SAFE_TEMP = 65.0     # Standard safe
GROUND_MEAT_MIN_TEMP = 60.0  # Bacteria throughout
PORK_MIN_TEMP = 57.0         # Modern recommendation

def validate_cook_params(data: dict[str, Any] | None) -> CookParams:
    """
    Validate cooking parameters.
    
    Args:
        data: Raw request data (may be None or malformed)
        
    Returns:
        CookParams with validated values
        
    Raises:
        ValidationError: If any validation fails
        
    Satisfies: FR-04, FR-05, FR-07, FR-08
    """
    if data is None:
        raise ValidationError("MISSING_BODY", "Request body is required")
    
    # === Temperature validation ===
    temp = data.get("temperature_celsius")
    if temp is None:
        raise ValidationError("MISSING_TEMPERATURE", "temperature_celsius is required")
    
    try:
        temp = float(temp)
    except (TypeError, ValueError):
        raise ValidationError("INVALID_TEMPERATURE", "temperature_celsius must be a number")
    
    # VAL-T01: Absolute minimum
    if temp < MIN_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_LOW",
            f"Temperature {temp}°C is below the safe minimum of {MIN_TEMP_CELSIUS}°C. "
            f"Food below this temperature is in the bacterial danger zone."
        )
    
    # VAL-T02: Absolute maximum
    if temp > MAX_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_HIGH",
            f"Temperature {temp}°C exceeds the safe maximum of {MAX_TEMP_CELSIUS}°C. "
            f"Water boils at 100°C."
        )
    
    # === Time validation ===
    time_min = data.get("time_minutes")
    if time_min is None:
        raise ValidationError("MISSING_TIME", "time_minutes is required")
    
    try:
        # VAL-TM03: Truncate floats to integer
        time_min = int(float(time_min))
    except (TypeError, ValueError):
        raise ValidationError("INVALID_TIME", "time_minutes must be a number")
    
    # VAL-TM01: Minimum time
    if time_min < MIN_TIME_MINUTES:
        raise ValidationError("TIME_TOO_SHORT", f"Time must be at least {MIN_TIME_MINUTES} minute")
    
    # VAL-TM02: Maximum time
    if time_min > MAX_TIME_MINUTES:
        raise ValidationError(
            "TIME_TOO_LONG",
            f"Time {time_min} minutes exceeds maximum of {MAX_TIME_MINUTES} minutes (99h 59m)"
        )
    
    # === Food type extraction (optional, for safety context) ===
    food_type = data.get("food_type")
    if food_type is not None:
        food_type = str(food_type).lower().strip()
        if len(food_type) > 100:
            food_type = food_type[:100]
        
        # VAL-T03: Food-specific safety checks
        if _is_poultry(food_type) and temp < POULTRY_MIN_TEMP:
            raise ValidationError(
                "POULTRY_TEMP_UNSAFE",
                f"Temperature {temp}°C is not safe for poultry. "
                f"Minimum is {POULTRY_MIN_TEMP}°C with extended time (3+ hours) "
                f"or {POULTRY_SAFE_TEMP}°C for standard cooking."
            )
        
        # VAL-T04: Ground meat safety
        if _is_ground_meat(food_type) and temp < GROUND_MEAT_MIN_TEMP:
            raise ValidationError(
                "GROUND_MEAT_TEMP_UNSAFE",
                f"Temperature {temp}°C is not safe for ground meat. "
                f"Minimum is {GROUND_MEAT_MIN_TEMP}°C because bacteria are mixed throughout."
            )
    
    return CookParams(
        temperature_celsius=round(temp, 1),
        time_minutes=time_min,
        food_type=food_type
    )

def _is_poultry(food_type: str) -> bool:
    """Check if food type is poultry."""
    poultry_keywords = ["chicken", "turkey", "duck", "poultry", "hen", "fowl", "goose"]
    return any(kw in food_type for kw in poultry_keywords)

def _is_ground_meat(food_type: str) -> bool:
    """Check if food type is ground meat."""
    ground_keywords = ["ground", "minced", "burger", "meatball", "sausage", "mince"]
    return any(kw in food_type for kw in ground_keywords)
```

**Validation Rules Matrix:**

| Rule ID | Rule | Condition | Error Code | Rationale |
|---------|------|-----------|------------|-----------|
| VAL-T01 | Temp minimum | temp < 40.0 | TEMPERATURE_TOO_LOW | Danger zone |
| VAL-T02 | Temp maximum | temp > 100.0 | TEMPERATURE_TOO_HIGH | Water boils |
| VAL-T03 | Poultry safety | poultry AND temp < 57.0 | POULTRY_TEMP_UNSAFE | Pasteurization |
| VAL-T04 | Ground meat safety | ground AND temp < 60.0 | GROUND_MEAT_TEMP_UNSAFE | Bacteria throughout |
| VAL-TM01 | Time minimum | time < 1 | TIME_TOO_SHORT | Minimum useful |
| VAL-TM02 | Time maximum | time > 5999 | TIME_TOO_LONG | Device limit |
| VAL-TM03 | Float truncation | 90.5 → 90 | N/A | Normalization |
| VAL-S01 | String length | food_type > 100 | Truncate | Prevent abuse |

---

### 4.3 Integration Layer

#### 4.3.1 anova_client.py - Anova Cloud Client

**Component ID:** COMP-ANOVA-01  
**Responsibility:** Abstract all Anova Cloud API interactions.

**Implementation:**
```python
# anova_client.py

import requests
from dataclasses import dataclass
from typing import Any
from config import Config
import time
import logging

logger = logging.getLogger(__name__)

# === Exception Hierarchy ===

class AnovaError(Exception):
    """Base exception for Anova API errors."""
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class DeviceOfflineError(AnovaError):
    """Device is not connected to Anova Cloud."""
    def __init__(self, message: str = "Device is offline or not connected to WiFi. Please check that the Anova is plugged in and connected to your WiFi network."):
        super().__init__("DEVICE_OFFLINE", message, 503)

class DeviceBusyError(AnovaError):
    """Device already has an active cooking session."""
    def __init__(self, message: str = "Device already has an active cooking session. Stop the current cook first, or wait for it to complete."):
        super().__init__("DEVICE_BUSY", message, 409)

class AuthenticationError(AnovaError):
    """Failed to authenticate with Anova."""
    def __init__(self, message: str = "Failed to authenticate with Anova. Please verify credentials."):
        super().__init__("AUTH_FAILED", message, 502)

class NoActiveCookError(AnovaError):
    """No active cooking session to stop."""
    def __init__(self, message: str = "No active cooking session to stop."):
        super().__init__("NO_ACTIVE_COOK", message, 409)

# === Data Classes ===

@dataclass
class DeviceStatus:
    """Current device state."""
    state: str                    # "idle", "preheating", "cooking", "done"
    current_temp_celsius: float
    target_temp_celsius: float | None
    time_remaining_minutes: int | None
    time_elapsed_minutes: int | None
    is_running: bool

# === Client Implementation ===

class AnovaClient:
    """
    Client for Anova Cloud API.
    
    Handles authentication, token refresh, and device commands.
    """
    
    # API endpoints (to be confirmed via research)
    FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
    ANOVA_API_BASE = "https://api.anovaculinary.com"  # Placeholder - verify via research
    
    # Firebase API key for Anova app (to be researched)
    FIREBASE_API_KEY = "AIzaSyDQiOP2fTR9zvFcag2kSbcmG9zPh6gZhHw"  # Placeholder
    
    def __init__(self, config: Config):
        self.config = config
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0
        
        # HTTP session for connection reuse
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def _ensure_authenticated(self) -> str:
        """
        Ensure we have a valid access token.
        
        Returns:
            Valid access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Check if current token is still valid (5 min buffer)
        if self._access_token and time.time() < self._token_expiry - 300:
            return self._access_token
        
        # Try to refresh if we have a refresh token
        if self._refresh_token:
            try:
                self._refresh_access_token()
                return self._access_token
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}, re-authenticating")
        
        # Full authentication
        self._authenticate()
        return self._access_token
    
    def _authenticate(self) -> None:
        """
        Authenticate with Firebase using email/password.
        
        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("Authenticating with Anova...")
        
        try:
            response = self._session.post(
                f"{self.FIREBASE_AUTH_URL}?key={self.FIREBASE_API_KEY}",
                json={
                    "email": self.config.ANOVA_EMAIL,
                    "password": self.config.ANOVA_PASSWORD,
                    "returnSecureToken": True
                },
                timeout=10
            )
            
            if response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                raise AuthenticationError(f"Firebase auth failed: {error_msg}")
            
            if response.status_code != 200:
                raise AuthenticationError(f"Firebase auth failed: HTTP {response.status_code}")
            
            data = response.json()
            self._access_token = data["idToken"]
            self._refresh_token = data["refreshToken"]
            self._token_expiry = time.time() + int(data.get("expiresIn", 3600))
            
            logger.info("Successfully authenticated with Anova")
            
        except requests.RequestException as e:
            raise AuthenticationError(f"Network error during authentication: {e}")
    
    def _refresh_access_token(self) -> None:
        """
        Refresh the access token using refresh token.
        
        Raises:
            AuthenticationError: If refresh fails
        """
        logger.debug("Refreshing access token...")
        
        try:
            response = self._session.post(
                f"{self.FIREBASE_REFRESH_URL}?key={self.FIREBASE_API_KEY}",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token
                },
                timeout=10
            )
            
            if response.status_code != 200:
                raise AuthenticationError("Token refresh failed")
            
            data = response.json()
            self._access_token = data["id_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._token_expiry = time.time() + int(data.get("expires_in", 3600))
            
            logger.debug("Successfully refreshed access token")
            
        except requests.RequestException as e:
            raise AuthenticationError(f"Network error during token refresh: {e}")
    
    def _api_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make authenticated request to Anova API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            **kwargs: Additional arguments to requests
            
        Returns:
            JSON response data
            
        Raises:
            AnovaError: On API errors
        """
        token = self._ensure_authenticated()
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.ANOVA_API_BASE}{endpoint}"
        
        try:
            response = self._session.request(
                method,
                url,
                headers=headers,
                timeout=kwargs.pop("timeout", 15),
                **kwargs
            )
            
            # Handle token expiry during request
            if response.status_code == 401:
                logger.warning("Token expired during request, re-authenticating")
                self._access_token = None
                token = self._ensure_authenticated()
                headers["Authorization"] = f"Bearer {token}"
                response = self._session.request(method, url, headers=headers, **kwargs)
            
            # Map Anova errors to our exceptions
            if response.status_code == 404:
                raise DeviceOfflineError()
            
            if response.status_code == 409:
                raise DeviceBusyError()
            
            if response.status_code >= 400:
                raise AnovaError(
                    "ANOVA_API_ERROR",
                    f"Anova API error: {response.status_code}",
                    502
                )
            
            return response.json() if response.content else {}
            
        except requests.Timeout:
            raise AnovaError("TIMEOUT", "Request to Anova timed out", 503)
        except requests.RequestException as e:
            raise AnovaError("NETWORK_ERROR", f"Network error: {e}", 503)
    
    def get_status(self) -> dict:
        """
        Get current device status.
        
        Returns:
            Status dictionary with state, temps, timers
            
        Raises:
            AnovaError: On API errors
            
        Satisfies: FR-02
        """
        data = self._api_request("GET", f"/devices/{self.config.DEVICE_ID}/status")
        
        # Map Anova response to our format
        state = self._map_state(data.get("state"))
        is_running = state in ["preheating", "cooking"]
        
        return {
            "device_online": True,
            "state": state,
            "current_temp_celsius": data.get("current_temp"),
            "target_temp_celsius": data.get("target_temp"),
            "time_remaining_minutes": data.get("time_remaining"),
            "time_elapsed_minutes": data.get("time_elapsed"),
            "is_running": is_running
        }
    
    def start_cook(self, temperature_c: float, time_minutes: int) -> dict:
        """
        Start a cooking session.
        
        Args:
            temperature_c: Target temperature in Celsius
            time_minutes: Cook time in minutes
            
        Returns:
            Result dictionary with success status
            
        Raises:
            DeviceBusyError: If device already cooking
            DeviceOfflineError: If device not reachable
            AnovaError: On other API errors
            
        Satisfies: FR-01
        """
        import uuid
        from datetime import datetime, timedelta
        
        data = self._api_request(
            "POST",
            f"/devices/{self.config.DEVICE_ID}/cook",
            json={
                "target_temp": temperature_c,
                "timer": time_minutes * 60  # API may expect seconds
            }
        )
        
        # Generate cook_id if not provided by API
        cook_id = data.get("cook_id") or str(uuid.uuid4())
        
        # Calculate estimated completion
        estimated_completion = datetime.utcnow() + timedelta(minutes=time_minutes + 15)  # +15 for preheat
        
        return {
            "success": True,
            "message": f"Started cooking at {temperature_c}°C for {time_minutes} minutes. Water heating to target temperature.",
            "cook_id": cook_id,
            "device_state": "preheating",
            "target_temp_celsius": temperature_c,
            "time_minutes": time_minutes,
            "estimated_completion": estimated_completion.isoformat() + "Z"
        }
    
    def stop_cook(self) -> dict:
        """
        Stop current cooking session.
        
        Returns:
            Result dictionary
            
        Raises:
            DeviceOfflineError: If device not reachable
            AnovaError: On other API errors
            
        Satisfies: FR-03
        """
        self._api_request("POST", f"/devices/{self.config.DEVICE_ID}/stop")
        
        return {
            "success": True,
            "message": "Cooking stopped",
            "device_state": "idle"
        }
    
    def _map_state(self, anova_state: str | None) -> str:
        """Map Anova's state values to our standard states."""
        state_map = {
            "off": "idle",
            "idle": "idle",
            "preheating": "preheating",
            "heating": "preheating",
            "maintaining": "cooking",
            "cooking": "cooking",
            "holding": "cooking",
            "done": "done",
            "timer_done": "done",
            "complete": "done"
        }
        return state_map.get(anova_state, "unknown") if anova_state else "unknown"
```

---

### 4.4 Infrastructure Layer

#### 4.4.1 config.py - Configuration Management

**Component ID:** COMP-CFG-01  
**Responsibility:** Load and provide configuration from various sources.

**Implementation:**
```python
# config.py

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Application configuration."""
    
    # Anova credentials (CRED-01, CRED-02)
    ANOVA_EMAIL: str
    ANOVA_PASSWORD: str
    DEVICE_ID: str
    
    # Optional API key for ChatGPT auth (CRED-05)
    API_KEY: str | None = None
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    DEBUG: bool = False
    
    # Safety limits (not configurable - from kb-domain-knowledge.md)
    MIN_TEMP_CELSIUS: float = 40.0
    MAX_TEMP_CELSIUS: float = 100.0
    MAX_TIME_MINUTES: int = 5999
    
    @classmethod
    def load(cls) -> Self:
        """
        Load configuration from environment or encrypted file.
        
        Environment variables take precedence if set.
        Falls back to encrypted config file in production.
        
        Returns:
            Config instance
            
        Raises:
            ValueError: If required config is missing
        """
        # Try environment first (development)
        if os.getenv("ANOVA_EMAIL"):
            logger.info("Loading configuration from environment variables")
            return cls._from_env()
        
        # Try encrypted file (production)
        config_path = Path(__file__).parent.parent / "config" / "credentials.enc"
        if config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            return cls._from_encrypted_file(config_path)
        
        # Try plain JSON for development (gitignored)
        plain_config = Path(__file__).parent.parent / "config" / "credentials.json"
        if plain_config.exists():
            logger.warning("Loading from plain JSON config - use encrypted file in production!")
            return cls._from_json_file(plain_config)
        
        raise ValueError(
            "Configuration not found. Set ANOVA_EMAIL, ANOVA_PASSWORD, "
            "and DEVICE_ID environment variables, or provide credentials.enc"
        )
    
    @classmethod
    def _from_env(cls) -> Self:
        """Load config from environment variables."""
        email = os.environ.get("ANOVA_EMAIL")
        password = os.environ.get("ANOVA_PASSWORD")
        device_id = os.environ.get("DEVICE_ID")
        
        if not all([email, password, device_id]):
            missing = [k for k, v in [("ANOVA_EMAIL", email), ("ANOVA_PASSWORD", password), ("DEVICE_ID", device_id)] if not v]
            raise ValueError(f"Missing required environment variables: {missing}")
        
        return cls(
            ANOVA_EMAIL=email,
            ANOVA_PASSWORD=password,
            DEVICE_ID=device_id,
            API_KEY=os.environ.get("API_KEY"),
            DEBUG=os.environ.get("DEBUG", "").lower() == "true"
        )
    
    @classmethod
    def _from_json_file(cls, path: Path) -> Self:
        """Load config from plain JSON file (development only)."""
        with open(path) as f:
            data = json.load(f)
        
        return cls(
            ANOVA_EMAIL=data["anova_email"],
            ANOVA_PASSWORD=data["anova_password"],
            DEVICE_ID=data["device_id"],
            API_KEY=data.get("api_key"),
            DEBUG=data.get("debug", False)
        )
    
    @classmethod
    def _from_encrypted_file(cls, path: Path) -> Self:
        """
        Load config from encrypted file.
        
        Uses AES-256-GCM with key derived from machine identifier.
        """
        # Implementation depends on chosen encryption library
        # Placeholder - implement with cryptography library
        raise NotImplementedError(
            "Encrypted config loading not yet implemented. "
            "Use environment variables or plain JSON for now."
        )
```

#### 4.4.2 exceptions.py - Custom Exceptions

**Component ID:** COMP-EXC-01  
**Responsibility:** Define domain-specific exceptions.

```python
# exceptions.py

class AnovaAssistantError(Exception):
    """Base exception for all application errors."""
    pass

class ConfigurationError(AnovaAssistantError):
    """Configuration is missing or invalid."""
    pass

class ValidationError(AnovaAssistantError):
    """Input validation failed."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class AnovaError(AnovaAssistantError):
    """Error communicating with Anova Cloud."""
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class DeviceOfflineError(AnovaError):
    """Device is not connected."""
    def __init__(self, message: str = "Device is offline"):
        super().__init__("DEVICE_OFFLINE", message, 503)

class DeviceBusyError(AnovaError):
    """Device already has an active cook."""
    def __init__(self, message: str = "Device is busy"):
        super().__init__("DEVICE_BUSY", message, 409)

class AuthenticationError(AnovaError):
    """Authentication with Anova failed."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__("AUTH_FAILED", message, 502)
```

---

## 5. Component Interaction Sequences

### 5.1 Start Cook Sequence

```
User          ChatGPT         Server          Validator       AnovaClient      Anova Cloud
  │              │               │                │                │                │
  │ "Cook steak" │               │                │                │                │
  │─────────────►│               │                │                │                │
  │              │ POST /start-cook               │                │                │
  │              │ {temp:54, time:120}            │                │                │
  │              │──────────────►│                │                │                │
  │              │               │                │                │                │
  │              │               │ validate()     │                │                │
  │              │               │───────────────►│                │                │
  │              │               │                │                │                │
  │              │               │   CookParams   │                │                │
  │              │               │◄───────────────│                │                │
  │              │               │                │                │                │
  │              │               │ start_cook()   │                │                │
  │              │               │───────────────────────────────►│                │
  │              │               │                │                │                │
  │              │               │                │                │ API call       │
  │              │               │                │                │───────────────►│
  │              │               │                │                │     200 OK     │
  │              │               │                │                │◄───────────────│
  │              │               │                │                │                │
  │              │               │    Result      │                │                │
  │              │               │◄───────────────────────────────│                │
  │              │               │                │                │                │
  │              │  200 OK       │                │                │                │
  │              │  {success:true}                │                │                │
  │              │◄──────────────│                │                │                │
  │              │               │                │                │                │
  │ "Started!"   │               │                │                │                │
  │◄─────────────│               │                │                │                │
```

### 5.2 Validation Failure Sequence

```
User          ChatGPT         Server          Validator
  │              │               │                │
  │ "Cook chicken│               │                │
  │  at 50°C"    │               │                │
  │─────────────►│               │                │
  │              │ POST /start-cook               │
  │              │ {temp:50, food:"chicken"}      │
  │              │──────────────►│                │
  │              │               │                │
  │              │               │ validate()     │
  │              │               │───────────────►│
  │              │               │                │
  │              │               │ ValidationError│
  │              │               │ POULTRY_TEMP_  │
  │              │               │ UNSAFE         │
  │              │               │◄───────────────│
  │              │               │                │
  │              │  400 Bad Request               │
  │              │  {error: "POULTRY_TEMP_UNSAFE",│
  │              │   message: "Temp 50°C not safe │
  │              │   for poultry. Min is 57°C..."}│
  │              │◄──────────────│                │
  │              │               │                │
  │ "That temp   │               │                │
  │  isn't safe" │               │                │
  │◄─────────────│               │                │
```

---

## 6. Error Propagation

| Layer | Error Handling | Propagation |
|-------|----------------|-------------|
| API | Catch all exceptions, map to ErrorResponse | Return HTTP status + JSON |
| Service | Throw ValidationError | Caught by API layer |
| Integration | Throw AnovaError subclasses | Caught by API layer |
| Infrastructure | Log and propagate | Caught by API layer |

---

## 7. Test Strategy by Component

| Component ID | Component | Unit Tests | Integration Tests | Mock Dependencies |
|--------------|-----------|------------|-------------------|-------------------|
| COMP-ROUTE-01 | routes.py | HTTP request/response | Full API calls | Service layer |
| COMP-VAL-01 | validators.py | All validation rules | N/A | None |
| COMP-ANOVA-01 | anova_client.py | Error handling | With real API (manual) | HTTP responses |
| COMP-CFG-01 | config.py | Loading, merging | N/A | File system |
| COMP-MW-01 | middleware.py | Auth decorator | With routes | None |

### 7.1 Critical Test Cases for Validators

| Test ID | Scenario | Input | Expected |
|---------|----------|-------|----------|
| TC-VAL-01 | Valid parameters | temp=65, time=90 | Pass |
| TC-VAL-02 | Temp below minimum | temp=39.9 | Fail: TEMPERATURE_TOO_LOW |
| TC-VAL-03 | Temp above maximum | temp=100.1 | Fail: TEMPERATURE_TOO_HIGH |
| TC-VAL-04 | Temp exactly minimum | temp=40.0 | Pass |
| TC-VAL-05 | Temp exactly maximum | temp=100.0 | Pass |
| TC-VAL-06 | Time zero | time=0 | Fail: TIME_TOO_SHORT |
| TC-VAL-07 | Time negative | time=-1 | Fail: TIME_TOO_SHORT |
| TC-VAL-08 | Time exactly maximum | time=5999 | Pass |
| TC-VAL-09 | Time above maximum | time=6000 | Fail: TIME_TOO_LONG |
| TC-VAL-10 | Chicken at 56°C | temp=56, food="chicken" | Fail: POULTRY_TEMP_UNSAFE |
| TC-VAL-11 | Chicken at 57°C | temp=57, food="chicken" | Pass |
| TC-VAL-12 | Ground beef at 59°C | temp=59, food="ground beef" | Fail: GROUND_MEAT_TEMP_UNSAFE |
| TC-VAL-13 | Ground beef at 60°C | temp=60, food="ground beef" | Pass |
| TC-VAL-14 | Float time truncation | temp=65, time=90.7 | Pass (time=90) |
| TC-VAL-15 | Missing temperature | time=90 | Fail: MISSING_TEMPERATURE |
| TC-VAL-16 | Missing time | temp=65 | Fail: MISSING_TIME |

---

## 8. External Dependencies

### 8.1 Python Package Requirements

```
# requirements.txt

# Web framework
flask==3.0.*

# HTTP client for Anova API
requests==2.31.*

# Configuration (development)
python-dotenv==1.0.*

# Encryption (production)
cryptography==41.*

# Production WSGI server
gunicorn==21.*

# Development/testing
pytest==7.*
pytest-flask==1.*
responses==0.24.*  # For mocking HTTP requests
```

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-08 | Claude | Initial draft |
| 2.0 | 2025-01-08 | Claude | Merged: layered architecture from previous + code templates |

---

## 10. Next Steps

With Component Architecture complete:

1. **05-API Specification** - Define exact endpoint contracts
2. **Implementation** - Create files following this structure
3. **Testing** - Implement test cases defined in section 7.1
