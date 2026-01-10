# Handoff Prompt: TDD Implementation (Post-Phase 4-6)

> **Purpose:** Start TDD implementation in a fresh conversation
> **Date:** 2026-01-10
> **Branch:** main (3 commits ahead of origin)
> **TDD Readiness:** 95% ✅
> **Next Phase:** Begin red-green-refactor implementation

---

## Context: Where We Are

You are beginning **TDD implementation** for the **Anova AI Sous Vide Assistant** project - a Flask API that bridges ChatGPT with an Anova Precision Cooker 3.0 for natural language sous vide control with food safety guardrails.

**Project Status:**
- ✅ **Phases 1-3 Complete:** Architecture analysis, specification refactoring, test specifications
- ✅ **Phases 4-6 Complete:** Food safety requirements, error catalog, traceability matrix, quality requirements enhancement
- ✅ **Verification Complete:** Code quality (100%), documentation consistency (95%), architecture integrity (100%), repository health (100%)
- ✅ **TDD Readiness:** 95% (exceeded 90% target)
- 🏗️ **Ready for Implementation:** All specifications in place, tests defined, stubs ready

**Current Commit:** `bfa56ff` - "Complete Phase 4-6: Comprehensive documentation foundation for TDD"

---

## Essential Reading (Do This First)

**CRITICAL - Read these files before starting:**

1. **Project Overview & Current Status:**
   ```bash
   Read README.md
   → Current status: 95% TDD readiness
   → Scaffolding complete (15 files, all valid)
   → Ready for red-green-refactor
   ```

2. **Implementation Patterns & Anti-Patterns:**
   ```bash
   Read CLAUDE.md
   → Code patterns (validation, error handling, auth, logging)
   → Food safety rules (critical constants)
   → Testing strategy (16 validator test cases specified)
   → Anti-patterns (what NOT to do)
   ```

3. **Component Specifications (Behavioral Contracts):**
   ```bash
   Read docs/03-component-architecture.md
   → Behavioral contracts for all 7 components
   → Preconditions/postconditions
   → Error contracts (what exceptions to raise)
   → Test oracles (links to test cases)
   ```

4. **Test Specifications:**
   ```bash
   Read tests/test_validators.py  # 16 test case stubs (TC-VAL-01 through TC-VAL-16)
   Read docs/09-integration-test-specification.md  # 25+ integration tests
   Read docs/13-test-traceability-matrix.md  # Requirements ↔ Tests mapping
   ```

5. **Food Safety Requirements (Critical):**
   ```bash
   Read docs/06-food-safety-requirements.md
   → Minimum safe temperatures by food type
   → Absolute limits (40°C-100°C)
   → Traceability to FR-07, FR-08
   ```

---

## Project Architecture Quick Reference

### Layered Architecture
```
API Layer (routes.py, middleware.py, app.py)
    ↓
Service Layer (validators.py)
    ↓
Integration Layer (anova_client.py)
    ↓
Infrastructure Layer (config.py, exceptions.py)
```

### Component Dependency Graph
```
exceptions.py (base, no deps)
    ↓
config.py, validators.py, middleware.py (depend on exceptions)
    ↓
anova_client.py (depends on config, exceptions)
    ↓
routes.py (depends on validators, anova_client, middleware)
    ↓
app.py (depends on routes, middleware, config)
```

**Critical:** No circular dependencies. All dependencies flow downward.

### File Structure
```
chef-gpt/
├── server/                    # Flask application
│   ├── exceptions.py          # ✅ COMPLETE (167 lines, 7 exception classes)
│   ├── validators.py          # 🏗️ STUB - START HERE (food safety validation)
│   ├── anova_client.py        # 🏗️ STUB (Anova Cloud API client)
│   ├── routes.py              # 🏗️ STUB (4 HTTP endpoints)
│   ├── middleware.py          # 🏗️ STUB (auth, logging, error handling)
│   ├── config.py              # 🏗️ STUB (environment config)
│   └── app.py                 # 🏗️ STUB (application factory)
├── tests/
│   ├── test_validators.py     # 🏗️ 16 test stubs (TC-VAL-01 to TC-VAL-16)
│   ├── test_routes.py         # 🏗️ Integration test stubs
│   └── test_anova_client.py   # 🏗️ Client test stubs
├── docs/
│   ├── 01-system-context.md             # Requirements (FR-XX, QR-XX, SEC-REQ-XX)
│   ├── 03-component-architecture.md     # Behavioral contracts
│   ├── 06-food-safety-requirements.md   # NEW (Phase 4) - Safety specs
│   ├── 10-error-catalog.md              # NEW (Phase 4) - 16 error codes
│   ├── 13-test-traceability-matrix.md   # NEW (Phase 5) - Req ↔ Test mapping
│   └── COMPONENT-IMPLEMENTATIONS.md     # Reference implementations
├── CLAUDE.md                  # Implementation guide (patterns, rules)
└── README.md                  # Current status
```

---

## TDD Implementation Plan

### Phase 1: Validator Implementation (Week 1)

**Priority:** HIGHEST - Start here
**Component:** `server/validators.py`
**Tests:** `tests/test_validators.py` (TC-VAL-01 through TC-VAL-16)

#### Step-by-Step TDD Process

**1. Read Specifications First:**
```bash
# Read behavioral contract
Read docs/03-component-architecture.md Section 4.2.1

# Read test specifications
Read tests/test_validators.py (16 test case stubs)

# Read food safety requirements
Read docs/06-food-safety-requirements.md
```

**2. Implement Tests (Red Phase):**
```bash
# Open tests/test_validators.py
# Pick ONE test (e.g., TC-VAL-01: Valid parameters)
# Write full test implementation
# Run: pytest tests/test_validators.py::test_valid_parameters
# Expected: FAIL (function not implemented yet)
```

**3. Implement Code (Green Phase):**
```bash
# Open server/validators.py
# Implement JUST ENOUGH code to make test pass
# Run: pytest tests/test_validators.py::test_valid_parameters
# Expected: PASS
```

**4. Refactor (Clean Phase):**
```bash
# Improve code quality
# Extract constants
# Add type hints
# Improve error messages
# Run: pytest tests/test_validators.py::test_valid_parameters
# Expected: STILL PASS
```

**5. Repeat for All 16 Tests:**
```bash
# TC-VAL-01: Valid parameters
# TC-VAL-02: Temperature too low (< 40°C)
# TC-VAL-03: Temperature too high (> 100°C)
# TC-VAL-04: Temperature exactly minimum (40.0°C)
# TC-VAL-05: Temperature exactly maximum (100.0°C)
# TC-VAL-06: Time zero
# TC-VAL-07: Time negative
# TC-VAL-08: Time exactly maximum (5999 min)
# TC-VAL-09: Time above maximum (> 5999 min)
# TC-VAL-10: Chicken at 56°C (unsafe)
# TC-VAL-11: Chicken at 57°C (safe)
# TC-VAL-12: Ground beef at 59°C (unsafe)
# TC-VAL-13: Ground beef at 60°C (safe)
# TC-VAL-14: Float time truncation
# TC-VAL-15: Missing temperature
# TC-VAL-16: Missing time
```

#### Food Safety Constants (Critical)

**Define these constants in `server/validators.py`:**
```python
# Absolute limits
MIN_TEMP_CELSIUS = 40.0
MAX_TEMP_CELSIUS = 100.0

# Food-specific minimums
POULTRY_MIN_TEMP = 57.0      # With extended time (3+ hours)
POULTRY_SAFE_TEMP = 65.0     # Standard safe temperature
GROUND_MEAT_MIN_TEMP = 60.0  # Higher due to bacteria mixed throughout

# Time limits
MIN_TIME_MINUTES = 1
MAX_TIME_MINUTES = 5999  # Device firmware limit
```

**Source of Truth:**
- CLAUDE.md "Food Safety Rules" section
- docs/06-food-safety-requirements.md
- docs/01-system-context.md (FR-04, FR-05, FR-07, FR-08)

**CRITICAL:** These values are verified consistent across 5 documents. Do not change them.

#### Error Codes to Use

**From `server/exceptions.py` (already complete):**
```python
from server.exceptions import ValidationError

# Raise these error codes:
ValidationError("MISSING_TEMPERATURE", "temperature_celsius is required")
ValidationError("MISSING_TIME", "time_minutes is required")
ValidationError("INVALID_TEMPERATURE", "temperature_celsius must be a number")
ValidationError("INVALID_TIME", "time_minutes must be an integer")
ValidationError("TEMPERATURE_TOO_LOW", "Temperature X°C is below safe minimum...")
ValidationError("TEMPERATURE_TOO_HIGH", "Temperature X°C exceeds safe maximum...")
ValidationError("TIME_TOO_SHORT", "Time must be at least 1 minute")
ValidationError("TIME_TOO_LONG", "Time exceeds device maximum...")
ValidationError("POULTRY_TEMP_UNSAFE", "Temperature X°C is not safe for poultry...")
ValidationError("GROUND_MEAT_TEMP_UNSAFE", "Temperature X°C is not safe for ground meat...")
```

**Complete list:** See docs/10-error-catalog.md (16 error codes documented)

---

### Phase 2: Middleware Implementation (Week 1-2)

**Component:** `server/middleware.py`
**Tests:** `tests/test_routes.py` (authentication tests)

**Key Responsibilities:**
1. API key authentication (constant-time comparison)
2. Request/response logging (no secrets)
3. Error handling (map exceptions to HTTP status)

**Pattern Reference:** CLAUDE.md Section "3. Authentication Pattern"

---

### Phase 3: Anova Client Implementation (Week 2)

**Component:** `server/anova_client.py`
**Tests:** `tests/test_anova_client.py`

**Key Responsibilities:**
1. Firebase authentication
2. Token refresh management
3. Device command execution (start, stop, status)
4. Error handling (device offline, API errors)

**Pattern Reference:** docs/COMPONENT-IMPLEMENTATIONS.md "Implementation: anova_client.py (COMP-ANOVA-01)"

---

### Phase 4: Routes & App Factory (Week 2-3)

**Components:** `server/routes.py`, `server/app.py`
**Tests:** `tests/test_routes.py` (integration tests)

**Key Responsibilities:**
1. HTTP endpoint handlers (4 routes)
2. Input validation orchestration
3. Error response formatting
4. Application factory pattern

**Pattern Reference:** docs/09-integration-test-specification.md

---

## Critical Constraints & Rules

### 1. Food Safety is Paramount
**Non-negotiable validation rules:**
- Server-side validation ALWAYS enforced (never trust client)
- All temperatures validated against absolute limits (40-100°C)
- Food-specific rules enforced (poultry ≥57°C, ground meat ≥60°C)
- Error messages are educational (explain WHY validation failed)

### 2. Security Best Practices
**From docs/11-security-test-specification.md:**
- NEVER log credentials, tokens, or API keys
- Use constant-time comparison for auth (prevent timing attacks)
- API key required for all endpoints except `/health`
- No secrets in code (use environment variables)

### 3. Error Handling Pattern
**From CLAUDE.md:**
- All errors flow through custom exceptions (`AnovaServerError` base)
- ValidationError → HTTP 400
- AnovaAPIError → HTTP 500/503
- DeviceOfflineError → HTTP 503
- Never let raw exceptions reach client

### 4. Testing Strategy
**From docs/13-test-traceability-matrix.md:**
- Write tests from specifications (not from code)
- Test behavior, not implementation details
- Mock external dependencies (no real Anova API calls)
- Fast feedback (full test suite < 30 seconds)

### 5. Code Quality
**From CLAUDE.md "Anti-Patterns":**
- ❌ Never log secrets (passwords, tokens, API keys)
- ❌ Never trust input without validation
- ❌ Never bypass server-side safety checks
- ❌ Never hardcode credentials
- ✅ Always validate first
- ✅ Always use type hints
- ✅ Always write docstrings

---

## Commands for TDD Workflow

### Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt
```

### Testing Commands
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validators.py

# Run specific test
pytest tests/test_validators.py::test_temperature_too_low

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=server --cov-report=html

# Run and stop on first failure
pytest -x

# Run tests matching pattern
pytest -k "temperature"
```

### Code Quality Commands
```bash
# Syntax check
python -m py_compile server/*.py tests/*.py

# Import validation
python -c "from server.exceptions import ValidationError"

# Type checking (optional)
mypy server/

# Linting (optional)
ruff check server/
```

---

## Success Criteria

### Validator Implementation Complete When:
- [ ] All 16 test cases pass (`pytest tests/test_validators.py`)
- [ ] Coverage ≥ 90% for validators.py
- [ ] All food safety constants defined
- [ ] All error codes used correctly
- [ ] Type hints on all functions
- [ ] Docstrings on all functions
- [ ] No hardcoded magic numbers

### Overall Phase 1 Complete When:
- [ ] validators.py fully implemented
- [ ] All 16 tests passing
- [ ] Integration tests passing (routes calling validators)
- [ ] No code smells (ruff check passes)
- [ ] Documentation updated (if needed)
- [ ] Git commit with comprehensive message

---

## Common Pitfalls to Avoid

### 1. Testing Anti-Patterns
**❌ Don't:**
- Test implementation details (how code works)
- Look at code before writing tests
- Write tests after code
- Copy implementation into tests

**✅ Do:**
- Test behavior (what code does)
- Read specifications first
- Write tests before code (red-green-refactor)
- Test against requirements

### 2. Validation Anti-Patterns
**❌ Don't:**
- Skip validation because "GPT won't send bad data"
- Trust client-provided data
- Validate only on happy path
- Return generic error messages

**✅ Do:**
- Validate ALL inputs server-side
- Assume all input is malicious
- Test edge cases and boundary conditions
- Provide actionable error messages

### 3. Food Safety Anti-Patterns
**❌ Don't:**
- Change safety constants without verification
- Allow temperature override
- Bypass food-specific rules
- Use vague temperature ranges

**✅ Do:**
- Use exact constants from specs
- Enforce non-negotiable limits
- Apply food-specific validation
- Explain safety reasoning in errors

---

## Quick Reference: Key Files

### Specifications (Read for Requirements)
- `docs/03-component-architecture.md` - Behavioral contracts
- `docs/06-food-safety-requirements.md` - Safety rules
- `docs/10-error-catalog.md` - Error codes and messages
- `docs/13-test-traceability-matrix.md` - Requirements ↔ Tests

### Implementation Guides (Read for Patterns)
- `CLAUDE.md` - Patterns, anti-patterns, food safety rules
- `docs/COMPONENT-IMPLEMENTATIONS.md` - Reference implementations

### Test Specifications (Read for Test Cases)
- `tests/test_validators.py` - 16 unit test stubs
- `docs/09-integration-test-specification.md` - 25+ integration tests
- `docs/11-security-test-specification.md` - 24 security tests

### Implementation Files (Write Code Here)
- `server/exceptions.py` - ✅ COMPLETE (do not modify)
- `server/validators.py` - 🏗️ START HERE
- `server/middleware.py` - 🏗️ Phase 2
- `server/anova_client.py` - 🏗️ Phase 3
- `server/routes.py` - 🏗️ Phase 4
- `server/app.py` - 🏗️ Phase 4

---

## Starting Prompt for New Conversation

Use this to begin TDD implementation:

```
I'm starting TDD implementation for the Anova AI Sous Vide Assistant project
(Phases 4-6 complete, 95% TDD ready). I've read the handoff context.

Before proceeding, let me:
1. Read CLAUDE.md to understand implementation patterns
2. Read docs/03-component-architecture.md Section 4.2.1 (validators contract)
3. Read tests/test_validators.py to understand test expectations
4. Read docs/06-food-safety-requirements.md for safety constants

Then I'll begin red-green-refactor starting with TC-VAL-01 (valid parameters).

My approach:
1. Write test first (red)
2. Implement minimal code to pass (green)
3. Refactor for quality (clean)
4. Repeat for all 16 validator tests

I'll follow TDD strictly: no implementation before tests, test behavior not
implementation, use specifications as source of truth.

Ready to start with TC-VAL-01?
```

---

## Additional Context

### Project Background
- **Purpose:** Gift for non-technical user to control sous vide via ChatGPT
- **Constraint:** Zero recurring costs (self-hosted on Raspberry Pi Zero 2 W)
- **Critical:** Food safety validation must be server-side (non-bypassable)

### Tech Stack
- Python 3.11+
- Flask 3.0.* (web framework)
- pytest 7.* (testing)
- responses 0.24.* (HTTP mocking)
- gunicorn 21.* (production WSGI server)

### Deployment Target
- Raspberry Pi Zero 2 W
- Cloudflare Tunnel (HTTPS without port forwarding)
- systemd service management
- Zero recurring costs

---

## Git Workflow

### Before Starting
```bash
git status  # Verify working tree is clean
git log --oneline -3  # See recent commits
```

### During Implementation
```bash
# Commit after each completed feature
git add server/validators.py tests/test_validators.py
git commit -m "Implement validators.py with TDD (TC-VAL-01 through TC-VAL-16)

- Implement validate_start_cook() function
- Add food safety constants
- All 16 test cases passing
- Coverage: 95%
- Follows behavioral contract from docs/03

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Commit Message Template
```
<Type>: <Brief description>

<Detailed description>
- <What was implemented>
- <What tests were added>
- <Any important decisions>

<Metrics>
- Tests passing: X/X
- Coverage: X%
- Follows: <Specification reference>

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Helpful Agent Commands

### During Implementation
- Use `test-automator` agent when creating complex test scenarios
- Use `debugging-toolkit:debugger` agent when tests fail unexpectedly
- Use `python-development:python-pro` agent for advanced Python patterns
- Use `code-documentation:code-reviewer` agent before committing

---

## Summary

**You are starting TDD implementation after successful completion of Phases 4-6.**

**Key Achievements So Far:**
- ✅ 95% TDD readiness (exceeded 90% target)
- ✅ Complete specifications (behavioral contracts for all components)
- ✅ Comprehensive test specifications (65+ test cases defined)
- ✅ Food safety requirements documented
- ✅ Error catalog complete (16 error codes)
- ✅ Requirements traceability matrix (bidirectional mapping)
- ✅ All code syntactically valid

**What You Need to Do:**
1. Start with `server/validators.py` (highest priority)
2. Follow strict TDD (red-green-refactor)
3. Use specifications as source of truth
4. Implement all 16 validator test cases
5. Maintain food safety as paramount concern

**Expected Timeline:**
- Week 1: validators.py complete (16 tests passing)
- Week 2: middleware.py + anova_client.py (integration tests passing)
- Week 3: routes.py + app.py (full API functional)
- Week 4+: Polish, performance tests, deployment

**Success Indicator:** When you run `pytest tests/test_validators.py -v` and see 16 passing tests with descriptive output, Phase 1 of TDD implementation is complete.

🚀 **Ready to begin red-green-refactor cycle!**
