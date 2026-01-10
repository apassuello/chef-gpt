# Implementation Roadmap

This document provides a phased approach to implementing the Anova AI Sous Vide Assistant. Each phase builds on the previous one, with clear acceptance criteria for moving forward.

---

## Overview

**Total Estimated Time:** 10-20 hours (depending on familiarity with Flask/Python)

**Approach:** Start simple, add complexity incrementally. Each phase should be fully working before moving to the next.

---

## Phase 1: Core Server (MVP)

**Goal:** Get a running Flask server with health check and mock responses for all endpoints.

**Duration:** 2-4 hours

**Why This First:** Validates the basic architecture before integrating external APIs. You can develop and test without needing Anova credentials or a physical device.

### Tasks

1. **Create Flask Application Factory** (`server/app.py`)
   - Implement `create_app()` function
   - Register blueprints for routes
   - Configure Flask app from environment variables
   - Set up error handlers

2. **Define Custom Exceptions** (`server/exceptions.py`)
   - `AnovaServerError` base class
   - `ValidationError` with error_code and message
   - `AnovaAPIError` with status_code
   - `DeviceOfflineError`, `AuthenticationError`

3. **Implement Input Validators** (`server/validators.py`)
   - Define all safety constants (MIN_TEMP, MAX_TEMP, etc.)
   - Implement `validate_start_cook()`
   - Implement helper functions: `_is_poultry()`, `_is_ground_meat()`
   - Enforce all food safety rules from CLAUDE.md

4. **Create Route Stubs** (`server/routes.py`)
   - `/health` - Return `{"status": "ok"}`
   - `/start-cook` - Validate input, return mock success response
   - `/status` - Return mock status (idle or cooking)
   - `/stop-cook` - Return mock stop response
   - All routes return proper JSON format

5. **Basic Configuration** (`server/config.py`)
   - Load environment variables from `.env`
   - Provide config object to Flask app
   - Validate required variables are set

6. **Write Validator Unit Tests** (`tests/test_validators.py`)
   - Implement all test cases from CLAUDE.md Table (TC-VAL-01 through TC-VAL-16)
   - Temperature boundary tests
   - Time boundary tests
   - Food safety tests (poultry, ground meat)
   - Edge cases (missing fields, invalid types)

### Acceptance Criteria

- [ ] `python -m server.app` starts Flask server without errors
- [ ] `curl http://localhost:5000/health` returns `{"status": "ok"}` with 200 status
- [ ] `POST /start-cook` with valid data returns mock success response
- [ ] `POST /start-cook` with temp=35 returns 400 error with TEMPERATURE_TOO_LOW
- [ ] `POST /start-cook` with chicken at 56°C returns 400 error with POULTRY_TEMP_UNSAFE
- [ ] `POST /start-cook` with ground beef at 59°C returns 400 error with GROUND_MEAT_TEMP_UNSAFE
- [ ] All validator tests pass: `pytest tests/test_validators.py -v`
- [ ] Test coverage for validators >80%: `pytest --cov=server.validators`

### Definition of Done

- All routes are accessible and return JSON
- All food safety validation rules are enforced
- All validator unit tests pass
- Server runs without errors

### Sample Manual Tests

```bash
# Valid request
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{"temperature_celsius": 65, "time_minutes": 90, "food_type": "chicken"}'

# Should return mock success

# Invalid temperature
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{"temperature_celsius": 35, "time_minutes": 90}'

# Should return 400 with TEMPERATURE_TOO_LOW

# Unsafe poultry temp
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{"temperature_celsius": 56, "time_minutes": 90, "food_type": "chicken"}'

# Should return 400 with POULTRY_TEMP_UNSAFE
```

---

## Phase 2: Anova Integration

**Goal:** Replace mock responses with real Anova API calls. Ability to control actual device.

**Duration:** 4-8 hours

**Why This Second:** Core validation and structure is proven. Now add the integration layer.

### Prerequisites

- Anova Precision Cooker 3.0 setup and connected to WiFi
- Anova account credentials (email/password)
- Device ID (can be discovered via API or from Anova app)

### Tasks

1. **Implement Firebase Authentication** (`server/anova_client.py`)
   - Firebase email/password sign-in
   - Token storage (in-memory for dev)
   - Token refresh logic
   - Error handling for auth failures

2. **Implement Anova API Client** (`server/anova_client.py`)
   - `start_cook(temperature, time, device_id)` - Start cooking
   - `get_status(device_id)` - Get current status
   - `stop_cook(device_id)` - Stop cooking
   - Device state parsing (idle, preheating, cooking, done)
   - Handle device offline scenarios

3. **Update Routes to Use Real Client** (`server/routes.py`)
   - Replace mock responses with actual API calls
   - Handle `DeviceOfflineError` → 503 response
   - Handle `AuthenticationError` → 500 response
   - Handle device busy state → 409 response

4. **Write Client Tests with Mocks** (`tests/test_anova_client.py`)
   - Mock Firebase auth responses
   - Mock Anova API responses
   - Test successful operations
   - Test error scenarios (device offline, auth failure)
   - Use `responses` library for HTTP mocking

5. **Integration Testing** (Manual)
   - Start cook on real device
   - Query status while cooking
   - Stop cook
   - Test with device unplugged (offline scenario)

### Acceptance Criteria

- [ ] Can authenticate with real Anova credentials
- [ ] Can start a cooking session on physical device
- [ ] Can query status and see real temperature/time
- [ ] Can stop a cooking session
- [ ] Device offline returns 503 with retry_after header
- [ ] Auth failure returns 500 with clear error message
- [ ] Attempting to start cook while already cooking returns 409
- [ ] All Anova client tests pass with mocked responses

### Definition of Done

- Real device responds to API commands
- Status endpoint shows actual device state
- Error scenarios are handled gracefully
- Manual testing confirms end-to-end functionality

### Sample Manual Tests

```bash
# Start real cook
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{"temperature_celsius": 60, "time_minutes": 30, "food_type": "test"}'

# Should start actual device heating water

# Check status
curl -X GET http://localhost:5000/status \
  -H "Authorization: Bearer ${API_KEY}"

# Should show real current temp, target temp, time remaining

# Stop cook
curl -X POST http://localhost:5000/stop-cook \
  -H "Authorization: Bearer ${API_KEY}"

# Device should stop cooking

# Test device offline (unplug device first)
curl -X GET http://localhost:5000/status \
  -H "Authorization: Bearer ${API_KEY}"

# Should return 503 with DEVICE_OFFLINE error
```

---

## Phase 3: Security & Polish

**Goal:** Production-ready security and logging.

**Duration:** 2-4 hours

**Why This Third:** Core functionality works. Now harden for production.

### Tasks

1. **Implement API Key Authentication** (`server/middleware.py`)
   - `@require_api_key` decorator
   - Constant-time comparison using `hmac.compare_digest()`
   - Proper 401 responses for missing/invalid keys
   - Exclude `/health` endpoint from auth requirement

2. **Implement Safe Logging** (`server/middleware.py`)
   - Request logging (method, path, remote addr)
   - Response logging (status code, duration)
   - Error logging (error type, code - NOT values)
   - Explicitly filter out credentials, tokens, API keys
   - Before/after request hooks for automatic logging

3. **Standardize Error Responses** (`server/routes.py` or `server/middleware.py`)
   - Consistent JSON error format across all endpoints
   - Map all exception types to HTTP status codes
   - Register Flask error handlers
   - Include actionable messages in all errors

4. **Write Integration Tests** (`tests/test_routes.py`)
   - Full request/response cycle tests
   - Test with valid API key
   - Test with missing API key (should get 401)
   - Test with invalid API key (should get 401)
   - Test all validation error scenarios
   - Test device offline scenario

5. **Code Review for Security**
   - Verify no credentials in logs (grep for passwords, tokens, keys)
   - Verify API key is constant-time compared
   - Verify all endpoints (except /health) require auth
   - Verify .env is in .gitignore

### Acceptance Criteria

- [ ] Requests without API key return 401
- [ ] Requests with wrong API key return 401
- [ ] Requests with correct API key succeed
- [ ] `/health` endpoint works without API key
- [ ] Logs do not contain API keys, passwords, or tokens
- [ ] All error responses follow consistent JSON format
- [ ] All integration tests pass
- [ ] Security code review passes (no credentials in logs)

### Definition of Done

- Authentication middleware working
- Safe logging implemented
- All tests pass
- Security review complete

### Sample Manual Tests

```bash
# Request without auth
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -d '{"temperature_celsius": 65, "time_minutes": 90}'

# Should return 401 UNAUTHORIZED

# Request with wrong API key
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wrong-key" \
  -d '{"temperature_celsius": 65, "time_minutes": 90}'

# Should return 401 UNAUTHORIZED

# Request with correct API key
curl -X POST http://localhost:5000/start-cook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{"temperature_celsius": 65, "time_minutes": 90}'

# Should succeed (200 or appropriate response)

# Health check (no auth required)
curl http://localhost:5000/health

# Should return {"status": "ok"} without auth
```

---

## Phase 4: Deployment

**Goal:** System running on Raspberry Pi, accessible via HTTPS, integrated with Custom GPT.

**Duration:** 2-4 hours

**Why This Last:** Code is complete and tested. Now deploy to production environment.

### Prerequisites

- Raspberry Pi Zero 2 W with Raspberry Pi OS Lite
- SSH access to the Pi
- Cloudflare account (free)

### Tasks

1. **Set Up Production Configuration**
   - Create encrypted credentials file on Pi
   - Generate encryption key (or use hardware-based key)
   - Update `server/config.py` to support both .env (dev) and encrypted file (prod)
   - Test config loading on Pi

2. **Create systemd Service** (`deployment/anova-server.service`)
   - Already created from spec (07-deployment-architecture.md)
   - Copy to `/etc/systemd/system/`
   - Set proper file permissions
   - Create log directory: `/var/log/anova-server/`

3. **Configure Cloudflare Tunnel**
   - Install `cloudflared` on Pi
   - Create tunnel in Cloudflare dashboard
   - Configure tunnel routing to localhost:5000
   - Install as systemd service
   - Obtain HTTPS URL

4. **Deploy Application to Pi**
   - Clone repository to `/opt/anova-assistant/`
   - Create virtual environment
   - Install dependencies
   - Set up encrypted config file
   - Enable and start services

5. **Configure Custom GPT**
   - Import OpenAPI spec from `05-api-specification.md`
   - Update server URL to Cloudflare Tunnel URL
   - Configure API key authentication (Bearer token)
   - Import system prompt from `04-custom-gpt-spec.md`
   - Test with sample commands

6. **End-to-End Testing**
   - Ask GPT to start a cook
   - Ask GPT for status
   - Ask GPT to stop cook
   - Test error scenarios (invalid temp, device offline)
   - Verify auto-restart after Pi reboot

### Acceptance Criteria

- [ ] Service starts automatically on Pi boot
- [ ] Cloudflare Tunnel provides stable HTTPS URL
- [ ] HTTPS endpoint is accessible from internet
- [ ] Custom GPT can successfully call all endpoints
- [ ] Custom GPT successfully starts a real cook
- [ ] Custom GPT correctly handles validation errors
- [ ] System survives Pi reboot (test by unplugging/replugging)
- [ ] Logs are being written to `/var/log/anova-server/`

### Definition of Done

- Pi is configured and running
- Services auto-start on boot
- Custom GPT is operational
- End-to-end flow works
- System is production-ready

### Deployment Commands

```bash
# On development machine
git push origin main

# On Raspberry Pi
ssh pi@raspberrypi.local

# Clone repository
sudo mkdir -p /opt/anova-assistant
sudo chown pi:pi /opt/anova-assistant
cd /opt/anova-assistant
git clone https://github.com/apassuello/chef-gpt.git .

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create log directory
sudo mkdir -p /var/log/anova-server
sudo chown pi:pi /var/log/anova-server

# Set up encrypted config (manual step - follow security docs)
# ... configure credentials ...

# Install systemd service
sudo cp deployment/anova-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable anova-server
sudo systemctl start anova-server

# Check status
sudo systemctl status anova-server

# Install and configure Cloudflare Tunnel
# (Follow 07-deployment-architecture.md Section 4.4)

# Test
curl http://localhost:5000/health
```

### Post-Deployment Checklist

- [ ] Service is running: `sudo systemctl status anova-server`
- [ ] Cloudflare tunnel is running: `sudo systemctl status cloudflared`
- [ ] Health check works: `curl https://YOUR-TUNNEL-URL/health`
- [ ] Custom GPT can connect to server
- [ ] Logs are clean (no errors in `/var/log/anova-server/`)
- [ ] Credentials are not in git repository
- [ ] `.env` file is gitignored
- [ ] Test reboot: `sudo reboot` then verify services auto-start

---

## Troubleshooting Guide

### Phase 1 Issues

**Problem:** Flask won't start
```bash
# Check for Python syntax errors
python -m py_compile server/app.py

# Check for import errors
python -c "from server.app import create_app"

# Check environment variables
cat .env
```

**Problem:** Tests failing
```bash
# Run with verbose output
pytest -v tests/test_validators.py

# Run specific test
pytest tests/test_validators.py::test_temperature_too_low -v

# Check test coverage
pytest --cov=server.validators --cov-report=term-missing
```

### Phase 2 Issues

**Problem:** Can't connect to Anova
- Check device is online in Anova app
- Verify credentials in `.env`
- Check Firebase auth response (look for error messages)
- Verify device ID is correct

**Problem:** Token refresh failing
- Check refresh token is being stored
- Verify token expiration logic
- Check Firebase refresh endpoint response

### Phase 3 Issues

**Problem:** API key auth not working
- Verify `API_KEY` is set in `.env`
- Check `Authorization` header format: `Bearer <key>`
- Verify constant-time comparison is used

**Problem:** Credentials appearing in logs
- Grep logs for sensitive patterns: `grep -i password /var/log/anova-server/*.log`
- Review logging code for f-strings with variables
- Check middleware filtering

### Phase 4 Issues

**Problem:** Cloudflare Tunnel not connecting
```bash
# Check cloudflared status
sudo systemctl status cloudflared

# View cloudflared logs
sudo journalctl -u cloudflared -n 100

# Test local connectivity first
curl http://localhost:5000/health
```

**Problem:** Service won't start on boot
```bash
# Check service is enabled
sudo systemctl is-enabled anova-server

# Enable if needed
sudo systemctl enable anova-server

# Check for errors
sudo journalctl -u anova-server -n 50
```

**Problem:** Custom GPT can't connect
- Verify Cloudflare Tunnel URL is correct in GPT Actions
- Test URL manually: `curl https://YOUR-TUNNEL-URL/health`
- Check API key is correctly entered in GPT
- Review server logs for 401 errors

---

## Success Metrics

### Phase 1
- ✅ All validator tests pass
- ✅ Mock endpoints return proper JSON
- ✅ Food safety rules enforced

### Phase 2
- ✅ Real device responds to commands
- ✅ Can complete full cook cycle
- ✅ Error handling works

### Phase 3
- ✅ Authentication working
- ✅ No credentials in logs
- ✅ All tests passing

### Phase 4
- ✅ Deployed and accessible via HTTPS
- ✅ Custom GPT operational
- ✅ System stable after reboot

---

## Next Steps After Deployment

1. **Monitor for a week** - Check logs daily, verify no errors
2. **Test edge cases** - Try various foods, temperatures, error scenarios
3. **Document any issues** - Create issues in GitHub for bugs
4. **Create backup** - Run backup script from deployment docs
5. **Share with recipient** - Provide Custom GPT link and brief usage guide

---

## Time Estimates Summary

| Phase | Optimistic | Realistic | Pessimistic |
|-------|-----------|-----------|-------------|
| Phase 1: Core Server | 2 hours | 3 hours | 4 hours |
| Phase 2: Anova Integration | 4 hours | 6 hours | 8 hours |
| Phase 3: Security & Polish | 2 hours | 3 hours | 4 hours |
| Phase 4: Deployment | 2 hours | 3 hours | 4 hours |
| **Total** | **10 hours** | **15 hours** | **20 hours** |

**Note:** Times assume familiarity with Python and Flask. Add 50% if learning these technologies.

---

## Questions During Implementation?

1. Check `CLAUDE.md` for code patterns and anti-patterns
2. Review specification documents in project knowledge base
3. Search project knowledge for specific topics
4. Check troubleshooting section above
5. Review test cases for examples

**Remember:** Food safety is non-negotiable. When in doubt about validation, be conservative and reject the request with a clear explanation.
