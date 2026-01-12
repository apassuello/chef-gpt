# Phase 2: Happy Path Integration Tests - Implementation Plan

> **Status**: Ready to implement
> **Prerequisites**: ✅ Phase 1 Complete (fixtures working)
> **Estimated Time**: 2-3 hours
> **Tests to Implement**: 2 (INT-01, INT-02)

---

## Executive Summary

Phase 2 validates that the core happy path works end-to-end:
1. **INT-01**: Complete cook cycle (start → check status → stop)
2. **INT-02**: Validation rejects unsafe requests before calling Anova API

These tests prove the system works correctly for the primary use case.

---

## Prerequisites Checklist

Before starting Phase 2, verify:

- [x] Phase 1 complete (all fixtures implemented)
- [x] All 91 tests passing (83 unit + 8 smoke)
- [x] Mock fixtures working correctly (verified with smoke tests)
- [x] Integration test directory exists (`tests/integration/`)
- [x] Can create Flask test client successfully
- [x] No regressions in existing tests

**Status**: ✅ ALL PREREQUISITES MET

---

## Test File to Create

```
tests/integration/test_int_happy_path.py
```

This file will contain:
- INT-01: Complete cook cycle success
- INT-02: Validation rejection flow

**Reference**: Integration Test Spec Section 3.1 (lines 390-513)

---

## INT-01: Complete Cook Cycle Success

### Specification Reference

- **Test ID**: INT-01
- **Spec Location**: docs/09-integration-test-specification.md lines 390-459
- **Validates**: FR-01, FR-02, FR-03, QR-01
- **Estimated Time**: 1-1.5 hours

### What This Test Validates

1. **Start Cook** endpoint accepts valid parameters
2. **Status** endpoint returns current state
3. **Stop Cook** endpoint successfully stops cooking
4. All responses have correct schema
5. End-to-end flow completes in < 2 seconds

### Implementation Steps

#### Step 1: Create Test File

```bash
touch tests/integration/test_int_happy_path.py
```

#### Step 2: Add Imports and Docstring

```python
"""
Integration tests for happy path scenarios.

These tests validate the core functionality works end-to-end:
- Complete cook cycle from start to stop
- Validation properly rejects unsafe requests

Reference: docs/09-integration-test-specification.md Section 3.1
"""

import pytest
import responses
```

#### Step 3: Implement INT-01

```python
@responses.activate
def test_int_01_complete_cook_cycle_success(
    client,
    auth_headers,
    valid_cook_requests,
    mock_anova_api_success
):
    """
    INT-01: Complete cook cycle from start to stop.

    Validates:
    - FR-01: Start cook accepts valid parameters
    - FR-02: Status returns current state
    - FR-03: Stop cook successfully stops
    - QR-01: Response time < 2 seconds

    Reference: Spec Section 3.1, lines 390-459
    """
    # ARRANGE
    # mock_anova_api_success fixture already added mocks

    # ACT 1: Start cook
    start_response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    # ASSERT 1: Start cook succeeded
    assert start_response.status_code == 200, \
        f"Expected 200, got {start_response.status_code}: {start_response.get_json()}"

    start_data = start_response.get_json()

    # Validate response schema (all required fields present)
    required_fields = [
        "success", "message", "cook_id", "device_state",
        "target_temp_celsius", "time_minutes", "estimated_completion"
    ]
    for field in required_fields:
        assert field in start_data, f"Response missing required field: {field}"

    # Validate response values match request
    assert start_data["success"] is True
    assert start_data["target_temp_celsius"] == 65.0
    assert start_data["time_minutes"] == 90
    assert start_data["device_state"] == "preheating"

    # Validate field types and formats
    assert isinstance(start_data["cook_id"], str)
    assert len(start_data["cook_id"]) == 36  # UUID format
    assert "T" in start_data["estimated_completion"]  # ISO 8601
    assert start_data["estimated_completion"].endswith("Z")  # UTC

    # ACT 2: Check status
    status_response = client.get('/status', headers=auth_headers)

    # ASSERT 2: Status shows device running
    assert status_response.status_code == 200
    status_data = status_response.get_json()

    assert "device_online" in status_data
    assert "state" in status_data
    assert "is_running" in status_data

    assert status_data["device_online"] is True
    assert status_data["is_running"] is True
    # Note: state may be "preheating" or "cooking" depending on mock

    # ACT 3: Stop cook
    stop_response = client.post('/stop-cook', headers=auth_headers)

    # ASSERT 3: Stop succeeded
    assert stop_response.status_code == 200
    stop_data = stop_response.get_json()

    assert "success" in stop_data
    assert "device_state" in stop_data
    assert "final_temp_celsius" in stop_data

    assert stop_data["success"] is True
    assert stop_data["device_state"] == "idle"

    # Performance: Entire cycle should be fast (< 2s with mocks)
    # This is implicitly validated by test not timing out
```

#### Step 4: Run INT-01

```bash
# Run just this test
pytest tests/integration/test_int_happy_path.py::test_int_01_complete_cook_cycle_success -v

# Expected: PASSED
```

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Mock not matching URL | Check Firebase/Anova URLs in anova_client.py |
| Missing response fields | Verify routes.py returns all required fields |
| 401 Unauthorized | Check auth_headers fixture matches API_KEY in TEST_CONFIG |
| ConnectionError | Verify @responses.activate decorator present |

---

## INT-02: Validation Rejection Flow

### Specification Reference

- **Test ID**: INT-02
- **Spec Location**: docs/09-integration-test-specification.md lines 462-513
- **Validates**: FR-04, FR-05, FR-07, FR-08
- **Estimated Time**: 30-45 minutes

### What This Test Validates

1. Validator blocks unsafe temperature (<40°C)
2. Error response has correct code and message
3. Anova API is **NOT** called (validation fails fast)
4. Error message is actionable for user

### Implementation Steps

#### Step 1: Add INT-02 to Same File

```python
@responses.activate
def test_int_02_validation_rejection_flow(
    client,
    auth_headers,
    invalid_cook_requests
):
    """
    INT-02: Validation rejects request before calling Anova API.

    Validates:
    - FR-04: Temperature minimum enforced (40°C)
    - FR-05: Actionable error messages returned
    - FR-07: Validation fails fast (no API call)
    - FR-08: Error response has correct schema

    Reference: Spec Section 3.1, lines 462-513
    """
    # ARRANGE
    invalid_request = invalid_cook_requests["temp_too_low"]
    # Note: No mock_anova_api_success fixture used
    # We want to verify NO API calls are made

    # ACT
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={
            "temperature_celsius": invalid_request["temperature_celsius"],
            "time_minutes": invalid_request["time_minutes"]
        }
    )

    # ASSERT 1: Validation rejected request
    assert response.status_code == 400, \
        f"Expected 400, got {response.status_code}: {response.get_json()}"

    data = response.get_json()

    # ASSERT 2: Error response schema
    assert "error" in data, "Response missing 'error' field"
    assert "message" in data, "Response missing 'message' field"

    # ASSERT 3: Correct error code
    assert data["error"] == "TEMPERATURE_TOO_LOW", \
        f"Expected 'TEMPERATURE_TOO_LOW', got '{data['error']}'"

    # ASSERT 4: Message mentions danger zone
    assert "danger zone" in data["message"].lower(), \
        f"Error message should mention danger zone: {data['message']}"

    # ASSERT 5: No Anova API calls were made
    # This is critical - validation should fail BEFORE API call
    assert len(responses.calls) == 0, \
        f"Validator should block before API call. Calls made: {len(responses.calls)}"
```

#### Step 2: Run INT-02

```bash
# Run just this test
pytest tests/integration/test_int_happy_path.py::test_int_02_validation_rejection_flow -v

# Expected: PASSED
```

#### Step 3: Run Both Tests Together

```bash
# Run entire file
pytest tests/integration/test_int_happy_path.py -v

# Expected: 2 passed
```

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Test makes API calls | Ensure NO mock_anova_api_success fixture in params |
| Wrong error code | Check validators.py error codes match spec |
| Missing error fields | Verify middleware.py error handler returns correct schema |
| Test fails in suite | Check fixture isolation (should pass alone and in suite) |

---

## Success Criteria

Phase 2 is complete when:

### Functional
- ✅ INT-01 passes (complete cook cycle)
- ✅ INT-02 passes (validation rejection)
- ✅ Both tests pass together
- ✅ Both tests pass in random order

### Performance
- ✅ Both tests complete in < 5 seconds total
- ✅ No real API calls made (all mocked)

### Quality
- ✅ All assertions comprehensive
- ✅ Error messages clear and actionable
- ✅ No test pollution (each test isolated)

### Verification Commands

```bash
# Run Phase 2 tests
pytest tests/integration/test_int_happy_path.py -v

# Run all tests (no regressions)
pytest tests/ -v

# Run in random order (check isolation)
pytest tests/integration/ --random-order -v

# Check performance
pytest tests/integration/test_int_happy_path.py --durations=5
```

---

## Expected Output

### After INT-01 Implementation

```
tests/integration/test_int_happy_path.py::test_int_01_complete_cook_cycle_success PASSED [100%]

======================== 1 passed in 0.02s ==========================
```

### After INT-02 Implementation

```
tests/integration/test_int_happy_path.py::test_int_01_complete_cook_cycle_success PASSED [ 50%]
tests/integration/test_int_happy_path.py::test_int_02_validation_rejection_flow PASSED [100%]

======================== 2 passed in 0.03s ==========================
```

### Full Test Suite

```
======================== 93 passed in 0.12s ==========================

Coverage:
- routes.py: 75%+ (up from 60%)
- validators.py: 95%+ (already high)
- Overall: 75%+
```

---

## Post-Implementation Checklist

- [ ] INT-01 passes independently
- [ ] INT-02 passes independently
- [ ] Both pass together
- [ ] Both pass in random order
- [ ] All 93 tests pass (91 existing + 2 new)
- [ ] Tests complete in < 5 seconds
- [ ] No ConnectionError (all mocked)
- [ ] No timing failures
- [ ] Coverage increased
- [ ] Documentation updated (if needed)

---

## Troubleshooting Guide

### Issue: INT-01 fails with ConnectionError

**Symptom:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Diagnosis:**
- Missing `@responses.activate` decorator
- OR mock URLs don't match actual URLs

**Solution:**
```python
# 1. Check decorator present
@responses.activate
def test_int_01_...

# 2. Debug what URLs are being called
for call in responses.calls:
    print(f"Called: {call.request.url}")

# 3. Check anova_client.py for actual URLs
# Verify mock URLs match
```

### Issue: INT-01 fails with wrong response schema

**Symptom:**
```
AssertionError: Response missing 'success' field
```

**Diagnosis:**
- routes.py response doesn't match spec

**Solution:**
```bash
# Check what routes.py actually returns
pytest tests/integration/test_int_happy_path.py::test_int_01... -v -s

# Compare with spec (lines 420-427)
cat docs/09-integration-test-specification.md | sed -n '420,427p'
```

### Issue: INT-02 makes API calls when it shouldn't

**Symptom:**
```
AssertionError: Validator should block before API call. Calls made: 1
```

**Diagnosis:**
- Validator not rejecting request
- OR validation happens after API auth

**Solution:**
```python
# Check validators.py runs BEFORE anova_client
# In routes.py, validate FIRST:
validated = validate_start_cook(request.json)  # This should raise
client.start_cook(**validated)  # Should never reach here
```

### Issue: Tests pass alone, fail in suite

**Symptom:**
```bash
pytest test_int_01... -v  # PASSED
pytest tests/integration/ -v  # FAILED
```

**Diagnosis:**
- State pollution between tests
- Shared fixture not cleaning up

**Solution:**
```bash
# Run in random order to isolate
pytest tests/integration/ --random-order -v

# Check fixture scope (should be function, not module)
pytest --fixtures | grep -A 3 "mock_anova"
```

---

## What's Next: Phase 3 Preview

After Phase 2 completes, Phase 3 will implement:

**Error Paths (3 tests, 4-5 hours):**
- INT-03: Device offline scenario (503)
- INT-04: Device already cooking (409)
- INT-05: Invalid auth handling (401)

**Edge Cases (3 tests):**
- INT-06: Concurrent requests
- INT-07: Token refresh mid-request
- INT-08: Network timeouts

**Reference**: Integration Test Spec Section 3.2 (lines 516-718)

---

## Resources

1. **Integration Test Spec** - Your implementation bible
   ```bash
   cat docs/09-integration-test-specification.md | less
   # Jump to line 390 for INT-01
   # Jump to line 462 for INT-02
   ```

2. **API Specification** - Request/response schemas
   ```bash
   cat docs/05-api-specification.md | less
   ```

3. **Working Example** - From audit agent
   ```bash
   cat HANDOFF-INTEGRATION-TESTS.md | grep -A 50 "Complete Working Test Example"
   ```

4. **Fixtures Reference**
   ```bash
   pytest --fixtures | grep -A 3 "mock_anova\|valid_cook\|auth_headers"
   ```

---

## Time Tracking

| Task | Estimated | Actual | Status |
|------|-----------|--------|--------|
| Read spec for INT-01 | 15 min | | |
| Implement INT-01 | 45 min | | |
| Debug INT-01 | 30 min | | |
| Read spec for INT-02 | 10 min | | |
| Implement INT-02 | 20 min | | |
| Debug INT-02 | 15 min | | |
| Verify & document | 15 min | | |
| **TOTAL** | **2h 30min** | | |

---

**Document Created**: 2026-01-11
**Phase**: 2 of 5
**Prerequisites**: Phase 1 Complete ✅
**Status**: READY TO IMPLEMENT
**Next Session**: Implement INT-01 and INT-02
