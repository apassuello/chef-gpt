# Anova AI Sous Vide Assistant - System Architecture Overview

## Purpose & Goals

An **AI-powered sous vide cooking assistant** that bridges ChatGPT (via Custom GPT) with an Anova Precision Cooker 3.0, enabling natural language control of precision cooking with built-in food safety guardrails.

**Primary Goal**: Enable users to control their sous vide cooker through conversational AI while maintaining non-bypassable food safety validation.

**Key Constraint**: Food safety validation must happen server-side, not just in the AI layer.

**Design Principle**: Zero recurring costs - fully self-hosted solution.

---

## Architecture Pattern

**Type**: API Gateway / Bridge Pattern with WebSocket Client

```
┌─────────────────┐    HTTPS     ┌──────────────────┐   WebSocket   ┌─────────────┐
│  ChatGPT        │ ◄─────────► │  Flask API       │ ◄──────────► │  Anova      │
│  Custom GPT     │  (OpenAPI)  │  (Raspberry Pi)  │   (wss://)    │  Cooker 3.0 │
└─────────────────┘              └──────────────────┘               └─────────────┘
                                        ▲
                                        │
                                   Food Safety
                                   Validation Layer
```

**Key Innovation**: Threading bridge that connects synchronous Flask HTTP with async WebSocket API, enabling real-time device communication.

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Web Framework** | Flask | 3.0.* | Lightweight HTTP API server |
| **Production Server** | gunicorn | 21.* | WSGI server with process management |
| **WebSocket Client** | websockets | 13.0+ | Real-time device communication |
| **HTTP Client** | requests | 2.31.* | HTTP operations (if needed) |
| **Security** | cryptography | 42.* | Fernet symmetric encryption for credentials |
| **Config Management** | python-dotenv | 1.0.* | Environment variable handling |
| **Runtime** | Python | 3.11+ | Modern type hints, AsyncIO support |

### Deployment Stack
- **Hardware**: Raspberry Pi Zero 2 W
- **OS**: Raspberry Pi OS (Linux)
- **Tunnel**: Cloudflare Tunnel (HTTPS ingress)
- **Service Manager**: systemd (auto-restart, logging)

---

## Component Architecture

### Layer 1: API Layer
**Module**: `routes.py`

**4 HTTP Endpoints**:
- `GET /health` - Health check (no authentication)
- `POST /start-cook` - Start cooking session (requires Bearer token)
- `GET /status` - Get current device status (requires Bearer token)
- `POST /stop-cook` - Stop cooking (requires Bearer token)

**Responsibilities**:
- HTTP request/response handling
- Endpoint routing
- Orchestration between validators and client

### Layer 2: Service Layer
**Module**: `validators.py`

**Food Safety Validation Engine**:
- Absolute temperature limits: 40-100°C
- Food-specific rules:
  - Poultry: ≥57°C (extended time) or ≥65°C (standard)
  - Ground meat: ≥60°C
  - Pork: ≥57°C
  - Beef/Lamb: ≥52°C
- Time validation: 1-5999 minutes
- Type coercion and input sanitization

**Responsibilities**:
- Non-bypassable safety guardrails
- Input validation with actionable error messages
- Food safety rule enforcement

### Layer 3: Integration Layer
**Module**: `anova_client.py`

**WebSocket Client with Threading Bridge**:
- Personal Access Token authentication
- Automatic device discovery (no manual DEVICE_ID configuration)
- Real-time status caching
- Command execution (START, STOP)
- Graceful shutdown handling
- Per-request response queues using `requestId` matching

**Responsibilities**:
- Translate HTTP requests to WebSocket commands
- Manage persistent WebSocket connection
- Handle async/sync bridge via threading

### Layer 4: Infrastructure

**Middleware** (`middleware.py`):
- Bearer token authentication with constant-time comparison
- Error handling and HTTP status code mapping
- Request/response logging (without sensitive data)

**Configuration** (`config.py`):
- Multi-source configuration (priority order):
  1. Environment variables
  2. Encrypted JSON file (production)
  3. Plain JSON file (development)
- Fernet encryption for production credentials

**Exceptions** (`exceptions.py`):
- 7 custom exception classes
- Mapped to HTTP status codes (400, 401, 409, 500, 503)
- Structured error responses

**Application Factory** (`app.py`):
- Flask application initialization
- WebSocket lifecycle management
- Error handler registration
- Middleware setup

---

## Threading Bridge Architecture

**Challenge**: Flask is synchronous, WebSocket API is async

**Solution**: Background thread runs async event loop

```
Flask Request Thread          Background Thread
      │                            │
      ├──► Put command in queue ──►│
      │                            │◄── WebSocket Event Loop
      │                            │    (async/await)
      │◄── Get response from queue─┤
      │                            │
   Return JSON                Real-time Updates
```

**Key Features**:
- Per-request queues identified by `requestId`
- Thread-safe device dictionary for status caching
- Single persistent WebSocket connection per app instance
- atexit handler for graceful shutdown

---

## API Interface

### POST /start-cook
Start a cooking session with temperature and time validation.

**Request**:
```json
{
  "temperature_celsius": 65.0,
  "time_minutes": 90,
  "food_type": "chicken"
}
```

**Success Response (200)**:
```json
{
  "status": "started",
  "target_temp_celsius": 65.0,
  "time_minutes": 90,
  "device_id": "abc123"
}
```

**Error Responses**:
- `400` - Validation error (TEMPERATURE_TOO_LOW, POULTRY_TEMP_UNSAFE, etc.)
- `401` - Missing or invalid API key
- `409` - Device already cooking (DEVICE_BUSY)
- `503` - Device offline (DEVICE_OFFLINE)

---

### GET /status
Get current cooking status and device state.

**Success Response (200)**:
```json
{
  "device_online": true,
  "state": "cooking",
  "current_temp_celsius": 64.8,
  "target_temp_celsius": 65.0,
  "time_remaining_minutes": 47,
  "time_elapsed_minutes": 43,
  "is_running": true
}
```

**States**: `idle`, `preheating`, `cooking`, `done`

---

### POST /stop-cook
Stop the current cooking session.

**Success Response (200)**:
```json
{
  "status": "stopped",
  "final_temp_celsius": 64.9,
  "total_time_minutes": 85
}
```

**Error Responses**:
- `401` - Missing or invalid API key
- `404` - No active cook (NO_ACTIVE_COOK)
- `503` - Device offline

---

### GET /health
Health check endpoint for monitoring.

**Success Response (200)**:
```json
{
  "status": "ok"
}
```

**Note**: No authentication required

---

## WebSocket API Integration

### Authentication
```
Token Format: "anova-{token}"
Connection: wss://devices.anovaculinary.io?token={token}
Source: Personal Access Token from Anova mobile app
```

### WebSocket Commands
- `CMD_APC_START` - Start cooking (targetTemperature, timer, unit)
- `CMD_APC_STOP` - Stop cooking
- `EVENT_APC_WIFI_LIST` - Device discovery (automatic)

### Message Format
```json
{
  "command": "CMD_APC_START",
  "payload": {
    "targetTemperature": 65.0,
    "timer": 5400,
    "temperatureUnit": "c"
  },
  "requestId": "req-1234567890"
}
```

---

## Food Safety Rules

### Absolute Temperature Limits
```python
MIN_TEMP = 40.0°C   # Below = bacterial danger zone (4-60°C)
MAX_TEMP = 100.0°C  # Above = water boils
```

### Food-Specific Minimum Safe Temperatures

| Food Type | Min Temp | Rationale |
|-----------|----------|-----------|
| **Poultry** | 57.0°C | Pasteurization with 3+ hours |
| **Poultry (standard)** | 65.0°C | Safe cooking 1-2 hours |
| **Ground Meat** | 60.0°C | Bacteria mixed throughout during grinding |
| **Pork** | 57.0°C | Modern pork is safe |
| **Beef/Lamb** | 52.0°C | Bacteria only on surface |

### Time Limits
```python
MIN_TIME = 1 minute
MAX_TIME = 5999 minutes  # Device limit (99h 59m)
```

### Validation Error Codes
- `TEMPERATURE_TOO_LOW` - Below 40°C (danger zone)
- `TEMPERATURE_TOO_HIGH` - Above 100°C (boiling)
- `POULTRY_TEMP_UNSAFE` - Poultry below minimum safe temperature
- `GROUND_MEAT_TEMP_UNSAFE` - Ground meat below minimum
- `TIME_TOO_SHORT` - Less than 1 minute
- `TIME_TOO_LONG` - More than 5999 minutes

---

## System Capabilities

### Core Capabilities
1. **Natural Language Control** - ChatGPT parses user intent and calls API
2. **Real-Time Monitoring** - WebSocket provides live temperature and timer updates
3. **Automatic Device Discovery** - No manual device ID configuration required
4. **Food Safety Validation** - Server-side enforcement of temperature/time rules
5. **Graceful Error Handling** - Actionable error messages for users
6. **Secure Authentication** - Bearer token with constant-time comparison
7. **Connection Persistence** - Single WebSocket connection for app lifetime
8. **Zero Recurring Costs** - Self-hosted on Raspberry Pi

### Supported Operations
- **Start Cook**: Temperature (40-100°C) + Time (1-5999 min) + Optional food type
- **Get Status**: Real-time temp, target temp, timer, state, device online status
- **Stop Cook**: Immediate stop with final stats
- **Health Check**: Monitoring endpoint for uptime checks

---

## Deployment Architecture

### Physical Deployment
```
Internet
   │
   ▼
Cloudflare Tunnel (HTTPS)
   │
   ▼
gunicorn (2 workers, localhost:5000)
   │
   ▼
Flask Application
   │
   ▼
WebSocket Client ──► Anova Cloud API ──► Physical Anova Device
```

### Service Configuration
- **Installation Path**: `/opt/anova-assistant/`
- **systemd Service**: `anova-server.service`
- **Workers**: 2 gunicorn workers
- **Bind Address**: `127.0.0.1:5000` (local only, exposed via tunnel)
- **Logs**: `/var/log/anova-server/`
- **Auto-restart**: Enabled via systemd

### Security Hardening
- `NoNewPrivileges=true` - Prevent privilege escalation
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=read-only` - Limited home access
- `PrivateTmp=true` - Isolated /tmp directory
- Restrictive file permissions (0o600 for credentials)

---

## Configuration Management

### Environment Variables
```bash
PERSONAL_ACCESS_TOKEN=anova-{token}  # Required: From Anova mobile app
API_KEY=sk-anova-{key}              # Required: Generated for ChatGPT
ANOVA_WEBSOCKET_URL=wss://...       # Optional: Defaults to production
DEBUG=true                           # Optional: Enable debug logging
```

### Configuration Priority (Highest to Lowest)
1. **Environment Variables** - Development and testing
2. **Encrypted JSON File** - Production (`config/credentials.enc`)
3. **Plain JSON File** - Development fallback (`config/credentials.json`)

### Encryption
- **Algorithm**: Fernet symmetric encryption (cryptography library)
- **Key Storage**: Environment variable (`ENCRYPTION_KEY`)
- **File Permissions**: 0o600 (owner read/write only)

---

## Usage Flow Example

**User**: *"Hey ChatGPT, cook chicken breast at 65 degrees for 90 minutes"*

### Request Flow
1. **ChatGPT** parses natural language intent
2. **ChatGPT** calls `POST /start-cook` with structured JSON:
   ```json
   {
     "temperature_celsius": 65.0,
     "time_minutes": 90,
     "food_type": "chicken"
   }
   ```
3. **Middleware** validates Bearer token
4. **Validator** checks food safety:
   - 65°C ≥ 57°C (poultry minimum) ✅
   - 90 minutes valid ✅
5. **WebSocket Client** sends `CMD_APC_START` to device
6. **Device** confirms start
7. **API** responds with success:
   ```json
   {
     "status": "started",
     "target_temp_celsius": 65.0,
     "time_minutes": 90,
     "device_id": "APC-123456"
   }
   ```
8. **ChatGPT** confirms to user: *"Started cooking chicken at 65°C for 90 minutes"*

### Safety Rejection Example

**User**: *"Cook chicken at 50 degrees"*

1. **Validator** detects unsafe temperature (50°C < 57°C for poultry)
2. **API** returns `400 Bad Request`:
   ```json
   {
     "error": "POULTRY_TEMP_UNSAFE",
     "message": "Temperature 50°C is not safe for poultry. Minimum is 57°C with extended time (3+ hours) or 65°C for standard cooking."
   }
   ```
3. **ChatGPT** explains to user why the request was rejected and suggests safe alternatives

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Flask over FastAPI** | Simpler for small API, synchronous model fits use case, mature ecosystem |
| **WebSocket over REST** | Official Anova API requirement (not REST-based) |
| **Threading Bridge** | Bridges synchronous Flask with async WebSocket without rewriting entire app |
| **Server-Side Validation** | Food safety is paramount—AI cannot be solely trusted for safety-critical decisions |
| **Raspberry Pi** | Zero recurring costs, low power consumption, sufficient for single-user API |
| **Cloudflare Tunnel** | Free HTTPS ingress without port forwarding or firewall changes |
| **Personal Access Token** | More secure than email/password, long-lived, obtained from Anova mobile app |
| **Automatic Discovery** | Eliminates manual device ID configuration, improves user experience |

---

## Current Status

**Completion**: 95% (Production deployment pending)

**Implemented**:
- ✅ Complete Flask API with 4 endpoints
- ✅ WebSocket integration with threading bridge
- ✅ Food safety validation engine
- ✅ Bearer token authentication
- ✅ Automatic device discovery
- ✅ Real-time status monitoring
- ✅ Graceful shutdown handling
- ✅ Error handling with actionable messages
- ✅ Configuration management (multi-source)
- ✅ systemd service configuration

**Pending**:
- 🔲 Physical deployment to Raspberry Pi
- 🔲 ChatGPT Custom GPT configuration with OpenAPI Actions

---

## Summary

A **production-ready, safety-first sous vide control system** that successfully bridges conversational AI with physical cooking hardware. The architecture balances ease of use (natural language interface) with safety (non-bypassable server-side validation) and reliability (official WebSocket API, persistent connections, graceful error handling).

**Core Achievement**: Demonstrates how to build a **safe AI-to-hardware bridge** where critical safety logic cannot be bypassed, even by a powerful language model.

**Status**: Ready for production deployment and ChatGPT Custom GPT integration.
