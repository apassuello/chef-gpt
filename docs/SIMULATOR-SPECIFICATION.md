# Anova Precision Cooker 3.0 Simulator Specification

> **Document Type:** Technical Specification
> **Status:** Implemented
> **Version:** 1.1
> **Last Updated:** 2026-01-20
> **Purpose:** Integration and validation testing without physical device

---

## 1. Overview

### 1.1 Purpose

This document specifies a software simulator for the Anova Precision Cooker 3.0 (APC) that faithfully replicates the device's cloud API behavior. The simulator enables:

- **Integration testing** without a physical device
- **Deterministic test scenarios** (device offline, errors, state transitions)
- **Accelerated time simulation** for long cook cycles
- **CI/CD pipeline integration** for automated testing

### 1.2 Scope

The simulator implements:
- WebSocket server matching `wss://devices.anovaculinary.io` protocol
- Firebase authentication mock
- All APC commands (START, STOP, SET_TARGET_TEMP, SET_TIMER)
- EVENT_APC_STATE message broadcasting
- Physical simulation (temperature heating, timer countdown)
- Test control API for scenario setup

### 1.3 Design Principles

| Principle | Description |
|-----------|-------------|
| **Protocol Fidelity** | Exact match to real Anova WebSocket API |
| **Deterministic** | Same inputs produce same outputs |
| **Time Control** | Configurable time acceleration for testing |
| **Isolated** | No external dependencies; runs entirely locally |
| **Observable** | Full state inspection for test assertions |

### 1.4 References

- [bogd/anova-oven-api](https://github.com/bogd/anova-oven-api) - Community API documentation
- [Anova Developer Portal](https://developer.anovaculinary.com/) - Official documentation
- Firebase Authentication API documentation

---

## 2. Architecture

### 2.1 Component Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         SIMULATOR                                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────────────┐    ┌──────────────────────────────────────┐ │
│  │  Firebase Auth   │    │         WebSocket Server             │ │
│  │  Mock            │    │         (wss://localhost:8765)       │ │
│  │                  │    │                                      │ │
│  │  POST /token     │    │  ← CMD_APC_START                     │ │
│  │  (validates &    │    │  ← CMD_APC_STOP                      │ │
│  │   issues tokens) │    │  ← CMD_APC_SET_TARGET_TEMP           │ │
│  │                  │    │  ← CMD_APC_SET_TIMER                 │ │
│  │                  │    │  → EVENT_APC_STATE (push)            │ │
│  │                  │    │  → RESPONSE (command ack)            │ │
│  └──────────────────┘    └─────────────┬────────────────────────┘ │
│                                        │                          │
│                                        ▼                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    DEVICE STATE MACHINE                    │   │
│  │                                                            │   │
│  │   ┌──────┐  start   ┌────────────┐  temp   ┌─────────┐    │   │
│  │   │ IDLE │─────────►│ PREHEATING │────────►│ COOKING │    │   │
│  │   └──────┘          └────────────┘ reached └─────────┘    │   │
│  │       ▲                   │                     │         │   │
│  │       │                   │ stop                │ timer=0 │   │
│  │       │     stop          ▼                     ▼         │   │
│  │       └───────────────────┴─────────────────►┌──────┐     │   │
│  │                                              │ DONE │     │   │
│  │                                              └──────┘     │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                        │                          │
│                                        ▼                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    PHYSICS ENGINE                          │   │
│  │                                                            │   │
│  │  • Temperature Model: dT/dt = k(T_target - T_current)      │   │
│  │  • Timer Model: countdown in real/accelerated time         │   │
│  │  • Configurable time_scale (1.0 = realtime, 60.0 = 1min/s) │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                 TEST CONTROL API (HTTP)                    │   │
│  │                 (http://localhost:8766)                    │   │
│  │                                                            │   │
│  │  POST /reset          - Reset to initial state             │   │
│  │  POST /set-state      - Force specific state               │   │
│  │  POST /set-offline    - Simulate device offline            │   │
│  │  POST /set-time-scale - Adjust time acceleration           │   │
│  │  GET  /state          - Inspect current state              │   │
│  │  GET  /messages       - View message history               │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 Port Assignments

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Firebase Auth Mock | 8764 | HTTPS | Token generation/validation |
| WebSocket Server | 8765 | WSS | Device communication |
| Test Control API | 8766 | HTTP | Test setup and inspection |

### 2.3 File Structure

```
simulator/
├── __init__.py
├── server.py                 # Main entry point, orchestrates all servers
├── websocket_server.py       # WebSocket protocol implementation
├── firebase_mock.py          # Firebase auth endpoint mock
├── device.py                 # Device state machine
├── physics.py                # Temperature and timer simulation
├── messages.py               # Message type definitions and serialization
├── control_api.py            # Test control HTTP endpoints
├── config.py                 # Simulator configuration
└── types.py                  # Type definitions (enums, dataclasses)
```

---

## 3. WebSocket Protocol Specification

### 3.1 Connection

**Endpoint:** `wss://localhost:8765` (simulator) or `wss://devices.anovaculinary.io` (production)

**Query Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `token` | Yes | Firebase ID token (JWT) |
| `supportedAccessories` | Yes | Device types: `"APC"` for cooker |
| `platform` | No | `"ios"` or `"android"` (default: `"ios"`) |

**Example Connection URL:**
```
wss://localhost:8765?token=eyJhbGc...&supportedAccessories=APC&platform=ios
```

**Connection Lifecycle:**
1. Client connects with valid token
2. Server validates token
3. Server sends initial `EVENT_APC_STATE`
4. Server continues sending `EVENT_APC_STATE` every 2s (cooking) or 30s (idle)
5. Client sends commands, server responds

### 3.2 Message Envelope Format

All messages use this JSON envelope:

```json
{
  "command": "<MESSAGE_TYPE>",
  "requestId": "<22-digit-hex>",  // For commands only
  "payload": { ... }
}
```

### 3.3 Commands (Client → Server)

#### 3.3.1 CMD_APC_START

Starts a cooking session with specified temperature and timer.

**Request:**
```json
{
  "command": "CMD_APC_START",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "targetTemperature": 65.0,
    "unit": "C",
    "timer": 5400,
    "requestId": "a1b2c3d4e5f6g7h8i9j0kl"
  }
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cookerId` | string | Yes | Device identifier |
| `type` | string | Yes | Device type: `"pro"`, `"nano"`, `"wifi"` |
| `targetTemperature` | float | Yes | Target temperature (40.0-100.0°C) |
| `unit` | string | Yes | `"C"` or `"F"` |
| `timer` | int | Yes | Cook time in seconds (60-359940) |
| `requestId` | string | Yes | Must match outer requestId |

**Success Response:**
```json
{
  "command": "RESPONSE",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "status": "ok"
  }
}
```

**Error Response:**
```json
{
  "command": "RESPONSE",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "status": "error",
    "code": "DEVICE_BUSY",
    "message": "Device is already cooking"
  }
}
```

**State Transition:** `IDLE` → `PREHEATING`

---

#### 3.3.2 CMD_APC_STOP

Stops the current cooking session.

**Request:**
```json
{
  "command": "CMD_APC_STOP",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "requestId": "a1b2c3d4e5f6g7h8i9j0kl"
  }
}
```

**Success Response:**
```json
{
  "command": "RESPONSE",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "status": "ok"
  }
}
```

**Error Codes:**
- `NO_ACTIVE_COOK` - Device is not cooking

**State Transition:** Any → `IDLE`

---

#### 3.3.3 CMD_APC_SET_TARGET_TEMP

Changes target temperature (works while idle or cooking).

**Request:**
```json
{
  "command": "CMD_APC_SET_TARGET_TEMP",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "targetTemperature": 70.0,
    "unit": "C",
    "requestId": "a1b2c3d4e5f6g7h8i9j0kl"
  }
}
```

**Validation:**
- Temperature must be 40.0-100.0°C
- If unit is `"F"`, temperature must be 104.0-212.0°F

---

#### 3.3.4 CMD_APC_SET_TIMER

Sets or modifies the cook timer.

**Request:**
```json
{
  "command": "CMD_APC_SET_TIMER",
  "requestId": "a1b2c3d4e5f6g7h8i9j0kl",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "timer": 7200,
    "requestId": "a1b2c3d4e5f6g7h8i9j0kl"
  }
}
```

**Parameters:**
- `timer`: Cook time in seconds (60-359940, i.e., 1 min to 99h 59m)

---

### 3.4 Events (Server → Client)

#### 3.4.1 EVENT_APC_STATE

Periodic state update pushed by server.

**Frequency:**
- Every 30 seconds when idle
- Every 2 seconds when cooking/preheating

**Full Message Structure:**
```json
{
  "command": "EVENT_APC_STATE",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "state": {
      "audio": {
        "file-name": "",
        "volume": 50
      },
      "cap-touch": {
        "minus-button": 0,
        "play-button": 0,
        "plus-button": 0,
        "target-temperature-button": 0,
        "timer-button": 0,
        "water-temperature-button": 0
      },
      "firmware-info": {
        "firmware-version": "3.3.01",
        "firmware-update-available": false
      },
      "heater-control": {
        "duty-cycle": 0.0
      },
      "job": {
        "cook-time-seconds": 5400,
        "id": "a1b2c3d4e5f6g7h8i9j0kl",
        "mode": "IDLE",  // Matches job-status.state: IDLE, PREHEATING, COOKING, or DONE
        "target-temperature": 65.0,
        "temperature-unit": "C"
      },
      "job-status": {
        "cook-time-remaining": 5400,
        "state": "IDLE",  // IDLE, PREHEATING, COOKING, DONE
        "job-start-systick": 0,
        "state-change-systick": 0
      },
      "motor-control": {
        "duty-cycle": 0.0
      },
      "motor-info": {
        "rpm": 0
      },
      "network-info": {
        "connection-status": "connected-station",
        "mac-address": "AA:BB:CC:DD:EE:FF",
        "ssid": "HomeNetwork",
        "security-type": "WPA2"
      },
      "pin-info": {
        "device-safe": 1,
        "water-leak": 0,
        "water-level-critical": 0,
        "water-level-low": 0,
        "motor-stuck": 0
      },
      "system-info": {
        "firmware-version": "3.3.01",
        "mcu-temperature": 35,
        "heap-size": 102400
      },
      "temperature-info": {
        "heater-temperature": 22.5,
        "triac-temperature": 25,
        "water-temperature": 22.5
      }
    }
  }
}
```

**Key Fields for Testing:**

| Field Path | Type | Description |
|------------|------|-------------|
| `state.job-status.state` | string | `IDLE`, `PREHEATING`, `COOKING`, `DONE` |
| `state.job.target-temperature` | float | Target temperature in configured unit |
| `state.job.cook-time-seconds` | int | Total cook time set |
| `state.job-status.cook-time-remaining` | int | Seconds remaining |
| `state.temperature-info.water-temperature` | float | Current water temperature |
| `state.heater-control.duty-cycle` | float | 0.0-100.0, heater power |
| `state.motor-control.duty-cycle` | float | 0.0-100.0, circulation pump |
| `state.pin-info.device-safe` | int | 1=safe, 0=error |
| `state.pin-info.water-level-low` | int | 1=warning |
| `state.pin-info.water-level-critical` | int | 1=critical, stops cooking |

---

## 4. Device State Machine

### 4.1 States

| State | Description | Heater | Motor | Timer |
|-------|-------------|--------|-------|-------|
| `IDLE` | Not cooking, ambient temperature | Off | Off | Stopped |
| `PREHEATING` | Heating water to target | 100% | 100% | Paused |
| `COOKING` | At temperature, timer running | Variable | 100% | Counting down |
| `DONE` | Timer expired, maintaining temp | Variable | 100% | Stopped at 0 |

### 4.2 State Transitions

```
┌─────────────────────────────────────────────────────────────────┐
│                     STATE TRANSITION DIAGRAM                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        CMD_APC_START                            │
│         ┌────────────────────────────────────────┐              │
│         │                                        │              │
│         │                                        ▼              │
│      ┌──────┐                             ┌────────────┐        │
│      │      │                             │            │        │
│      │ IDLE │                             │ PREHEATING │        │
│      │      │                             │            │        │
│      └──────┘                             └────────────┘        │
│         ▲                                        │              │
│         │                                        │              │
│         │ CMD_APC_STOP                           │              │
│         │ (from any state)       water_temp >= target_temp      │
│         │                                        │              │
│         │                                        ▼              │
│         │                                 ┌───────────┐         │
│         │                                 │           │         │
│         ├─────────────────────────────────│  COOKING  │         │
│         │                                 │           │         │
│         │                                 └───────────┘         │
│         │                                        │              │
│         │                                        │              │
│         │                           timer_remaining == 0        │
│         │                                        │              │
│         │                                        ▼              │
│         │                                  ┌──────────┐         │
│         │                                  │          │         │
│         └──────────────────────────────────│   DONE   │         │
│                                            │          │         │
│                                            └──────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Transition Triggers

| From | To | Trigger | Action |
|------|----|---------|--------|
| IDLE | PREHEATING | CMD_APC_START received | Set target temp, timer; start heating |
| PREHEATING | COOKING | `water_temp >= target_temp - 0.5` | Start timer countdown |
| COOKING | DONE | `timer_remaining == 0` | Stop timer, continue heating |
| Any | IDLE | CMD_APC_STOP received | Stop heating, reset timer |
| DONE | IDLE | Timeout (configurable) or CMD_APC_STOP | Full reset |

### 4.4 State Invariants

| State | Invariant |
|-------|-----------|
| IDLE | `target_temp == null`, `timer_remaining == null` |
| PREHEATING | `water_temp < target_temp`, `timer_remaining == cook_time_seconds` |
| COOKING | `water_temp >= target_temp - 0.5`, `timer_remaining > 0` |
| DONE | `timer_remaining == 0`, `water_temp >= target_temp - 0.5` |

---

## 5. Physics Simulation

### 5.1 Temperature Model

The simulator models water temperature using a first-order differential equation:

```
dT/dt = k * (T_target - T_current) * heater_duty_cycle
```

Where:
- `T_current`: Current water temperature (°C)
- `T_target`: Target temperature (°C)
- `k`: Heating constant (default: 0.05 per second)
- `heater_duty_cycle`: 0.0-1.0 (100% during preheating)

**Simplified Implementation:**
```python
def update_temperature(self, dt_seconds: float):
    if self.state == "PREHEATING":
        # Heat at max rate toward target
        delta = self.heating_rate * dt_seconds
        self.water_temp = min(self.water_temp + delta, self.target_temp)
    elif self.state in ("COOKING", "DONE"):
        # Maintain temperature with minor oscillation
        self.water_temp = self.target_temp + random.uniform(-0.2, 0.2)
    elif self.state == "IDLE":
        # Cool toward ambient
        delta = self.cooling_rate * dt_seconds
        self.water_temp = max(self.water_temp - delta, self.ambient_temp)
```

### 5.2 Configurable Parameters

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `ambient_temp` | 22.0 | °C | Starting/ambient temperature |
| `heating_rate` | 1.0 | °C/min | Temperature increase rate |
| `cooling_rate` | 0.5 | °C/min | Temperature decrease rate (when idle) |
| `temp_tolerance` | 0.5 | °C | Threshold for "at temperature" |
| `temp_oscillation` | 0.2 | °C | Random variation when maintaining |

### 5.3 Timer Model

```python
def update_timer(self, dt_seconds: float):
    if self.state == "COOKING":
        self.timer_remaining = max(0, self.timer_remaining - dt_seconds)
        self.timer_elapsed += dt_seconds

        if self.timer_remaining == 0:
            self.transition_to("DONE")
```

### 5.4 Time Acceleration

The simulator supports time acceleration via `time_scale`:

| time_scale | Effect | Use Case |
|------------|--------|----------|
| 1.0 | Real-time (1s = 1s) | Manual testing, demos |
| 60.0 | 1 minute = 1 second | Integration tests |
| 3600.0 | 1 hour = 1 second | Long cook scenario tests |
| ∞ (instant) | Immediate transitions | Unit tests |

---

## 6. Firebase Authentication Mock

### 6.1 Endpoint

**URL:** `https://localhost:8764/v1/token`

Mocks `https://securetoken.googleapis.com/v1/token`

### 6.2 Token Exchange

**Request (JSON format - matches anova_client.py):**
```
POST /v1/token?key=<FIREBASE_API_KEY>
Content-Type: application/json

{
  "grant_type": "refresh_token",
  "refresh_token": "<REFRESH_TOKEN>"
}
```

**Note:** Firebase accepts both JSON and form-encoded formats. The existing `anova_client.py` uses JSON (see line 184).

**Success Response (200):**
```json
{
  "access_token": "mock-access-token-xyz",
  "expires_in": "3600",
  "token_type": "Bearer",
  "refresh_token": "mock-refresh-token-abc",
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "mock-user-123",
  "project_id": "anova-production"
}
```

### 6.3 Token Validation

The WebSocket server validates tokens by:
1. Checking token format (starts with expected prefix)
2. Checking expiry (if enforcing expiry)
3. Matching against known test tokens

**Test Tokens:**

| Token | Purpose | Valid |
|-------|---------|-------|
| `valid-test-token` | Happy path testing | Yes |
| `expired-test-token` | Token expiry testing | No (401) |
| `invalid-test-token` | Auth failure testing | No (401) |

---

## 7. Test Control API

### 7.1 Overview

HTTP API for test setup and state inspection. Runs on `http://localhost:8766`.

### 7.2 Endpoints

#### POST /reset

Reset simulator to initial state.

**Request:**
```json
{
  "ambient_temp": 22.0,    // optional
  "cooker_id": "test-123"  // optional
}
```

**Response:**
```json
{
  "status": "ok",
  "state": "IDLE",
  "water_temp": 22.0
}
```

---

#### POST /set-state

Force simulator into specific state (for test setup).

**Request:**
```json
{
  "state": "COOKING",
  "water_temp": 65.0,
  "target_temp": 65.0,
  "timer_remaining": 2700,
  "timer_elapsed": 2700
}
```

**Response:**
```json
{
  "status": "ok",
  "state": "COOKING"
}
```

---

#### POST /set-offline

Simulate device going offline.

**Request:**
```json
{
  "offline": true,
  "duration_seconds": 30  // optional, auto-recover after
}
```

**Response:**
```json
{
  "status": "ok",
  "offline": true
}
```

---

#### POST /set-time-scale

Adjust time acceleration.

**Request:**
```json
{
  "time_scale": 60.0
}
```

**Response:**
```json
{
  "status": "ok",
  "time_scale": 60.0
}
```

---

#### POST /trigger-error

Inject error conditions.

**Request:**
```json
{
  "error_type": "WATER_LEVEL_LOW"  // or WATER_LEVEL_CRITICAL, MOTOR_STUCK
}
```

**Response:**
```json
{
  "status": "ok",
  "pin-info": {
    "water-level-low": 1
  }
}
```

---

#### GET /state

Get current device state (for assertions).

**Response:**
```json
{
  "state": "COOKING",
  "water_temp": 64.8,
  "target_temp": 65.0,
  "timer_remaining": 2650,
  "timer_elapsed": 2750,
  "heater_duty_cycle": 15.5,
  "motor_duty_cycle": 100.0,
  "online": true,
  "pin_info": {
    "device_safe": 1,
    "water_leak": 0,
    "water_level_low": 0,
    "water_level_critical": 0
  }
}
```

---

#### GET /messages

Get message history (for debugging).

**Query Parameters:**
- `limit`: Max messages to return (default: 100)
- `direction`: `"inbound"` | `"outbound"` | `"all"` (default: `"all"`)

**Response:**
```json
{
  "messages": [
    {
      "timestamp": "2026-01-18T10:30:00Z",
      "direction": "inbound",
      "command": "CMD_APC_START",
      "requestId": "abc123..."
    },
    {
      "timestamp": "2026-01-18T10:30:00Z",
      "direction": "outbound",
      "command": "RESPONSE",
      "requestId": "abc123..."
    }
  ]
}
```

---

## 8. Error Simulation

### 8.1 Error Codes

| Code | HTTP/WS Status | Condition | Trigger |
|------|----------------|-----------|---------|
| `DEVICE_OFFLINE` | 404 / Close 1006 | Device not connected | `POST /set-offline` |
| `DEVICE_BUSY` | 409 | Already cooking | Send CMD_APC_START when cooking |
| `NO_ACTIVE_COOK` | 409 | Not cooking | Send CMD_APC_STOP when idle |
| `INVALID_TEMPERATURE` | 400 | Temp out of range | Send temp < 40 or > 100 |
| `INVALID_TIMER` | 400 | Timer out of range | Send timer < 60 or > 359940 |
| `AUTH_FAILED` | 401 | Invalid token | Connect with invalid token |
| `TOKEN_EXPIRED` | 401 | Token expired | Connect with expired token |
| `WATER_LEVEL_CRITICAL` | N/A | Water too low | `POST /trigger-error` |
| `HEATER_OVERTEMP` | N/A | Heater over temperature | `POST /trigger-error` |
| `TRIAC_OVERTEMP` | N/A | Triac over temperature | `POST /trigger-error` |
| `WATER_LEAK` | N/A | Water leak detected | `POST /trigger-error` |

### 8.2 Network Condition Simulation

All network conditions are simulated via the unified `/trigger-error` endpoint:

| Condition | Trigger | Behavior |
|-----------|---------|----------|
| Disconnect | `POST /set-offline {"offline": true}` | Close WebSocket with code 1006 |
| Latency | `POST /trigger-error {"error_type": "network_latency", "latency_ms": 500}` | Delay all responses |
| Intermittent | `POST /trigger-error {"error_type": "intermittent_failure", "failure_rate": 0.3}` | Random failures |

**Example: Trigger network latency**
```json
POST /trigger-error
{
  "error_type": "network_latency",
  "latency_ms": 1000,
  "duration": 30.0
}
```

**Example: Trigger intermittent failures**
```json
POST /trigger-error
{
  "error_type": "intermittent_failure",
  "failure_rate": 0.3,
  "duration": 60.0
}
```

---

## 9. Test Scenarios

### 9.1 Happy Path Tests

| Test ID | Scenario | Steps | Expected |
|---------|----------|-------|----------|
| SIM-HP-01 | Connect and receive state | Connect with valid token | EVENT_APC_STATE received |
| SIM-HP-02 | Start cook | Send CMD_APC_START | RESPONSE ok, state → PREHEATING |
| SIM-HP-03 | Preheat to cooking | Wait for temp to reach target | state → COOKING |
| SIM-HP-04 | Cook complete | Wait for timer to expire | state → DONE |
| SIM-HP-05 | Stop cook | Send CMD_APC_STOP | RESPONSE ok, state → IDLE |
| SIM-HP-06 | Change temp while cooking | Send CMD_APC_SET_TARGET_TEMP | target_temp updated |
| SIM-HP-07 | Change timer while cooking | Send CMD_APC_SET_TIMER | timer updated |

### 9.2 Error Condition Tests

| Test ID | Scenario | Steps | Expected |
|---------|----------|-------|----------|
| SIM-ERR-01 | Start when busy | CMD_APC_START while cooking | DEVICE_BUSY error |
| SIM-ERR-02 | Stop when idle | CMD_APC_STOP while idle | NO_ACTIVE_COOK error |
| SIM-ERR-03 | Invalid temperature | CMD_APC_START with temp=30 | INVALID_TEMPERATURE error |
| SIM-ERR-04 | Invalid timer | CMD_APC_START with timer=30 | INVALID_TIMER error |
| SIM-ERR-05 | Invalid token | Connect with bad token | Connection rejected (401) |
| SIM-ERR-06 | Device offline | Set offline, send command | Connection closed (1006) |

### 9.3 State Transition Tests

| Test ID | Scenario | Initial State | Action | Expected State |
|---------|----------|---------------|--------|----------------|
| SIM-ST-01 | Idle to preheating | IDLE | CMD_APC_START | PREHEATING |
| SIM-ST-02 | Preheating to cooking | PREHEATING | Temp reaches target | COOKING |
| SIM-ST-03 | Cooking to done | COOKING | Timer expires | DONE |
| SIM-ST-04 | Preheating to idle | PREHEATING | CMD_APC_STOP | IDLE |
| SIM-ST-05 | Cooking to idle | COOKING | CMD_APC_STOP | IDLE |
| SIM-ST-06 | Done to idle | DONE | CMD_APC_STOP | IDLE |

### 9.4 Timing Tests

| Test ID | Scenario | Setup | Verification |
|---------|----------|-------|--------------|
| SIM-TM-01 | State broadcast frequency (idle) | IDLE state | EVENT_APC_STATE every ~30s |
| SIM-TM-02 | State broadcast frequency (cooking) | COOKING state | EVENT_APC_STATE every ~2s |
| SIM-TM-03 | Timer countdown accuracy | COOKING, time_scale=60 | Timer decreases correctly |
| SIM-TM-04 | Temp increase rate | PREHEATING | Temp increases per heating_rate |

---

## 10. Configuration

### 10.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_WS_PORT` | 8765 | WebSocket server port |
| `SIM_AUTH_PORT` | 8764 | Firebase mock port |
| `SIM_CONTROL_PORT` | 8766 | Test control API port |
| `SIM_TIME_SCALE` | 1.0 | Time acceleration factor |
| `SIM_AMBIENT_TEMP` | 22.0 | Initial water temperature |
| `SIM_HEATING_RATE` | 1.0 | °C per minute heating rate |
| `SIM_COOKER_ID` | test-cooker-123 | Default cooker ID |
| `SIM_LOG_LEVEL` | INFO | Logging verbosity |

### 10.2 Configuration File

Optional `simulator.yaml`:

```yaml
simulator:
  ports:
    websocket: 8765
    firebase: 8764
    control: 8766

  physics:
    ambient_temp: 22.0
    heating_rate: 1.0
    cooling_rate: 0.5
    temp_tolerance: 0.5

  timing:
    time_scale: 1.0
    state_broadcast_idle: 30.0
    state_broadcast_cooking: 2.0

  device:
    cooker_id: "anova test-cooker-123"
    type: "pro"
    firmware_version: "3.3.01"

  auth:
    valid_tokens:
      - "valid-test-token"
    expired_tokens:
      - "expired-test-token"
```

---

## 11. Pytest Integration

### 11.1 Fixture Usage

```python
import pytest
from simulator import AnovaSimulator

@pytest.fixture
def simulator():
    """Start simulator for test, stop after."""
    sim = AnovaSimulator(time_scale=60.0)  # Accelerated time
    sim.start()
    yield sim
    sim.stop()

@pytest.fixture
def ws_client(simulator):
    """WebSocket client connected to simulator."""
    import websockets
    client = websockets.connect(
        f"ws://localhost:{simulator.ws_port}?token=valid-test-token&supportedAccessories=APC"
    )
    yield client
    client.close()

def test_start_cook(simulator, ws_client):
    """Test starting a cook via WebSocket."""
    # Arrange
    simulator.reset()

    # Act
    ws_client.send(json.dumps({
        "command": "CMD_APC_START",
        "requestId": "test123",
        "payload": {
            "cookerId": simulator.cooker_id,
            "type": "pro",
            "targetTemperature": 65.0,
            "unit": "C",
            "timer": 5400,
            "requestId": "test123"
        }
    }))

    response = json.loads(ws_client.recv())

    # Assert
    assert response["command"] == "RESPONSE"
    assert response["payload"]["status"] == "ok"
    assert simulator.state == "PREHEATING"
```

### 11.2 Async Fixture (for async tests)

```python
import pytest
import asyncio
import websockets

@pytest.fixture
async def async_simulator():
    """Async simulator fixture."""
    from simulator import AnovaSimulator
    sim = AnovaSimulator(time_scale=60.0)
    await sim.start_async()
    yield sim
    await sim.stop_async()

@pytest.fixture
async def async_ws_client(async_simulator):
    """Async WebSocket client."""
    uri = f"ws://localhost:{async_simulator.ws_port}?token=valid-test-token&supportedAccessories=APC"
    async with websockets.connect(uri) as ws:
        yield ws

@pytest.mark.asyncio
async def test_cook_flow(async_simulator, async_ws_client):
    """Test complete cook flow with async."""
    # Wait for initial state
    initial = await async_ws_client.recv()
    state = json.loads(initial)
    assert state["command"] == "EVENT_APC_STATE"

    # Start cook
    await async_ws_client.send(json.dumps({
        "command": "CMD_APC_START",
        ...
    }))

    response = await async_ws_client.recv()
    assert json.loads(response)["payload"]["status"] == "ok"
```

---

## 12. Implementation Checklist

### Phase 1: Core (MVP) ✅

- [x] **SIM-CORE-01**: WebSocket server accepting connections
- [x] **SIM-CORE-02**: Token validation on connect
- [x] **SIM-CORE-03**: CMD_APC_START command handler
- [x] **SIM-CORE-04**: CMD_APC_STOP command handler
- [x] **SIM-CORE-05**: EVENT_APC_STATE broadcast loop
- [x] **SIM-CORE-06**: Basic state machine (IDLE, PREHEATING, COOKING, DONE)

### Phase 2: Physics ✅

- [x] **SIM-PHYS-01**: Temperature simulation (heating)
- [x] **SIM-PHYS-02**: Timer countdown
- [x] **SIM-PHYS-03**: Automatic state transitions based on physics
- [x] **SIM-PHYS-04**: Time acceleration support

### Phase 3: Commands ✅

- [x] **SIM-CMD-01**: CMD_APC_SET_TARGET_TEMP
- [x] **SIM-CMD-02**: CMD_APC_SET_TIMER
- [x] **SIM-CMD-03**: Command validation (temp/timer ranges, Fahrenheit support)
- [x] **SIM-CMD-04**: Error responses for invalid commands

### Phase 4: Firebase Mock ✅

- [x] **SIM-AUTH-01**: Token exchange endpoint
- [x] **SIM-AUTH-02**: Test token validation
- [x] **SIM-AUTH-03**: Token expiry simulation

### Phase 5: Test Control ✅

- [x] **SIM-CTRL-01**: Reset endpoint
- [x] **SIM-CTRL-02**: Set state endpoint
- [x] **SIM-CTRL-03**: Set offline endpoint
- [x] **SIM-CTRL-04**: State inspection endpoint
- [x] **SIM-CTRL-05**: Message history endpoint

### Phase 6: Error Simulation ✅

- [x] **SIM-ERR-01**: Device offline simulation
- [x] **SIM-ERR-02**: Device busy error
- [x] **SIM-ERR-03**: Water level warnings (low, critical)
- [x] **SIM-ERR-04**: Network latency injection
- [x] **SIM-ERR-05**: Intermittent failure mode
- [x] **SIM-ERR-06**: Heater overtemp error
- [x] **SIM-ERR-07**: Triac overtemp error
- [x] **SIM-ERR-08**: Water leak detection
- [x] **SIM-ERR-09**: Motor stuck error

### Phase 7: Integration ✅

- [x] **SIM-INT-01**: Pytest fixtures (conftest.py)
- [ ] **SIM-INT-02**: Docker support
- [ ] **SIM-INT-03**: CI/CD integration
- [x] **SIM-INT-04**: Documentation

---

## 13. Appendix

### A. Full EVENT_APC_STATE Example

```json
{
  "command": "EVENT_APC_STATE",
  "payload": {
    "cookerId": "anova abc-1234567890",
    "type": "pro",
    "state": {
      "audio": {
        "file-name": "",
        "volume": 50
      },
      "cap-touch": {
        "minus-button": 0,
        "play-button": 0,
        "plus-button": 0,
        "target-temperature-button": 0,
        "timer-button": 0,
        "water-temperature-button": 0
      },
      "firmware-info": {
        "firmware-version": "3.3.01",
        "firmware-update-available": false
      },
      "heater-control": {
        "duty-cycle": 85.5
      },
      "job": {
        "cook-time-seconds": 5400,
        "id": "a1b2c3d4e5f6g7h8i9j0kl",
        "mode": "COOKING",  // Matches job-status.state
        "target-temperature": 65.0,
        "temperature-unit": "C"
      },
      "job-status": {
        "cook-time-remaining": 3200,
        "state": "COOKING",
        "job-start-systick": 1705584600,
        "state-change-systick": 1705585200
      },
      "motor-control": {
        "duty-cycle": 100.0
      },
      "motor-info": {
        "rpm": 1200
      },
      "network-info": {
        "connection-status": "connected-station",
        "mac-address": "AA:BB:CC:DD:EE:FF",
        "ssid": "HomeNetwork",
        "security-type": "WPA2"
      },
      "pin-info": {
        "device-safe": 1,
        "water-leak": 0,
        "water-level-critical": 0,
        "water-level-low": 0,
        "motor-stuck": 0
      },
      "system-info": {
        "firmware-version": "3.3.01",
        "mcu-temperature": 42,
        "heap-size": 98304
      },
      "temperature-info": {
        "heater-temperature": 68.2,
        "triac-temperature": 45,
        "water-temperature": 64.8
      }
    }
  }
}
```

### B. Request ID Generation

```python
import secrets

def generate_request_id() -> str:
    """Generate 22-digit hexadecimal request ID."""
    return secrets.token_hex(11)  # 22 hex characters
```

### C. Temperature Conversion

```python
def celsius_to_fahrenheit(c: float) -> float:
    return c * 9/5 + 32

def fahrenheit_to_celsius(f: float) -> float:
    return (f - 32) * 5/9
```

---

## 14. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-18 | Claude | Initial specification |
| 1.1 | 2026-01-20 | Claude | Implementation complete. Updated job.mode to match job_status.state. Added new error types (HEATER_OVERTEMP, TRIAC_OVERTEMP, WATER_LEAK). Added Fahrenheit validation. Updated checklist to reflect completed phases. |
