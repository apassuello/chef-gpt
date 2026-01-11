# Integration Testing Architecture - Visual Guide

> **Visual overview of test infrastructure and patterns**

---

## Test Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Integration Test Suite                          │
│                     (24+ test scenarios)                            │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌────────────────┐      ┌────────────────┐     ┌────────────────┐
│  Happy Path    │      │  Error Paths   │     │  Edge Cases    │
│  Tests (2)     │      │  Tests (3)     │     │  Tests (3)     │
├────────────────┤      ├────────────────┤     ├────────────────┤
│ INT-01         │      │ INT-03         │     │ INT-06         │
│ INT-02         │      │ INT-04         │     │ INT-07         │
│                │      │ INT-05         │     │ INT-08         │
└────────────────┘      └────────────────┘     └────────────────┘

         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Shared Fixtures                               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  app    │  │ client  │  │ auth_headers │  │ valid_cook   │    │
│  │         │  │         │  │              │  │ _requests    │    │
│  └─────────┘  └─────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Mock Infrastructure                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐     │
│  │           tests/mocks/anova_responses.py                  │     │
│  │  (Centralized mock data - single source of truth)         │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                 │                                    │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │           tests/mocks/anova_fixtures.py                   │     │
│  │  (Composable mock fixtures for all scenarios)             │     │
│  └───────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    External Dependencies (Mocked)                    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐              ┌──────────────────┐            │
│  │  Firebase Auth   │              │  Anova Cloud API │            │
│  │  (Mocked)        │              │  (Mocked)        │            │
│  └──────────────────┘              └──────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Test Execution Flow

```
┌───────────────────────────────────────────────────────────────────┐
│ 1. Test Invocation                                                │
│    $ pytest tests/integration/test_int_happy_path.py -v           │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│ 2. Fixture Setup (per test)                                       │
│    • Create fresh Flask app                                       │
│    • Create test client                                           │
│    • Load test config                                             │
│    • Prepare mock fixtures                                        │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│ 3. Mock Activation                                                │
│    • mock_anova_api_success() called                              │
│    • responses.add() registers mock HTTP responses                │
│    • No real API calls will be made                               │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│ 4. Test Execution                                                 │
│    • client.post('/start-cook', ...)                              │
│    • Request flows through:                                       │
│      Flask → routes.py → validators.py → anova_client.py          │
│    • anova_client makes HTTP request                              │
│    • responses library intercepts and returns mock                │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│ 5. Assertions                                                     │
│    • assert response.status_code == 200                           │
│    • assert response.get_json()["success"] is True                │
│    • All assertions pass → test succeeds                          │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────┐
│ 6. Cleanup                                                        │
│    • Flask app discarded                                          │
│    • Mock responses cleared                                       │
│    • Next test starts with clean state                            │
└───────────────────────────────────────────────────────────────────┘
```

---

## Fixture Dependency Graph

```
                           test_config (session)
                                   │
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
             auth_headers       app         valid_cook_requests
                                 │
                                 │
                                 ▼
                              client
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
         mock_anova_api_   mock_anova_   mock_anova_
            success        api_offline   api_busy
                    │            │            │
                    └────────────┼────────────┘
                                 │
                                 ▼
                         integration tests
```

---

## Mock Management Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  tests/mocks/anova_responses.py                      │
│                  (Mock Data Repository)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Firebase Auth Responses                                      │  │
│  │  • FIREBASE_AUTH_SUCCESS                                      │  │
│  │  • FIREBASE_TOKEN_REFRESH_SUCCESS                             │  │
│  │  • FIREBASE_TOKEN_EXPIRED                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Device Status Responses                                      │  │
│  │  • DEVICE_STATUS_IDLE                                         │  │
│  │  • DEVICE_STATUS_PREHEATING                                   │  │
│  │  • DEVICE_STATUS_COOKING                                      │  │
│  │  • DEVICE_STATUS_DONE                                         │  │
│  │  • DEVICE_STATUS_OFFLINE_404                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Device Command Responses                                     │  │
│  │  • START_COOK_SUCCESS                                         │  │
│  │  • START_COOK_ALREADY_COOKING                                 │  │
│  │  • STOP_COOK_SUCCESS                                          │  │
│  │  • STOP_COOK_NOT_COOKING                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Helper Functions                                             │  │
│  │  • anova_device_url(device_id, endpoint)                      │  │
│  │  • get_device_status_at_temp(temp, target, state)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ imported by
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  tests/mocks/anova_fixtures.py                       │
│                  (Composable Mock Fixtures)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Atomic Fixtures (building blocks):                                 │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  • mock_firebase_auth_success()                             │    │
│  │  • mock_device_status_idle()                                │    │
│  │  • mock_device_start_cook_success()                         │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Composite Fixtures (complete scenarios):                            │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  • mock_anova_api_success()                                 │    │
│  │    ├── Firebase auth                                        │    │
│  │    ├── Device idle status                                   │    │
│  │    ├── Start cook success                                   │    │
│  │    └── Stop cook success                                    │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  • mock_anova_api_offline()                                 │    │
│  │    ├── Firebase auth (works)                                │    │
│  │    └── Device offline (404)                                 │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  • mock_state_progression_idle_to_cooking()                 │    │
│  │    ├── Status: idle                                         │    │
│  │    ├── Start command                                        │    │
│  │    ├── Status: preheating                                   │    │
│  │    └── Status: cooking                                      │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ used by
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Integration Tests                                │
│  tests/integration/test_*.py                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Test Pattern Examples

### Pattern 1: Simple Happy Path

```
Test Function
└── Fixture: mock_anova_api_success()
    └── Activate mock
        ├── Register Firebase auth response
        ├── Register device status response
        ├── Register start cook response
        └── Register stop cook response

Test Execution
└── client.post('/start-cook', ...)
    ├── Request → Flask → routes.py
    ├── routes.py → validators.py (validation)
    ├── routes.py → anova_client.py
    ├── anova_client.py → HTTP request (intercepted by responses)
    ├── Mock returns success response
    └── Response → routes.py → client

Assertions
├── assert response.status_code == 200
├── assert response.json["success"] is True
└── assert response.json["target_temp"] == 65.0
```

---

### Pattern 2: State Transition

```
Test Function
└── Fixture: mock_state_progression_idle_to_cooking()
    └── Register sequential responses:
        1. GET /status → idle
        2. POST /start → success
        3. GET /status → preheating
        4. GET /status → cooking

Test Execution
├── Request 1: client.get('/status') → idle
├── Request 2: client.post('/start-cook') → success
├── Request 3: client.get('/status') → preheating
└── Request 4: client.get('/status') → cooking

Assertions
├── Response 1: state == "idle"
├── Response 3: state == "preheating"
└── Response 4: state == "cooking"
```

---

### Pattern 3: Parameterized Validation

```
Test Function (parameterized)
├── Parameter Set 1: (temp=35, error="TEMPERATURE_TOO_LOW")
├── Parameter Set 2: (temp=105, error="TEMPERATURE_TOO_HIGH")
├── Parameter Set 3: (temp=56, food="chicken", error="POULTRY_TEMP_UNSAFE")
└── ... (16+ parameter sets)

Each Test Run
├── client.post('/start-cook', json={temperature: param.temp})
├── routes.py → validators.py
├── validators.py raises ValidationError
├── routes.py catches and returns 400
└── assert response.json["error"] == param.expected_error
```

---

## CI/CD Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ Developer commits code                                               │
│ $ git push origin feature-branch                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ GitHub Actions Triggered                                             │
│ Workflow: .github/workflows/integration-tests.yml                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Python 3.11  │     │ Python 3.12  │     │ Fast Feedback│
│ Full Suite   │     │ Full Suite   │     │ Critical Only│
└──────────────┘     └──────────────┘     └──────────────┘
        │                     │                     │
        ├─ Install deps       ├─ Install deps      ├─ Install deps
        ├─ Run all tests      ├─ Run all tests     └─ Run INT-01, INT-02
        ├─ Random order       ├─ Random order
        ├─ Parallel (-n auto) ├─ Parallel (-n auto)
        ├─ Coverage report    └─ Coverage report
        └─ Upload to Codecov
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ All Pass?    │     │ Coverage OK? │     │ Time < 30s?  │
│ ✅ → Continue│     │ ✅ → Continue│     │ ✅ → Continue│
│ ❌ → Block   │     │ ❌ → Block   │     │ ⚠️  → Warn   │
└──────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ All Quality Gates Passed                                             │
│ ✅ Merge allowed                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Test Isolation Guarantees

```
┌─────────────────────────────────────────────────────────────────────┐
│ Test A                                                               │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Fresh Flask app created (function fixture)                       │
│ 2. Fresh test client created (function fixture)                     │
│  3. Mock activated with @responses.activate                          │
│ 4. Test runs                                                         │
│ 5. Mock automatically cleared                                        │
│ 6. Flask app discarded                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ No shared state
                              │
┌─────────────────────────────────────────────────────────────────────┐
│ Test B                                                               │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Fresh Flask app created (new instance)                           │
│ 2. Fresh test client created (new instance)                         │
│ 3. Different mock activated                                          │
│ 4. Test runs                                                         │
│ 5. Mock automatically cleared                                        │
│ 6. Flask app discarded                                               │
└─────────────────────────────────────────────────────────────────────┘

Result: Tests can run in any order, in parallel, 100% isolated
```

---

## Coverage Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ $ pytest tests/integration/ --cov=server --cov-report=html          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Coverage Collection (during test execution)                          │
├─────────────────────────────────────────────────────────────────────┤
│ • Track which lines in server/ are executed                         │
│ • Track which branches are taken                                    │
│ • Track which functions are called                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Coverage Report Generated                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Module              Lines    Covered    Missing    %        │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  server/routes.py      150       135        15      90%      │  │
│  │  server/validators.py  120       110        10      92%      │  │
│  │  server/anova_client   200       160        40      80%      │  │
│  │  server/middleware.py   80        70        10      88%      │  │
│  │  server/config.py       50        35        15      70%      │  │
│  │  server/exceptions.py   30        28         2      93%      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Overall Coverage: 85%  ✅ (Target: > 80%)                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HTML Report: htmlcov/index.html                                      │
│ • Line-by-line coverage visualization                                │
│ • Identify untested code paths                                       │
│ • Click through to see missing lines highlighted                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases Visual

```
Week 1                      Week 2                      Week 3                      Week 4
├────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤

Phase 1: Foundation     Phase 2: Happy Path     Phase 3: Edge Cases     Phase 6: Quality
├─ Mock infrastructure  ├─ INT-01              ├─ INT-06               ├─ Performance tests
├─ Core fixtures        ├─ INT-02              ├─ INT-07               ├─ Quality checks
└─ Validation           └─ API contracts       └─ INT-08               └─ CI/CD setup

                        Phase 3: Error Paths    Phase 4: State Trans    Phase 7: Production
                        ├─ INT-03              ├─ INT-ST-01 to 05      ├─ GitHub Actions
                        ├─ INT-04              └─ Validation           ├─ Documentation
                        └─ INT-05                                       └─ Team training

                                                Phase 5: Error Handling
                                                ├─ INT-ERR-01 to 04
                                                └─ Validation

Progress: [████░░░░░░░░░░░░░░░░] 20% (Foundation complete)
```

---

## Directory Structure

```
chef-gpt/
├── server/                         # Application code
│   ├── app.py                      # ← Tested
│   ├── routes.py                   # ← Tested
│   ├── validators.py               # ← Tested
│   ├── anova_client.py             # ← Tested (mocked)
│   ├── middleware.py               # ← Tested
│   ├── config.py                   # ← Tested
│   └── exceptions.py               # ← Tested
│
├── tests/
│   ├── conftest.py                 # Core fixtures
│   │
│   ├── mocks/                      # ✨ Mock infrastructure
│   │   ├── __init__.py
│   │   ├── anova_responses.py      # All mock data
│   │   └── anova_fixtures.py       # Composable fixtures
│   │
│   ├── integration/                # Integration tests
│   │   ├── test_int_happy_path.py
│   │   ├── test_int_error_paths.py
│   │   ├── test_int_edge_cases.py
│   │   ├── test_int_state_transitions.py
│   │   ├── test_int_api_contracts.py
│   │   ├── test_int_error_handling.py
│   │   └── test_int_performance.py
│   │
│   └── quality_checks.py           # Test quality validation
│
└── docs/
    ├── 09-integration-test-specification.md      # Test scenarios
    ├── 10-integration-test-automation-strategy.md # ✨ This strategy
    ├── TESTING-QUICK-REFERENCE.md                # ✨ Quick guide
    ├── TESTING-SUMMARY.md                        # ✨ Overview
    └── TESTING-ARCHITECTURE-DIAGRAM.md           # ✨ This file
```

---

## Key Concepts Visualization

### Fixture Reusability

```
                        ┌─────────────────┐
                        │  test_config    │ (session, reused)
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
            ┌───────▼──────┐ ┌──▼─────┐ ┌───▼────────────────┐
            │     app      │ │auth_   │ │ valid_cook_        │
            │   (fresh)    │ │headers │ │   requests         │
            └──────┬───────┘ └────────┘ └────────────────────┘
                   │            85%+ reuse across tests
            ┌──────▼───────┐
            │    client    │
            │   (fresh)    │
            └──────────────┘
                   │
        Used by all 24+ tests
```

### Mock Composability

```
Atomic Mocks (building blocks):
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ firebase_auth    │  │ device_status    │  │ start_cook       │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Composite Mocks     │
                    │  (complete scenarios)│
                    └──────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ api_success    │  │ api_offline    │  │ state_         │
│                │  │                │  │ progression    │
└────────────────┘  └────────────────┘  └────────────────┘
```

---

**Created:** 2026-01-11
**Purpose:** Visual reference for test infrastructure
