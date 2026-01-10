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
**Responsibility:** Bootstrap the Flask application and wire components together using the Application Factory pattern.

#### Interface Contract

**Function Signature:**
```python
def create_app(config: Config | None = None) -> Flask:
    """Create and configure Flask application."""
```

**Input Contract:**
- Parameter: config (Config | None) - Optional configuration object
- If None, configuration loaded from environment or file

**Behavioral Contract:**
- Creates Flask application instance
- Loads configuration from provided object or default sources
- Registers middleware (authentication, logging, error handling)
- Registers API routes (/health, /start-cook, /status, /stop-cook)
- Returns fully configured Flask application

**Preconditions:**
- If config is None, valid configuration must be available via environment variables or config files
- Python environment must have Flask installed

**Postconditions:**
- Returns Flask application ready to accept HTTP requests
- All routes are registered and accessible
- All middleware is active
- Configuration is loaded into app.config

**Error Contract:**
- ValueError: If required configuration is missing when config=None
- ImportError: If required dependencies not installed

**Dependencies:**
- config.Config (COMP-CFG-01) - Configuration management
- routes.register_routes (COMP-ROUTE-01) - Route registration
- middleware.register_middleware (COMP-MW-01) - Middleware registration

**Lifecycle:**
- **Startup:** Load config → Register middleware → Register routes → Return app
- **Shutdown:** Flask handles graceful shutdown of HTTP connections

#### Design Rationale
Application Factory pattern enables testing with different configurations without global state. Config injection allows unit tests to provide mock configurations.

#### Implementation Notes
See CLAUDE.md Section "Complete Component Implementations: app.py (COMP-APP-01)" for reference implementation.

#### 4.1.2 routes.py - HTTP Route Handlers

**Component ID:** COMP-ROUTE-01
**Responsibility:** Define API endpoints and orchestrate request handling with validation and error mapping.

**Dependencies:**
| Dependency | Type | Purpose |
|------------|------|---------|
| validators.py | Internal | Input validation |
| anova_client.py | Internal | Device commands |
| middleware.py | Internal | Authentication decorator |
| config.py | Internal | Settings |

#### Interface Contract

**Function Signature:**
```python
def register_routes(app: Flask) -> None:
    """Register all HTTP route handlers with the Flask application."""
```

**Input Contract:**
- Parameter: app (Flask) - Flask application instance
- app.config must contain valid Config object

**Behavioral Contract:**
- Registers 4 HTTP endpoints: /health, /start-cook, /status, /stop-cook
- Creates AnovaClient instance from app.config
- Wires validators and client to route handlers
- Maps domain exceptions to HTTP status codes

**Preconditions:**
- app is a valid Flask instance
- app.config contains valid configuration

**Postconditions:**
- All endpoints are registered and callable
- AnovaClient instance is created and used by handlers

**Route Specifications:**

| Route | Method | Auth | Satisfies | Input | Output | Status Codes |
|-------|--------|------|-----------|-------|--------|--------------|
| /health | GET | No | FR-06, QR-10 | None | {"status": "ok", "version": str, "timestamp": str} | 200 |
| /start-cook | POST | Yes | FR-01, FR-04, FR-05, FR-07, FR-08 | JSON: temperature_celsius, time_minutes, food_type? | See start_cook contract | 200, 400, 409, 503 |
| /status | GET | Yes | FR-02, FR-06 | None | See get_status contract | 200, 503 |
| /stop-cook | POST | Yes | FR-03, FR-06 | None | See stop_cook contract | 200, 409, 503 |

**Error Contract:**
- 400 Bad Request: ValidationError (invalid input)
- 401 Unauthorized: Missing or invalid API key
- 409 Conflict: DeviceBusyError (already cooking) or NoActiveCookError (nothing to stop)
- 503 Service Unavailable: DeviceOfflineError (device not reachable)
- 502 Bad Gateway: AnovaError (Anova API error)

**Test Oracle References:**
- TC-ROUTE-01: GET /health returns 200 without auth
- TC-ROUTE-02: POST /start-cook without auth returns 401
- TC-ROUTE-03: POST /start-cook with invalid temp returns 400
- TC-ROUTE-04: POST /start-cook when device busy returns 409
- TC-ROUTE-05: GET /status when device offline returns 503

#### Design Rationale
Routes act as thin orchestration layer - they coordinate validators and client but contain no business logic. This keeps handlers simple and testable. Exception-to-HTTP mapping is explicit for predictable API behavior.

#### Implementation Notes
See CLAUDE.md Section "Complete Component Implementations: routes.py (COMP-ROUTE-01)" for reference implementation.

#### 4.1.3 middleware.py - Cross-Cutting Concerns

**Component ID:** COMP-MW-01
**Responsibility:** Handle authentication, request/response logging, and global error handling.

#### Interface Contract

**Function Signature:**
```python
def register_middleware(app: Flask) -> None:
    """Register middleware hooks with Flask application."""

def require_api_key(f: Callable) -> Callable:
    """Decorator to enforce API key authentication on routes."""
```

**Input Contract (register_middleware):**
- Parameter: app (Flask) - Flask application instance
- app.config must contain optional API_KEY field

**Behavioral Contract (register_middleware):**
- Registers before_request hook: Records start time, logs request method and path
- Registers after_request hook: Calculates duration, logs response status code
- Registers global error handler: Logs exception, returns safe error response
- Does NOT log sensitive data (headers, bodies, tokens)

**Preconditions:**
- app is valid Flask instance
- logging is configured

**Postconditions:**
- All requests are logged (safely)
- All responses include timing information in logs
- Unhandled exceptions return 500 with generic message

**Input Contract (require_api_key):**
- Parameter: f (Callable) - Flask route handler function
- Expects HTTP request context with Authorization header

**Behavioral Contract (require_api_key):**
- Extracts API key from Authorization: Bearer <token> header
- Compares provided key with app.config.API_KEY using constant-time comparison
- If API_KEY not configured: allows request (dev mode)
- If header missing or invalid format: returns 401
- If key mismatch: returns 401
- If key matches: calls original route handler

**Security Properties:**
- Uses hmac.compare_digest to prevent timing attacks (SEC-REQ-06)
- Never logs API keys or auth headers
- Fails closed: missing header → deny access

**Error Contract:**
- 401 Unauthorized: Missing Authorization header
- 401 Unauthorized: Invalid Authorization header format (not "Bearer <token>")
- 401 Unauthorized: API key mismatch

**Test Oracle References:**
- TC-MW-01: Request without Authorization header returns 401
- TC-MW-02: Request with wrong API key returns 401
- TC-MW-03: Request with correct API key succeeds
- TC-MW-04: Request timing logged without sensitive data
- TC-MW-05: Unhandled exception returns 500 with safe message

**Design Rationale:**
Middleware separates cross-cutting concerns from business logic. API key authentication via decorator allows selective application to routes. Constant-time comparison prevents timing attacks. Safe logging avoids credential leaks.

**Implementation Notes:**
See CLAUDE.md Section "Complete Component Implementations: middleware.py (COMP-MW-01)" for reference implementation.

---

### 4.2 Service Layer

#### 4.2.1 validators.py - Input & Safety Validation

**Component ID:** COMP-VAL-01
**Responsibility:** Validate all inputs and enforce food safety rules. This is a SECURITY BOUNDARY.

**This component satisfies:** FR-04, FR-05, FR-07, FR-08, SEC-REQ-05

#### Interface Contract

**Function Signature:**
```python
def validate_cook_params(data: dict[str, Any] | None) -> CookParams:
    """Validate and normalize cooking parameters against food safety rules."""

@dataclass
class CookParams:
    """Validated cooking parameters."""
    temperature_celsius: float
    time_minutes: int
    food_type: str | None = None
```

**Input Contract:**
- Parameter: data (dict | None) - Raw request data from API
- Expected fields: temperature_celsius (numeric), time_minutes (numeric)
- Optional fields: food_type (string)
- Data may be malformed, missing fields, or wrong types

**Behavioral Contract:**
- Validates presence of required fields
- Coerces string numbers to float/int
- Enforces absolute safety limits (40-100°C, 1-5999 minutes)
- Applies food-specific safety rules based on food_type
- Normalizes temperature to 1 decimal place
- Truncates float time to integer
- Truncates food_type to 100 characters

**Validation Sequence (fail fast):**
1. Check data is not None
2. Check required fields present
3. Type validation with coercion
4. Range validation (absolute limits)
5. Food-specific safety validation

**Preconditions:**
- None (handles all edge cases including None, missing fields, wrong types)

**Postconditions:**
- Returns CookParams with guaranteed safe values
- OR raises ValidationError with specific error code

**Error Contract:**
| Error Code | Condition | HTTP Status |
|------------|-----------|-------------|
| MISSING_BODY | data is None | 400 |
| MISSING_TEMPERATURE | temperature_celsius field absent | 400 |
| MISSING_TIME | time_minutes field absent | 400 |
| INVALID_TEMPERATURE | temperature_celsius not convertible to float | 400 |
| INVALID_TIME | time_minutes not convertible to number | 400 |
| TEMPERATURE_TOO_LOW | temp < 40.0°C | 400 |
| TEMPERATURE_TOO_HIGH | temp > 100.0°C | 400 |
| POULTRY_TEMP_UNSAFE | food_type is poultry AND temp < 57.0°C | 400 |
| GROUND_MEAT_TEMP_UNSAFE | food_type is ground meat AND temp < 60.0°C | 400 |
| TIME_TOO_SHORT | time < 1 minute | 400 |
| TIME_TOO_LONG | time > 5999 minutes | 400 |

**Safety Constants:**
- MIN_TEMP_CELSIUS = 40.0 (Below: bacterial danger zone)
- MAX_TEMP_CELSIUS = 100.0 (Above: water boils)
- MIN_TIME_MINUTES = 1 (Practical minimum)
- MAX_TIME_MINUTES = 5999 (Device limit: 99h 59m)
- POULTRY_MIN_TEMP = 57.0 (With 3+ hour cook time)
- GROUND_MEAT_MIN_TEMP = 60.0 (Bacteria mixed throughout)

**Helper Functions:**
- `_is_poultry(food_type: str) -> bool`: Detects poultry keywords
- `_is_ground_meat(food_type: str) -> bool`: Detects ground meat keywords

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

**Test Oracle References:**
- TC-VAL-01 through TC-VAL-16: See Section 7.1 for comprehensive test case matrix

**Design Rationale:**
Food safety is NON-NEGOTIABLE and enforced at the API layer, not just in the GPT. Fail-fast principle: validate all inputs before any business logic executes. Validation is centralized here to ensure safety rules cannot be bypassed.

**Implementation Notes:**
See CLAUDE.md Section "Complete Component Implementations: validators.py (COMP-VAL-01)" for reference implementation.

---

### 4.3 Integration Layer

#### 4.3.1 anova_client.py - Anova Cloud Client

**Component ID:** COMP-ANOVA-01
**Responsibility:** Abstract all Anova Cloud API interactions including authentication, token management, and device commands.

#### Interface Contract

**Class Signature:**
```python
class AnovaClient:
    """Client for Anova Cloud API with automatic authentication and token refresh."""

    def __init__(self, config: Config) -> None:
        """Initialize client with configuration."""

    def get_status(self) -> dict:
        """Get current device status."""

    def start_cook(self, temperature_c: float, time_minutes: int) -> dict:
        """Start a cooking session."""

    def stop_cook(self) -> dict:
        """Stop current cooking session."""
```

**Input Contract (__init__):**
- Parameter: config (Config) - Configuration with ANOVA_EMAIL, ANOVA_PASSWORD, DEVICE_ID

**Behavioral Contract (__init__):**
- Stores configuration
- Initializes empty token state (_access_token, _refresh_token, _token_expiry)
- Creates persistent HTTP session for connection reuse
- Sets default headers (Content-Type, Accept)

**Input Contract (get_status):**
- No parameters

**Behavioral Contract (get_status):**
- Ensures valid authentication token (auto-refresh if needed)
- Requests device status from Anova API
- Maps Anova state values to standard states (idle, preheating, cooking, done)
- Returns normalized status dictionary

**Postconditions (get_status):**
- Returns dict with: device_online (bool), state (str), current_temp_celsius (float), target_temp_celsius (float|None), time_remaining_minutes (int|None), time_elapsed_minutes (int|None), is_running (bool)

**Input Contract (start_cook):**
- Parameter: temperature_c (float) - Target temperature in Celsius
- Parameter: time_minutes (int) - Cook time in minutes

**Behavioral Contract (start_cook):**
- Ensures valid authentication token
- Sends cook command to Anova API
- Generates cook_id if not provided by API
- Calculates estimated completion time
- Returns success response with metadata

**Postconditions (start_cook):**
- Returns dict with: success (bool), message (str), cook_id (str), device_state (str), target_temp_celsius (float), time_minutes (int), estimated_completion (str ISO8601)

**Input Contract (stop_cook):**
- No parameters

**Behavioral Contract (stop_cook):**
- Ensures valid authentication token
- Sends stop command to Anova API
- Returns success response

**Postconditions (stop_cook):**
- Returns dict with: success (bool), message (str), device_state (str)

**Error Contract:**
| Exception | Condition | HTTP Status |
|-----------|-----------|-------------|
| AuthenticationError | Firebase auth fails | 502 |
| DeviceOfflineError | Device not reachable (404 from API) | 503 |
| DeviceBusyError | Device already cooking (409 from API) | 409 |
| NoActiveCookError | No active cook to stop | 409 |
| AnovaError (TIMEOUT) | Request timeout | 503 |
| AnovaError (NETWORK_ERROR) | Network failure | 503 |
| AnovaError (ANOVA_API_ERROR) | Other API error (4xx/5xx) | 502 |

**Internal Methods (not called by routes):**
- `_ensure_authenticated() -> str`: Returns valid access token, refreshes if needed
- `_authenticate() -> None`: Full authentication with Firebase (email/password)
- `_refresh_access_token() -> None`: Refresh token using refresh_token
- `_api_request(method, endpoint, **kwargs) -> Any`: Authenticated HTTP request wrapper
- `_map_state(anova_state) -> str`: Map Anova states to standard states

**Authentication Flow:**
1. First API call triggers _authenticate() via _ensure_authenticated()
2. Firebase returns idToken (access) and refreshToken
3. Tokens cached with expiry timestamp
4. Subsequent calls reuse cached token if valid (5 min buffer)
5. If token expired, _refresh_access_token() called automatically
6. If refresh fails, full _authenticate() performed

**API Endpoints (to be confirmed):**
- FIREBASE_AUTH_URL: identitytoolkit.googleapis.com/v1/accounts:signInWithPassword
- FIREBASE_REFRESH_URL: securetoken.googleapis.com/v1/token
- ANOVA_API_BASE: api.anovaculinary.com (placeholder)

**Design Rationale:**
Encapsulates all Anova Cloud complexity. Automatic token management prevents routes from handling auth logic. HTTP session reuse improves performance. State mapping normalizes Anova's varying state names to consistent values for API consumers.

**Implementation Notes:**
See CLAUDE.md Section "Complete Component Implementations: anova_client.py (COMP-ANOVA-01)" for full 350-line reference implementation with authentication, retries, and error mapping.

---

### 4.4 Infrastructure Layer

#### 4.4.1 config.py - Configuration Management

**Component ID:** COMP-CFG-01
**Responsibility:** Load and provide configuration from environment, plain JSON (dev), or encrypted file (production).

#### Interface Contract

**Class Signature:**
```python
@dataclass
class Config:
    """Application configuration with credentials and safety constants."""

    ANOVA_EMAIL: str
    ANOVA_PASSWORD: str
    DEVICE_ID: str
    API_KEY: str | None = None
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    DEBUG: bool = False
    MIN_TEMP_CELSIUS: float = 40.0
    MAX_TEMP_CELSIUS: float = 100.0
    MAX_TIME_MINUTES: int = 5999

    @classmethod
    def load(cls) -> Self:
        """Load configuration from available source."""
```

**Input Contract (load):**
- No parameters
- Checks environment variables, then config files

**Behavioral Contract (load):**
- Priority order: Environment variables → Encrypted file → Plain JSON file
- Environment: Loads if ANOVA_EMAIL env var exists
- Encrypted file: Loads from config/credentials.enc if exists
- Plain JSON: Loads from config/credentials.json if exists (warns about security)
- Validates required fields present

**Preconditions:**
- At least one configuration source must be available

**Postconditions:**
- Returns Config instance with all required fields populated
- Safety constants are always set to hardcoded values (non-configurable)

**Error Contract:**
- ValueError: No configuration source found
- ValueError: Required fields missing from chosen source
- NotImplementedError: Encrypted file exists but decryption not yet implemented

**Configuration Sources:**

| Source | Priority | Use Case | Security |
|--------|----------|----------|----------|
| Environment variables | 1st | Development, testing | Moderate (process memory) |
| Encrypted file | 2nd | Production deployment | High (AES-256-GCM) |
| Plain JSON file | 3rd | Local development only | Low (gitignored) |

**Required Fields:**
- ANOVA_EMAIL: Email for Anova account
- ANOVA_PASSWORD: Password for Anova account
- DEVICE_ID: Target device identifier

**Optional Fields:**
- API_KEY: Bearer token for ChatGPT auth (None = no auth)
- DEBUG: Enable debug mode (default: False)

**Safety Constants (non-configurable):**
- MIN_TEMP_CELSIUS = 40.0
- MAX_TEMP_CELSIUS = 100.0
- MAX_TIME_MINUTES = 5999

**Design Rationale:**
Multiple configuration sources support different environments: env vars for development, encrypted files for production. Safety constants are hardcoded to prevent misconfiguration from bypassing food safety rules. Priority order allows environment override for testing.

**Implementation Notes:**
See CLAUDE.md Section "Complete Component Implementations: config.py (COMP-CFG-01)" for reference implementation. Note: Encrypted file loading is placeholder pending cryptography implementation.

---

#### 4.4.2 exceptions.py - Custom Exceptions

**Component ID:** COMP-EXC-01
**Responsibility:** Define domain-specific exception hierarchy with error codes and HTTP status mappings.

#### Interface Contract

**Exception Hierarchy:**
```python
class AnovaAssistantError(Exception):
    """Base exception for all application errors."""

class ConfigurationError(AnovaAssistantError):
    """Configuration is missing or invalid."""

class ValidationError(AnovaAssistantError):
    """Input validation failed."""
    def __init__(self, code: str, message: str)

class AnovaError(AnovaAssistantError):
    """Error communicating with Anova Cloud."""
    def __init__(self, code: str, message: str, status_code: int = 500)

class DeviceOfflineError(AnovaError):
    """Device is not connected."""

class DeviceBusyError(AnovaError):
    """Device already has an active cook."""

class AuthenticationError(AnovaError):
    """Authentication with Anova failed."""
```

**Exception Properties:**
- ValidationError.code: Error code string (e.g., "TEMPERATURE_TOO_LOW")
- ValidationError.message: Human-readable explanation
- AnovaError.code: Error code string (e.g., "DEVICE_OFFLINE")
- AnovaError.message: Human-readable explanation
- AnovaError.status_code: Recommended HTTP status code (default: 500)

**Exception-to-HTTP Mapping:**
| Exception | Default HTTP Status | Example Error Code |
|-----------|--------------------|--------------------|
| ValidationError | 400 Bad Request | TEMPERATURE_TOO_LOW |
| DeviceOfflineError | 503 Service Unavailable | DEVICE_OFFLINE |
| DeviceBusyError | 409 Conflict | DEVICE_BUSY |
| AuthenticationError | 502 Bad Gateway | AUTH_FAILED |
| AnovaError | 500 Internal Server Error | ANOVA_API_ERROR |

**Design Rationale:**
Custom exceptions enable explicit error handling and consistent API responses. Error codes provide machine-readable identifiers for client logic. HTTP status code mapping ensures correct REST semantics. Hierarchy allows catch-all handling at different levels (e.g., catch all AnovaError subclasses).

**Implementation Notes:**
See CLAUDE.md Section "Complete Component Implementations: exceptions.py (COMP-EXC-01)" for reference implementation.

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
