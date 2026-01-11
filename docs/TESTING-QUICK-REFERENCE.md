# Integration Testing Quick Reference

> **Quick access patterns for daily test development**
> **Full details:** See `10-integration-test-automation-strategy.md`

---

## Quick Commands

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test
pytest tests/integration/test_int_happy_path.py::test_int_01_complete_cook_cycle -v

# Run tests matching pattern
pytest tests/integration/ -k "auth" -v

# Run with coverage
pytest tests/integration/ --cov=server --cov-report=html

# Run in parallel (fast)
pytest tests/integration/ -n auto

# Run in random order (verify isolation)
pytest tests/integration/ --random-order

# Show slowest tests
pytest tests/integration/ --durations=10

# Stop on first failure
pytest tests/integration/ -x

# Verbose with stdout
pytest tests/integration/ -v -s
```

---

## Common Test Patterns

### 1. Simple Happy Path Test

```python
def test_endpoint_success(client, auth_headers, valid_cook_requests, mock_anova_api_success):
    """Test successful operation."""
    mock_anova_api_success()

    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
```

### 2. Validation Error Test

```python
def test_validation_error(client, auth_headers):
    """Test validation rejects invalid input."""
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json={"temperature_celsius": 35.0, "time_minutes": 60}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "TEMPERATURE_TOO_LOW"
    assert "danger zone" in data["message"].lower()
```

### 3. Parameterized Test (Multiple Scenarios)

```python
@pytest.mark.parametrize("request_data,expected_error", [
    ({"temperature_celsius": 35.0, "time_minutes": 60}, "TEMPERATURE_TOO_LOW"),
    ({"temperature_celsius": 105.0, "time_minutes": 60}, "TEMPERATURE_TOO_HIGH"),
    ({"temperature_celsius": 56.0, "time_minutes": 90, "food_type": "chicken"}, "POULTRY_TEMP_UNSAFE"),
])
def test_validation_errors(client, auth_headers, request_data, expected_error):
    """Test multiple validation scenarios."""
    response = client.post('/start-cook', headers=auth_headers, json=request_data)
    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error
```

### 4. Custom Mock Scenario

```python
def test_custom_scenario(client, auth_headers):
    """Test specific mock sequence."""
    with responses.RequestsMock() as rsps:
        # Mock Firebase auth
        rsps.add(
            responses.POST,
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            json={"idToken": "token", "refreshToken": "refresh", "expiresIn": "3600"},
            status=200
        )

        # Mock device offline
        rsps.add(
            responses.GET,
            "https://anovaculinary.io/api/v1/devices/test-device-123/status",
            json={"error": "Device offline"},
            status=404
        )

        # Test
        response = client.post(
            '/start-cook',
            headers=auth_headers,
            json={"temperature_celsius": 65.0, "time_minutes": 90}
        )

        assert response.status_code == 503
```

### 5. State Transition Test

```python
def test_state_transition(client, auth_headers):
    """Test state changes over time."""
    with responses.RequestsMock() as rsps:
        # First status: idle
        rsps.add(responses.GET, "...url.../status", json={"state": "idle"})

        # Start cook
        rsps.add(responses.POST, "...url.../start", json={"success": True})

        # Second status: cooking
        rsps.add(responses.GET, "...url.../status", json={"state": "cooking"})

        # Verify progression
        response1 = client.get('/status', headers=auth_headers)
        assert response1.get_json()["state"] == "idle"

        client.post('/start-cook', headers=auth_headers, json={...})

        response2 = client.get('/status', headers=auth_headers)
        assert response2.get_json()["state"] == "cooking"
```

---

## Available Fixtures

### Core Fixtures (Always Available)

```python
def test_example(client, auth_headers, valid_cook_requests):
    # client: Flask test client
    # auth_headers: {"Authorization": "Bearer test-api-key-12345"}
    # valid_cook_requests: Dict of valid cook requests
    pass
```

### Mock Fixtures

```python
def test_with_mock(client, auth_headers, mock_anova_api_success):
    mock_anova_api_success()  # Activate mock
    # Test code here
```

Available mock fixtures:
- `mock_anova_api_success` - Complete happy path
- `mock_anova_api_offline` - Device offline
- `mock_anova_api_busy` - Device already cooking

### Test Data Fixtures

```python
# valid_cook_requests["chicken"] - Safe chicken cook
# valid_cook_requests["steak"] - Steak cook
# valid_cook_requests["edge_min_temp"] - 40°C boundary
# valid_cook_requests["edge_max_temp"] - 100°C boundary

# invalid_cook_requests["temp_too_low"] - Below 40°C
# invalid_cook_requests["unsafe_poultry"] - Chicken below 57°C
```

---

## Writing a New Test

### Step 1: Choose Test File

```
tests/integration/
├── test_int_happy_path.py       # Happy path scenarios
├── test_int_error_paths.py      # Error scenarios (offline, busy)
├── test_int_edge_cases.py       # Edge cases (token refresh, concurrent)
├── test_int_state_transitions.py # State machine tests
├── test_int_api_contracts.py    # API schema validation
└── test_int_error_handling.py   # Error propagation tests
```

### Step 2: Write Test

```python
def test_int_XX_scenario_description(client, auth_headers, relevant_fixtures):
    """
    INT-XX: Brief scenario description.

    Validates:
    - FR-XX: Functional requirement
    - QR-XX: Quality requirement

    Steps:
    1. Setup
    2. Action
    3. Verify
    """
    # Arrange
    mock_fixture()

    # Act
    response = client.post('/endpoint', headers=auth_headers, json={...})

    # Assert
    assert response.status_code == 200
    assert response.get_json()["field"] == expected_value
```

### Step 3: Run Test

```bash
# Run new test
pytest tests/integration/test_file.py::test_int_XX_scenario -v

# Verify isolation (run 10 times)
for i in {1..10}; do pytest tests/integration/test_file.py::test_int_XX_scenario || break; done

# Run in full suite
pytest tests/integration/ -v
```

---

## Debugging Failed Tests

### 1. See Full Output

```bash
pytest tests/integration/test_failing.py -v -s
```

### 2. See Full Traceback

```bash
pytest tests/integration/test_failing.py -v --tb=long
```

### 3. Drop into Debugger on Failure

```bash
pytest tests/integration/test_failing.py --pdb
```

### 4. Print Request/Response

```python
def test_debug(client, auth_headers):
    response = client.post('/endpoint', headers=auth_headers, json={...})

    print(f"Status: {response.status_code}")
    print(f"Response: {response.get_json()}")

    assert response.status_code == 200
```

### 5. Check Mock Calls

```python
def test_verify_mock_called(client, auth_headers):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, "https://api.com/endpoint", json={"ok": True})

        response = client.post('/endpoint', headers=auth_headers, json={...})

        # Debug: Was mock called?
        print(f"Mock calls: {len(rsps.calls)}")
        for call in rsps.calls:
            print(f"  {call.request.method} {call.request.url}")

        assert len(rsps.calls) == 1  # Verify expected calls
```

---

## Common Errors & Fixes

### Error: "ConnectionError: Connection refused"

**Cause:** Test is trying to call real Anova API (mock not active).

**Fix:**
```python
# Ensure mock is activated
def test_example(client, auth_headers, mock_anova_api_success):
    mock_anova_api_success()  # <-- Add this line
    response = client.post(...)
```

### Error: "AssertionError: 401 != 200"

**Cause:** Missing or invalid authentication.

**Fix:**
```python
# Ensure auth_headers fixture is used
def test_example(client, auth_headers):  # <-- Add auth_headers
    response = client.post('/endpoint', headers=auth_headers, json={...})
```

### Error: "KeyError: 'temperature_celsius'"

**Cause:** Request data missing required field.

**Fix:**
```python
# Use valid_cook_requests fixture
def test_example(client, auth_headers, valid_cook_requests):
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]  # <-- Complete valid data
    )
```

### Error: Test passes alone, fails in suite

**Cause:** Test isolation issue (shared state).

**Fix:**
1. Use function-scoped fixtures (default)
2. Ensure `@responses.activate` decorator is used
3. Don't modify global variables
4. Verify with: `pytest --random-order`

---

## Pre-Commit Checklist

Before committing test changes:

- [ ] Test passes: `pytest tests/integration/test_new.py -v`
- [ ] Test isolated: `pytest tests/integration/test_new.py --random-order` (run 5 times)
- [ ] All tests pass: `pytest tests/integration/ -v`
- [ ] Coverage maintained: `pytest tests/integration/ --cov=server --cov-fail-under=80`
- [ ] Test has docstring with INT-XX reference
- [ ] Test uses fixtures (no hardcoded data)
- [ ] Test has clear assertion messages

---

## CI/CD Status

Check CI status after pushing:

```bash
# Push branch
git push origin feature-branch

# Check GitHub Actions
# Visit: https://github.com/your-repo/actions
```

**CI Checks:**
- ✅ All integration tests pass
- ✅ Code coverage > 80%
- ✅ Tests run in < 30 seconds
- ✅ Tests pass in random order
- ✅ Tests pass in parallel

---

## Getting Help

**Integration test issues:**
1. Read full error message and traceback
2. Check this quick reference
3. Review `10-integration-test-automation-strategy.md` for details
4. Check `09-integration-test-specification.md` for test requirements
5. Review existing similar tests in `tests/integration/`

**Fixture issues:**
- Check `tests/conftest.py` for fixture definitions
- Run `pytest --fixtures` to see all available fixtures

**Mock issues:**
- Check `tests/mocks/anova_responses.py` for mock data
- Check `tests/mocks/anova_fixtures.py` for mock fixtures

---

## Useful Links

- **Full Strategy:** `docs/10-integration-test-automation-strategy.md`
- **Test Spec:** `docs/09-integration-test-specification.md`
- **CLAUDE.md:** Implementation patterns
- **pytest docs:** https://docs.pytest.org/
- **responses docs:** https://github.com/getsentry/responses

---

**Last Updated:** 2026-01-11
