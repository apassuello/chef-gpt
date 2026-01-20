# Anova Simulator Implementation Plan

> **Document Type:** Implementation Plan & Progress Tracker
> **Status:** IN PROGRESS
> **Created:** 2026-01-19
> **Spec Reference:** [SIMULATOR-SPECIFICATION.md](./SIMULATOR-SPECIFICATION.md)

---

## Progress Summary

| Phase | Description | Status | Checkpoint | Tests |
|-------|-------------|--------|------------|-------|
| 0 | Project Setup | COMPLETE | CP-00 | - |
| 1 | Core WebSocket Server | IN_PROGRESS | CP-01 | 5 |
| 2 | Command Handlers | NOT_STARTED | CP-02 | 8 |
| 3 | State Broadcasting | NOT_STARTED | CP-03 | 4 |
| 4 | Physics Engine | NOT_STARTED | CP-04 | 6 |
| 5 | Firebase Mock | NOT_STARTED | CP-05 | 4 |
| 6 | Test Control API | NOT_STARTED | CP-06 | 6 |
| 7 | Error Simulation | NOT_STARTED | CP-07 | 5 |
| 8 | Integration & Polish | NOT_STARTED | CP-08 | 3 |

**Overall Progress:** 1/9 phases complete (11%)

---

## Phase 0: Project Setup (CP-00)

### Objective
Create project structure and dependencies.

### Tasks
- [ ] Create `simulator/` directory structure
- [ ] Create `__init__.py` files
- [ ] Create `types.py` with enums and dataclasses
- [ ] Create `config.py` with configuration
- [ ] Update `requirements.txt` with websockets dependency
- [ ] Create `tests/simulator/` test directory

### Files to Create
```
simulator/
├── __init__.py
├── types.py          # DeviceState enum, CookerState dataclass
├── config.py         # SimulatorConfig dataclass
└── messages.py       # Message type constants

tests/simulator/
├── __init__.py
└── conftest.py       # Simulator test fixtures
```

### Verification
- [ ] `python -c "from simulator import types, config"` succeeds
- [ ] All type hints valid: `mypy simulator/`

### Commit Message
```
feat(simulator): Initialize project structure and types (CP-00)
```

---

## Phase 1: Core WebSocket Server (CP-01)

### Objective
Implement basic WebSocket server that accepts connections and validates tokens.

### Tasks
- [ ] Implement `websocket_server.py` with connection handling
- [ ] Implement token validation (simple check for test tokens)
- [ ] Implement message envelope parsing
- [ ] Implement connection lifecycle (connect, disconnect, error)
- [ ] Create basic `server.py` entry point

### Files to Create/Modify
```
simulator/
├── websocket_server.py   # WebSocket server implementation
└── server.py             # Main entry point
```

### Test Cases (5 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| WS-01 | Connect with valid token | Connection accepted |
| WS-02 | Connect with invalid token | Connection rejected (401) |
| WS-03 | Connect without token | Connection rejected (401) |
| WS-04 | Send malformed JSON | Error response |
| WS-05 | Graceful disconnect | Clean shutdown |

### Verification
```bash
# Start server
python -m simulator.server &

# Test connection (using websocat or similar)
websocat "ws://localhost:8765?token=valid-test-token&supportedAccessories=APC"

# Run tests
pytest tests/simulator/test_websocket.py -v
```

### Agent Verification
- [ ] Agent: Verify WebSocket accepts connections with valid token
- [ ] Agent: Verify WebSocket rejects connections with invalid token

### Commit Message
```
feat(simulator): Implement core WebSocket server with auth (CP-01)
```

---

## Phase 2: Command Handlers (CP-02)

### Objective
Implement all four APC commands with validation.

### Tasks
- [ ] Implement `device.py` with DeviceStateMachine class
- [ ] Implement CMD_APC_START handler
- [ ] Implement CMD_APC_STOP handler
- [ ] Implement CMD_APC_SET_TARGET_TEMP handler
- [ ] Implement CMD_APC_SET_TIMER handler
- [ ] Implement command validation (temp/timer ranges)
- [ ] Implement RESPONSE message generation

### Files to Create/Modify
```
simulator/
├── device.py             # DeviceStateMachine class
├── commands.py           # Command handlers
└── websocket_server.py   # Wire up command routing
```

### Test Cases (8 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| CMD-01 | START with valid params | RESPONSE ok, state=PREHEATING |
| CMD-02 | START with temp < 40 | RESPONSE error INVALID_TEMPERATURE |
| CMD-03 | START with temp > 100 | RESPONSE error INVALID_TEMPERATURE |
| CMD-04 | START when already cooking | RESPONSE error DEVICE_BUSY |
| CMD-05 | STOP when cooking | RESPONSE ok, state=IDLE |
| CMD-06 | STOP when idle | RESPONSE error NO_ACTIVE_COOK |
| CMD-07 | SET_TARGET_TEMP valid | RESPONSE ok, temp updated |
| CMD-08 | SET_TIMER valid | RESPONSE ok, timer updated |

### Verification
```bash
pytest tests/simulator/test_commands.py -v
```

### Agent Verification
- [ ] Agent: Send CMD_APC_START and verify state transition
- [ ] Agent: Verify all error conditions return correct codes

### Commit Message
```
feat(simulator): Implement APC command handlers (CP-02)
```

---

## Phase 3: State Broadcasting (CP-03)

### Objective
Implement EVENT_APC_STATE periodic broadcasting.

### Tasks
- [ ] Implement full EVENT_APC_STATE message structure
- [ ] Implement broadcast loop (async)
- [ ] Implement frequency control (2s cooking, 30s idle)
- [ ] Send initial state on connection

### Files to Create/Modify
```
simulator/
├── messages.py           # EVENT_APC_STATE builder
├── broadcaster.py        # Async broadcast loop
└── websocket_server.py   # Integrate broadcaster
```

### Test Cases (4 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| BC-01 | Initial state on connect | EVENT_APC_STATE received |
| BC-02 | Broadcast while idle | ~30s interval |
| BC-03 | Broadcast while cooking | ~2s interval |
| BC-04 | State reflects current values | All fields correct |

### Verification
```bash
pytest tests/simulator/test_broadcast.py -v
```

### Agent Verification
- [ ] Agent: Connect and verify initial EVENT_APC_STATE
- [ ] Agent: Verify broadcast frequency changes with state

### Commit Message
```
feat(simulator): Implement EVENT_APC_STATE broadcasting (CP-03)
```

---

## Phase 4: Physics Engine (CP-04)

### Objective
Implement temperature and timer simulation with time acceleration.

### Tasks
- [ ] Implement `physics.py` with PhysicsEngine class
- [ ] Implement temperature heating model
- [ ] Implement temperature cooling model (when idle)
- [ ] Implement timer countdown
- [ ] Implement automatic state transitions
- [ ] Implement time_scale configuration

### Files to Create/Modify
```
simulator/
├── physics.py            # PhysicsEngine class
├── device.py             # Integrate physics
└── config.py             # Add physics parameters
```

### Test Cases (6 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| PH-01 | Temperature increases during preheat | water_temp rises |
| PH-02 | PREHEATING→COOKING at target temp | State transition |
| PH-03 | Timer counts down during cooking | timer_remaining decreases |
| PH-04 | COOKING→DONE when timer=0 | State transition |
| PH-05 | Time acceleration (60x) | 1 min passes in 1 sec |
| PH-06 | Temperature cools when idle | water_temp decreases |

### Verification
```bash
pytest tests/simulator/test_physics.py -v
```

### Agent Verification
- [ ] Agent: Start cook with time_scale=60, verify transitions
- [ ] Agent: Verify temperature changes match heating_rate

### Commit Message
```
feat(simulator): Implement physics engine with time acceleration (CP-04)
```

---

## Phase 5: Firebase Mock (CP-05)

### Objective
Implement Firebase authentication mock endpoints.

### Tasks
- [ ] Implement `firebase_mock.py` with Flask/aiohttp server
- [ ] Implement token exchange endpoint
- [ ] Implement token generation
- [ ] Implement token validation rules
- [ ] Integrate with WebSocket server

### Files to Create/Modify
```
simulator/
├── firebase_mock.py      # Firebase mock server
├── auth.py               # Token validation logic
└── server.py             # Start Firebase mock
```

### Test Cases (4 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| AUTH-01 | Token refresh valid | Returns id_token |
| AUTH-02 | Token refresh invalid | Returns 401 |
| AUTH-03 | WebSocket with Firebase token | Connection accepted |
| AUTH-04 | Token expiry simulation | Connection rejected after expiry |

### Verification
```bash
pytest tests/simulator/test_auth.py -v
```

### Agent Verification
- [ ] Agent: Get token from Firebase mock, use for WebSocket
- [ ] Agent: Verify expired tokens are rejected

### Commit Message
```
feat(simulator): Implement Firebase authentication mock (CP-05)
```

---

## Phase 6: Test Control API (CP-06)

### Objective
Implement HTTP API for test setup and state inspection.

### Tasks
- [ ] Implement `control_api.py` with Flask/aiohttp server
- [ ] Implement POST /reset endpoint
- [ ] Implement POST /set-state endpoint
- [ ] Implement POST /set-offline endpoint
- [ ] Implement POST /set-time-scale endpoint
- [ ] Implement GET /state endpoint
- [ ] Implement GET /messages endpoint

### Files to Create/Modify
```
simulator/
├── control_api.py        # Test control HTTP server
└── server.py             # Start control API
```

### Test Cases (6 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| CTL-01 | Reset to initial state | state=IDLE, temp=ambient |
| CTL-02 | Set state to COOKING | State updated, physics active |
| CTL-03 | Set offline | WebSocket closes |
| CTL-04 | Set time scale | Physics accelerated |
| CTL-05 | Get state | Returns full state JSON |
| CTL-06 | Get messages | Returns message history |

### Verification
```bash
pytest tests/simulator/test_control_api.py -v
```

### Agent Verification
- [ ] Agent: Use control API to set state, verify via WebSocket
- [ ] Agent: Test reset functionality

### Commit Message
```
feat(simulator): Implement test control API (CP-06)
```

---

## Phase 7: Error Simulation (CP-07)

### Objective
Implement error condition simulation for comprehensive testing.

### Tasks
- [ ] Implement device offline simulation
- [ ] Implement water level warnings (low, critical)
- [ ] Implement motor stuck error
- [ ] Implement network latency injection
- [ ] Implement intermittent failure mode

### Files to Create/Modify
```
simulator/
├── errors.py             # Error simulation logic
├── control_api.py        # Add trigger-error endpoint
└── device.py             # Integrate error states
```

### Test Cases (5 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| ERR-01 | Device goes offline | WebSocket closes with 1006 |
| ERR-02 | Water level low warning | pin-info.water-level-low=1 |
| ERR-03 | Water level critical | Cooking stops |
| ERR-04 | Network latency | Responses delayed |
| ERR-05 | Intermittent failures | Random command failures |

### Verification
```bash
pytest tests/simulator/test_errors.py -v
```

### Agent Verification
- [ ] Agent: Trigger offline, verify client disconnect
- [ ] Agent: Trigger water-level-low, verify in EVENT_APC_STATE

### Commit Message
```
feat(simulator): Implement error simulation (CP-07)
```

---

## Phase 8: Integration & Polish (CP-08)

### Objective
Final integration, documentation, and pytest fixtures.

### Tasks
- [ ] Create pytest fixtures in `conftest.py`
- [ ] Create async pytest fixtures
- [ ] Add Docker support (Dockerfile, docker-compose)
- [ ] Update main README with simulator usage
- [ ] Run full test suite
- [ ] Performance testing

### Files to Create/Modify
```
simulator/
├── Dockerfile
└── docker-compose.yml

tests/
├── conftest.py           # Global simulator fixtures
└── integration/
    └── test_with_simulator.py
```

### Test Cases (3 tests)
| Test ID | Description | Expected |
|---------|-------------|----------|
| INT-01 | Full cook cycle with simulator | Complete flow works |
| INT-02 | Simulator fixture isolation | Tests don't interfere |
| INT-03 | Docker container works | Simulator runs in Docker |

### Verification
```bash
# Full test suite
pytest tests/ -v --cov=simulator

# Docker
docker-compose up -d simulator
pytest tests/integration/ -v
```

### Agent Verification
- [ ] Agent: Run full integration test suite
- [ ] Agent: Verify test isolation (parallel tests)

### Commit Message
```
feat(simulator): Complete integration and documentation (CP-08)
```

---

## Checkpoint Log

### CP-00: Project Setup
- **Status:** COMPLETE
- **Started:** 2026-01-19
- **Completed:** 2026-01-19
- **Commit:** cd08ff2
- **Notes:** All files created, imports verified

### CP-01: Core WebSocket Server
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/5
- **Notes:** -

### CP-02: Command Handlers
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/8
- **Notes:** -

### CP-03: State Broadcasting
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/4
- **Notes:** -

### CP-04: Physics Engine
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/6
- **Notes:** -

### CP-05: Firebase Mock
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/4
- **Notes:** -

### CP-06: Test Control API
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/6
- **Notes:** -

### CP-07: Error Simulation
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/5
- **Notes:** -

### CP-08: Integration & Polish
- **Status:** NOT_STARTED
- **Started:** -
- **Completed:** -
- **Commit:** -
- **Tests Passed:** 0/3
- **Notes:** -

---

## Dependency Graph

```
CP-00 (Setup)
   │
   ▼
CP-01 (WebSocket) ──────────────────┐
   │                                │
   ▼                                ▼
CP-02 (Commands) ───────────► CP-05 (Firebase)
   │                                │
   ▼                                │
CP-03 (Broadcasting)                │
   │                                │
   ▼                                │
CP-04 (Physics) ◄───────────────────┘
   │
   ▼
CP-06 (Control API)
   │
   ▼
CP-07 (Errors)
   │
   ▼
CP-08 (Integration)
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WebSocket library issues | Low | High | Use well-tested `websockets` library |
| Async complexity | Medium | Medium | Follow established patterns, thorough testing |
| Time acceleration bugs | Medium | High | Extensive timing tests, tolerance thresholds |
| Test flakiness | Medium | Medium | Use deterministic time, avoid real sleeps |

---

## Success Criteria

### Minimum Viable Product (MVP)
- [ ] WebSocket server accepts connections
- [ ] CMD_APC_START and CMD_APC_STOP work
- [ ] EVENT_APC_STATE broadcasts
- [ ] Basic state machine works

### Full Implementation
- [ ] All 4 commands implemented
- [ ] Physics simulation works
- [ ] Time acceleration works
- [ ] All error scenarios testable
- [ ] Pytest fixtures ready
- [ ] 41/41 tests pass

---

## Appendix: File Checklist

| File | Phase | Status |
|------|-------|--------|
| `simulator/__init__.py` | 0 | NOT_STARTED |
| `simulator/types.py` | 0 | NOT_STARTED |
| `simulator/config.py` | 0 | NOT_STARTED |
| `simulator/messages.py` | 0, 3 | NOT_STARTED |
| `simulator/server.py` | 1 | NOT_STARTED |
| `simulator/websocket_server.py` | 1 | NOT_STARTED |
| `simulator/device.py` | 2 | NOT_STARTED |
| `simulator/commands.py` | 2 | NOT_STARTED |
| `simulator/broadcaster.py` | 3 | NOT_STARTED |
| `simulator/physics.py` | 4 | NOT_STARTED |
| `simulator/firebase_mock.py` | 5 | NOT_STARTED |
| `simulator/auth.py` | 5 | NOT_STARTED |
| `simulator/control_api.py` | 6 | NOT_STARTED |
| `simulator/errors.py` | 7 | NOT_STARTED |
| `tests/simulator/__init__.py` | 0 | NOT_STARTED |
| `tests/simulator/conftest.py` | 0 | NOT_STARTED |
| `tests/simulator/test_websocket.py` | 1 | NOT_STARTED |
| `tests/simulator/test_commands.py` | 2 | NOT_STARTED |
| `tests/simulator/test_broadcast.py` | 3 | NOT_STARTED |
| `tests/simulator/test_physics.py` | 4 | NOT_STARTED |
| `tests/simulator/test_auth.py` | 5 | NOT_STARTED |
| `tests/simulator/test_control_api.py` | 6 | NOT_STARTED |
| `tests/simulator/test_errors.py` | 7 | NOT_STARTED |
