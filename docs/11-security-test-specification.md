# 11 - Security Test Specification

> **Document Type:** Security Test Specification
> **Status:** Draft
> **Version:** 1.0
> **Last Updated:** 2026-01-10
> **Depends On:** 02-Security Architecture, 03-Component Architecture, 05-API Specification
> **Blocks:** Security Test Implementation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Security Test Categories](#2-security-test-categories)
3. [Detailed Security Test Specifications](#3-detailed-security-test-specifications)
4. [Timing Attack Testing Methodology](#4-timing-attack-testing-methodology)
5. [Credential Leakage Detection](#5-credential-leakage-detection)
6. [Security Test Data](#6-security-test-data)
7. [Security Testing Tools](#7-security-testing-tools)
8. [Production Security Checklist](#8-production-security-checklist)
9. [Security Test Implementation Guide](#9-security-test-implementation-guide)
10. [Continuous Security Testing](#10-continuous-security-testing)
11. [Traceability Matrix](#11-traceability-matrix)
12. [Security Test Maintenance](#12-security-test-maintenance)

---

## 1. Overview

### 1.1 Purpose

This document specifies security-focused tests for the Anova AI Sous Vide Assistant. Security testing validates that the system protects against unauthorized access, prevents credential leakage, resists timing attacks, and enforces food safety as a security control.

**Key Goals:**
- Verify all SEC-REQ-XX requirements from security architecture
- Prevent credential exposure through logs, errors, or responses
- Ensure timing attack resistance in authentication
- Validate that food safety rules cannot be bypassed
- Minimize information disclosure through error messages

### 1.2 Security Threat Model

This system faces specific threats that guide our security testing approach:

**Primary Threats:**

| Threat ID | Threat | Impact | Mitigation (to be tested) |
|-----------|--------|--------|---------------------------|
| THR-01 | Unauthorized API access via brute force or stolen key | Malicious cooking commands | API key authentication with constant-time comparison |
| THR-02 | Timing attacks to discover valid API keys | Key discovery | Constant-time comparison using `hmac.compare_digest()` |
| THR-03 | Credential exposure via logs or error messages | Account compromise | Log sanitization and controlled error messages |
| THR-04 | Food safety bypass attempts | Food poisoning, legal liability | Server-side validation enforcement |
| THR-05 | Man-in-the-middle attacks | Command tampering | HTTPS-only via Cloudflare Tunnel |
| THR-06 | Information disclosure via verbose errors | System reconnaissance | Generic error messages in production |

**Out of Scope for This Specification:**
- Physical security of Raspberry Pi hardware
- Network security beyond HTTPS enforcement
- Social engineering attacks
- Supply chain vulnerabilities in dependencies (covered by `safety` scanner)

### 1.3 Security Testing Scope

**In Scope:**
- API key authentication (SEC-REQ-01)
- Constant-time comparison (SEC-REQ-06)
- Credential encryption at rest (SEC-REQ-02)
- Credential leak prevention (SEC-REQ-05)
- Food safety validation (SEC-REQ-04)
- HTTPS enforcement (SEC-REQ-03) - deployment test only
- Error message information disclosure

**Testing vs. Penetration Testing:**

This specification defines **security testing** within the development process, not external penetration testing. We validate that security controls are correctly implemented, not that they're unbreakable by a determined attacker.

**Example:**
- **Security Test:** "Verify that API key comparison uses `hmac.compare_digest()`"
- **Penetration Test:** "Attempt to discover API key through timing analysis with network jitter"

We focus on the former. The latter is recommended annually but outside this document's scope.

---

## 2. Security Test Categories

Security tests are organized into categories based on threat vectors and requirements:

### 2.1 Authentication Security (SEC-AUTH-XX)

**Coverage:** SEC-REQ-01, SEC-REQ-06
**Priority:** CRITICAL
**Threat:** THR-01, THR-02

Tests that validate API key authentication and resist timing attacks.

**Test Count:** 6 tests (SEC-AUTH-01 through SEC-AUTH-06)

---

### 2.2 Timing Attack Resistance (SEC-TIME-XX)

**Coverage:** SEC-REQ-06
**Priority:** HIGH
**Threat:** THR-02

Tests that validate constant-time comparison and measure timing variance.

**Test Count:** 4 tests (SEC-TIME-01 through SEC-TIME-04)

---

### 2.3 Credential Security (SEC-CRED-XX)

**Coverage:** SEC-REQ-02, SEC-REQ-05
**Priority:** CRITICAL
**Threat:** THR-03

Tests that ensure credentials never leak through logs, errors, or responses.

**Test Count:** 5 tests (SEC-CRED-01 through SEC-CRED-05)

---

### 2.4 Input Validation Security (SEC-VAL-XX)

**Coverage:** SEC-REQ-04 (Food Safety as Security Control)
**Priority:** CRITICAL
**Threat:** THR-04

Tests that validate food safety rules cannot be bypassed through malicious input.

**Test Count:** 3 tests (SEC-VAL-01 through SEC-VAL-03)

---

### 2.5 Information Disclosure (SEC-INFO-XX)

**Coverage:** SEC-REQ-05 (partial)
**Priority:** HIGH
**Threat:** THR-06

Tests that error messages don't reveal system internals or sensitive data.

**Test Count:** 4 tests (SEC-INFO-01 through SEC-INFO-04)

---

### 2.6 Transport Security (SEC-TLS-XX)

**Coverage:** SEC-REQ-03
**Priority:** HIGH (deployment-time)
**Threat:** THR-05

Tests that HTTPS is enforced (deployment-time verification only).

**Test Count:** 2 tests (SEC-TLS-01 through SEC-TLS-02)

---

## 3. Detailed Security Test Specifications

### 3.1 Authentication Security Tests

---

#### SEC-AUTH-01: Valid API Key Authentication

**Requirement:** SEC-REQ-01
**Test Type:** Authentication Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that valid API key is accepted and grants access to protected endpoints.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-valid-test-key`
- Endpoint: `POST /start-cook`
- Headers: `Authorization: Bearer sk-anova-valid-test-key`
- Body: `{"temperature_celsius": 65.0, "time_minutes": 90}`

**Test Steps:**
1. Set environment variable `API_KEY` to known test value
2. Send POST request to `/start-cook` with valid API key in Authorization header
3. Verify request is accepted (not 401 Unauthorized)

**Expected Results:**
- Request accepted (HTTP 200 or appropriate success/error status)
- `middleware.require_api_key()` decorator passes
- Route handler executes

**Security Assertion:**
Valid credentials grant access as designed. This is a baseline test ensuring the authentication system works for legitimate users.

**Failure Criteria:**
- Valid API key rejected (false negative)
- 401 Unauthorized with valid key
- Authentication bypassed entirely

---

#### SEC-AUTH-02: Missing Authorization Header Rejected

**Requirement:** SEC-REQ-01
**Test Type:** Authentication Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that requests without Authorization header are rejected.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-valid-test-key`
- Endpoint: `POST /start-cook`
- Headers: **No Authorization header**
- Body: `{"temperature_celsius": 65.0, "time_minutes": 90}`

**Test Steps:**
1. Send POST request to `/start-cook` without Authorization header
2. Verify request is rejected with 401 Unauthorized
3. Verify error response contains actionable message

**Expected Results:**
- HTTP 401 Unauthorized
- Response body:
  ```json
  {
    "error": "UNAUTHORIZED",
    "message": "Missing or invalid Authorization header"
  }
  ```

**Security Assertion:**
Unauthenticated requests are denied. This prevents unauthorized device control.

**Failure Criteria:**
- Request accepted without authentication
- No error response returned
- Non-401 status code

---

#### SEC-AUTH-03: Invalid Bearer Format Rejected

**Requirement:** SEC-REQ-01
**Test Type:** Authentication Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that malformed Authorization headers are rejected.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-valid-test-key`
- Endpoint: `POST /start-cook`
- Body: Valid cook request

**Test Steps:**

Test each malformed Authorization header format:

| Test Case | Authorization Header | Expected Result |
|-----------|---------------------|-----------------|
| 3a | `Basic abc123` | 401 (wrong scheme) |
| 3b | `Bearer` | 401 (missing token) |
| 3c | `sk-anova-key` | 401 (no "Bearer" prefix) |
| 3d | (empty string) | 401 (empty) |

**Expected Results:**
- All cases return HTTP 401 Unauthorized
- Response body contains `"error": "UNAUTHORIZED"`

**Security Assertion:**
Authentication parser is strict and doesn't accept malformed inputs.

**Failure Criteria:**
- Any malformed header accepted
- Request processed without valid "Bearer <token>" format

---

#### SEC-AUTH-04: Invalid API Key Rejected

**Requirement:** SEC-REQ-01
**Test Type:** Authentication Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that incorrect API keys are rejected.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-correct-key`
- Endpoint: `POST /start-cook`
- Headers: `Authorization: Bearer sk-anova-WRONG-key`

**Test Steps:**
1. Send request with incorrect but well-formed API key
2. Verify rejection with 401 Unauthorized
3. Verify error message doesn't reveal valid key

**Expected Results:**
- HTTP 401 Unauthorized
- Response body:
  ```json
  {
    "error": "UNAUTHORIZED",
    "message": "Invalid API key"
  }
  ```
- Message does NOT contain valid key or hints about key format

**Security Assertion:**
Invalid credentials are rejected without revealing information about valid credentials.

**Failure Criteria:**
- Invalid key accepted
- Error message reveals valid key or key format
- Different behavior for "close" vs "far" keys (timing leak)

---

#### SEC-AUTH-05: Case-Sensitive API Key Validation

**Requirement:** SEC-REQ-01, SEC-REQ-06
**Test Type:** Authentication Security
**Priority:** HIGH
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that API key comparison is case-sensitive and constant-time.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-TestKey123`
- Endpoint: `POST /start-cook`

**Test Steps:**
1. Send request with correct case: `Authorization: Bearer sk-anova-TestKey123` → Accept
2. Send request with wrong case: `Authorization: Bearer sk-anova-testkey123` → Reject
3. Send request with wrong case: `Authorization: Bearer SK-ANOVA-TESTKEY123` → Reject

**Expected Results:**
- Only exact case match accepted
- Case mismatches rejected with 401
- All rejections have similar timing (constant-time)

**Security Assertion:**
Case sensitivity increases key entropy. Constant-time comparison prevents timing attacks on case differences.

**Failure Criteria:**
- Case-insensitive comparison (reduces key space)
- Early rejection on case mismatch (timing leak)

---

#### SEC-AUTH-06: All Protected Endpoints Require Auth

**Requirement:** SEC-REQ-01
**Test Type:** Authentication Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify all endpoints except `/health` require authentication.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-test-key`
- No Authorization header provided

**Test Steps:**

Test each endpoint without authentication:

| Endpoint | Method | Expected Status | Notes |
|----------|--------|-----------------|-------|
| `/health` | GET | 200 | Public endpoint |
| `/start-cook` | POST | 401 | Protected |
| `/status` | GET | 401 | Protected |
| `/stop-cook` | POST | 401 | Protected |

**Expected Results:**
- `/health` accessible without auth (200 OK)
- All other endpoints reject with 401 Unauthorized

**Security Assertion:**
Authentication is consistently applied. No unprotected endpoints exist that could control the device.

**Failure Criteria:**
- Any protected endpoint accessible without auth
- Inconsistent authentication enforcement

---

### 3.2 Timing Attack Resistance Tests

---

#### SEC-TIME-01: Constant-Time Comparison for Valid Key

**Requirement:** SEC-REQ-06
**Test Type:** Timing Attack Resistance
**Priority:** HIGH
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Verify that API key comparison for valid keys doesn't leak timing information.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-` + `a` * 32 (total 42 chars)
- Endpoint: `POST /start-cook`
- Sample size: 1000 requests

**Test Steps:**
1. Send 1000 requests with valid API key
2. Measure time from request send to response receive (nanosecond precision)
3. Calculate mean and standard deviation of timing
4. Store results for comparison with SEC-TIME-02

**Expected Results:**
- All 1000 requests return 200 OK (or validation error, not 401)
- Timing variance recorded for baseline

**Security Assertion:**
Establishes baseline timing for valid key comparison.

**Failure Criteria:**
- High variance in timing (> 10% coefficient of variation) suggests non-constant implementation
- Any 401 responses (test setup error)

---

#### SEC-TIME-02: Constant-Time Comparison for Invalid Key

**Requirement:** SEC-REQ-06
**Test Type:** Timing Attack Resistance
**Priority:** HIGH
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Verify that API key comparison for invalid keys (same length) has similar timing to valid keys.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-` + `a` * 32
- Test key: `sk-anova-` + `b` * 32 (same length, different content)
- Endpoint: `POST /start-cook`
- Sample size: 1000 requests

**Test Steps:**
1. Send 1000 requests with invalid but same-length API key
2. Measure timing for each request
3. Calculate mean and standard deviation
4. Compare timing distribution to SEC-TIME-01 results

**Expected Results:**
- All 1000 requests return 401 Unauthorized
- Mean timing difference from SEC-TIME-01 < 1 microsecond (1000 nanoseconds)
- Standard deviations overlap significantly

**Security Assertion:**
Invalid key comparison takes constant time, preventing attackers from learning about key correctness through timing.

**Failure Criteria:**
- Timing difference > 1 microsecond
- Measurable pattern that correlates with key correctness
- Early rejection (string comparison stops at first mismatch)

---

#### SEC-TIME-03: Statistical Timing Analysis

**Requirement:** SEC-REQ-06
**Test Type:** Timing Attack Resistance
**Priority:** HIGH
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Perform statistical analysis to detect timing leaks across different key scenarios.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-correct-key-12345`
- Test keys:
  - Correct: `sk-anova-correct-key-12345`
  - Wrong (1 char diff at start): `sk-anova-Xorrect-key-12345`
  - Wrong (1 char diff at end): `sk-anova-correct-key-1234X`
  - Wrong (all different): `sk-anova-completely-wrong-key`
- Sample size: 1000 requests per key

**Test Steps:**
1. Measure timing for each key type (4000 total requests)
2. Perform statistical tests:
   - Welch's t-test between correct and each incorrect key type
   - Calculate effect size (Cohen's d)
   - Test for correlation between "closeness" and timing

**Expected Results:**
- Welch's t-test p-value > 0.05 (no significant difference)
- Cohen's d < 0.2 (negligible effect size)
- No correlation between key similarity and timing

**Security Assertion:**
Timing is independent of key correctness, preventing attackers from iteratively discovering the key.

**Failure Criteria:**
- Significant timing difference (p < 0.05)
- Medium or large effect size (d > 0.5)
- Detectable correlation between key similarity and timing

---

#### SEC-TIME-04: No Early Rejection Timing Leakage

**Requirement:** SEC-REQ-06
**Test Type:** Timing Attack Resistance
**Priority:** HIGH
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Verify that comparison doesn't stop early when mismatch detected.

**Test Setup:**
- Environment variable: `API_KEY=sk-anova-correct-key`
- Test keys (same length, mismatch at different positions):
  - `sk-anova-Xorrect-key` (mismatch at position 9)
  - `sk-anova-cXrrect-key` (mismatch at position 10)
  - `sk-anova-coXrect-key` (mismatch at position 11)
  - ... (test all positions)
- Sample size: 500 requests per position

**Test Steps:**
1. Measure timing for keys with mismatch at each position
2. Plot timing vs. mismatch position
3. Test for linear correlation

**Expected Results:**
- No correlation between mismatch position and timing (R² < 0.1)
- Flat timing curve (no upward or downward trend)
- This confirms entire string is compared, not early-rejected

**Security Assertion:**
Comparison examines entire key regardless of where mismatch occurs, preventing position-based timing attacks.

**Failure Criteria:**
- Strong correlation (R² > 0.3) between position and timing
- Timing increases as mismatch position moves later in string
- Evidence of early rejection optimization

**Implementation Note:**
`hmac.compare_digest()` is specifically designed to prevent this. This test validates correct usage.

---

### 3.3 Credential Security Tests

---

#### SEC-CRED-01: Credentials Not in Application Logs

**Requirement:** SEC-REQ-05
**Test Type:** Credential Security
**Priority:** CRITICAL
**OWASP Mapping:** A09:2021 - Security Logging and Monitoring Failures

**Test Objective:**
Verify that credentials never appear in log output.

**Test Setup:**
- Set environment variables:
  - `API_KEY=sk-anova-secret-test-key-12345`
  - `ANOVA_PASSWORD=TestPassword123!`
  - `ANOVA_EMAIL=test@example.com`
- Configure logging to capture all output (pytest `caplog` fixture)
- Endpoints: All

**Test Steps:**
1. Make successful authenticated request to `/start-cook`
2. Make failed authentication request (invalid API key)
3. Trigger validation error
4. Trigger Anova API error
5. Search all log records for sensitive patterns:
   - Full API key: `sk-anova-secret-test-key-12345`
   - Partial API key: `secret-test-key`
   - Password: `TestPassword123!`
   - Email: `test@example.com`
   - Authorization header content: `Bearer sk-anova-`
   - Any occurrence of "password", "bearer", "authorization" followed by actual values

**Expected Results:**
- No log record contains full API key
- No log record contains password
- No log record contains email (if used for auth)
- Authorization headers not logged (may log "Authorization: [REDACTED]")

**Security Assertion:**
Logs can be safely shared for debugging without exposing credentials.

**Failure Criteria:**
- Any credential appears in plaintext in logs
- Authorization header logged with token
- Password logged during authentication attempts

**Allowed Log Patterns:**
```
✓ "Request: POST /start-cook"
✓ "Authentication failed"
✓ "Invalid API key attempt"
✗ "API key: sk-anova-..."
✗ "Authorization: Bearer sk-anova-..."
✗ "Password: TestPassword123!"
```

---

#### SEC-CRED-02: Credentials Not in Error Messages

**Requirement:** SEC-REQ-05
**Test Type:** Credential Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that error responses don't leak credentials.

**Test Setup:**
- Set `API_KEY=sk-anova-secret-key`
- Trigger various error conditions

**Test Steps:**

Test each error scenario and verify response doesn't contain credentials:

| Error Trigger | Endpoint | Check Response For |
|---------------|----------|-------------------|
| Missing auth header | `/start-cook` | No mention of expected key |
| Invalid auth header | `/start-cook` | Doesn't echo provided key back |
| Validation error | `/start-cook` | No credentials in error details |
| Anova auth failure | `/start-cook` | No email/password in message |
| Configuration error | Server startup | No credentials in error |

**Expected Results:**
- Error messages are generic and actionable
- No credentials echoed back to client
- No hints about valid credential format beyond necessary

**Security Assertion:**
Error messages help legitimate users troubleshoot without aiding attackers.

**Failure Criteria:**
- Error message contains API key (even partial)
- Error message reveals password or email
- Error echoes back provided credentials

**Example Good Error:**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid API key"
}
```

**Example Bad Error:**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Provided key 'sk-anova-wrong' does not match expected key 'sk-anova-secret-key'"
}
```

---

#### SEC-CRED-03: Credentials Not in HTTP Responses

**Requirement:** SEC-REQ-05
**Test Type:** Credential Security
**Priority:** CRITICAL
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that successful responses don't leak credentials.

**Test Setup:**
- Valid authentication configured
- Test all successful endpoints

**Test Steps:**

For each endpoint, verify response doesn't contain credentials:

| Endpoint | Response Fields to Check |
|----------|-------------------------|
| `/health` | All fields |
| `/start-cook` | All fields (especially cook metadata) |
| `/status` | All fields |
| `/stop-cook` | All fields |

**Expected Results:**
- No API key in response body
- No email/password in response
- No Firebase tokens in response
- No Anova credentials in response

**Security Assertion:**
Successful operations don't inadvertently leak credentials in response metadata.

**Failure Criteria:**
- Any credential appears in response JSON
- Response headers contain credentials (e.g., echoed Authorization header)

---

#### SEC-CRED-04: Environment Variables Not Exposed via /health

**Requirement:** SEC-REQ-05
**Test Type:** Credential Security
**Priority:** HIGH
**OWASP Mapping:** A05:2021 - Security Misconfiguration

**Test Objective:**
Verify that public `/health` endpoint doesn't expose configuration.

**Test Setup:**
- Set all environment variables (including credentials)
- Endpoint: `GET /health`

**Test Steps:**
1. Request `/health` endpoint without authentication
2. Parse response JSON
3. Verify no credential-related fields present

**Expected Results:**
- Response contains only:
  - `status`: "ok"
  - `version`: version string
  - `timestamp`: ISO timestamp
- Response does NOT contain:
  - API key
  - Configuration values
  - Environment variables
  - Anova credentials
  - Device ID (could be sensitive)

**Security Assertion:**
Health check provides monitoring capability without security risk.

**Failure Criteria:**
- Any credential or sensitive config in response
- Response contains environment variable dump
- Device ID or identifying information exposed

---

#### SEC-CRED-05: API Key Not Echoed in 401 Response

**Requirement:** SEC-REQ-05
**Test Type:** Credential Security
**Priority:** HIGH
**OWASP Mapping:** A01:2021 - Broken Access Control

**Test Objective:**
Verify that 401 error response doesn't echo provided API key.

**Test Setup:**
- Valid API key: `sk-anova-correct-key`
- Test with invalid key: `sk-anova-attacker-key`

**Test Steps:**
1. Send request with invalid API key
2. Receive 401 Unauthorized response
3. Verify response doesn't contain provided key

**Expected Results:**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid API key"
}
```
- Message does NOT contain `sk-anova-attacker-key`
- No other response field contains provided key

**Security Assertion:**
Failed authentication doesn't leak information about what was attempted.

**Failure Criteria:**
- Response echoes provided API key
- Response contains hint about expected key format
- Different error messages for "close" vs "far" keys

---

### 3.4 Input Validation Security Tests (Food Safety Bypass)

---

#### SEC-VAL-01: Cannot Bypass Temperature Validation

**Requirement:** SEC-REQ-04
**Test Type:** Input Validation Security
**Priority:** CRITICAL
**OWASP Mapping:** A03:2021 - Injection

**Test Objective:**
Verify that temperature validation cannot be bypassed through malicious input.

**Test Setup:**
- Endpoint: `POST /start-cook`
- Valid authentication

**Test Steps:**

Attempt various bypass techniques:

| Bypass Attempt | Input | Expected Result |
|----------------|-------|-----------------|
| Negative temp | `{"temperature_celsius": -100}` | 400 TEMPERATURE_TOO_LOW |
| Extreme temp | `{"temperature_celsius": 999999}` | 400 TEMPERATURE_TOO_HIGH |
| String injection | `{"temperature_celsius": "65; DROP TABLE"}` | 400 INVALID_TEMPERATURE |
| Type confusion | `{"temperature_celsius": null}` | 400 MISSING_TEMPERATURE |
| Array bypass | `{"temperature_celsius": [65]}` | 400 INVALID_TEMPERATURE |
| Object bypass | `{"temperature_celsius": {"value": 1}}` | 400 INVALID_TEMPERATURE |
| Bypass flag | `{"temperature_celsius": 1, "bypass_safety": true}` | 400 TEMPERATURE_TOO_LOW |

**Expected Results:**
- All bypass attempts rejected with 400 Bad Request
- Appropriate validation error code returned
- No request reaches Anova API

**Security Assertion:**
Food safety validation is robust against injection and type confusion attacks.

**Failure Criteria:**
- Any bypass attempt accepted
- Request forwarded to Anova with unsafe temperature
- Validation skipped based on any input flag

---

#### SEC-VAL-02: Cannot Bypass Time Validation

**Requirement:** SEC-REQ-04
**Test Type:** Input Validation Security
**Priority:** CRITICAL
**OWASP Mapping:** A03:2021 - Injection

**Test Objective:**
Verify that time validation cannot be bypassed.

**Test Setup:**
- Endpoint: `POST /start-cook`
- Valid authentication

**Test Steps:**

Attempt various bypass techniques:

| Bypass Attempt | Input | Expected Result |
|----------------|-------|-----------------|
| Zero time | `{"temperature_celsius": 65, "time_minutes": 0}` | 400 TIME_TOO_SHORT |
| Negative time | `{"temperature_celsius": 65, "time_minutes": -1}` | 400 TIME_TOO_SHORT |
| Extreme time | `{"temperature_celsius": 65, "time_minutes": 999999}` | 400 TIME_TOO_LONG |
| String injection | `{"time_minutes": "90; rm -rf /"}` | 400 INVALID_TIME |
| Float overflow | `{"time_minutes": 1e308}` | 400 TIME_TOO_LONG |

**Expected Results:**
- All bypass attempts rejected with 400
- Appropriate validation error code
- No unsafe time reaches Anova API

**Security Assertion:**
Time validation prevents both unsafe cooking and resource exhaustion attacks.

**Failure Criteria:**
- Any bypass accepted
- Extreme time values processed
- Injection attempts reach backend

---

#### SEC-VAL-03: Validation Happens Before Anova API Call

**Requirement:** SEC-REQ-04
**Test Type:** Input Validation Security
**Priority:** CRITICAL
**OWASP Mapping:** A04:2021 - Insecure Design

**Test Objective:**
Verify that validation happens server-side before external API call, not just in GPT.

**Test Setup:**
- Mock Anova API to track if called
- Send invalid temperature (e.g., 1°C)

**Test Steps:**
1. Send request with `temperature_celsius: 1` (unsafe)
2. Verify validation error returned (400)
3. Verify Anova API mock was NOT called

**Expected Results:**
- Validation error: 400 TEMPERATURE_TOO_LOW
- Anova API never receives request
- Response time is fast (< 100ms, no network call)

**Security Assertion:**
Server-side validation is the enforcement point, not just a convenience. This prevents attackers from directly calling the Anova API via our server with unsafe parameters.

**Failure Criteria:**
- Anova API called with invalid parameters
- Validation happens in Anova client instead of validator
- Request forwarded and rejected by Anova (validation should happen first)

**Implementation Verification:**
```python
# routes.py should follow this pattern:
def start_cook():
    data = request.json

    # 1. Validate FIRST (SEC-VAL-03)
    params = validate_cook_params(data)  # ← Must happen before API call

    # 2. Call Anova API SECOND
    result = anova.start_cook(**params)
```

---

### 3.5 Information Disclosure Tests

---

#### SEC-INFO-01: Error Messages Don't Reveal System Internals

**Requirement:** SEC-REQ-05 (partial)
**Test Type:** Information Disclosure
**Priority:** HIGH
**OWASP Mapping:** A05:2021 - Security Misconfiguration

**Test Objective:**
Verify that error messages are generic and don't expose implementation details.

**Test Setup:**
- Trigger various error conditions
- Production mode (DEBUG=False)

**Test Steps:**

Test each error type and verify message content:

| Error Scenario | Check Response Does NOT Contain |
|----------------|--------------------------------|
| Validation error | File paths, stack traces |
| Anova API error | Internal error codes, service URLs |
| Authentication error | Database info, config paths |
| Unhandled exception | Python version, library versions |
| Database error (if applicable) | Schema details, table names |

**Expected Results:**
- All errors return generic, actionable messages
- No file paths (e.g., `/home/pi/anova-server/...`)
- No stack traces
- No internal component names (unless necessary)

**Security Assertion:**
Errors help legitimate users without aiding attackers in reconnaissance.

**Failure Criteria:**
- Stack trace in response
- File system paths revealed
- Internal error details exposed

**Example Good Error:**
```json
{
  "error": "ANOVA_API_ERROR",
  "message": "Unable to communicate with device. Please check connection."
}
```

**Example Bad Error:**
```json
{
  "error": "ANOVA_API_ERROR",
  "message": "Connection failed to https://api.anovaculinary.com/devices/abc123 in /home/pi/anova-server/server/anova_client.py line 245"
}
```

---

#### SEC-INFO-02: Stack Traces Not Exposed in Production

**Requirement:** SEC-REQ-05
**Test Type:** Information Disclosure
**Priority:** HIGH
**OWASP Mapping:** A05:2021 - Security Misconfiguration

**Test Objective:**
Verify that unhandled exceptions don't expose stack traces.

**Test Setup:**
- Production configuration (DEBUG=False)
- Trigger unhandled exception (e.g., mock a code path that raises unexpected error)

**Test Steps:**
1. Configure Flask with DEBUG=False
2. Trigger unhandled exception (e.g., mock method to raise `RuntimeError`)
3. Verify response doesn't contain stack trace

**Expected Results:**
- HTTP 500 Internal Server Error
- Response body:
  ```json
  {
    "error": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
  ```
- No traceback in response
- Stack trace logged server-side only (not sent to client)

**Security Assertion:**
Internal errors are logged for debugging but don't leak information to clients.

**Failure Criteria:**
- Stack trace in HTTP response
- Python traceback visible
- File paths or code snippets in response

---

#### SEC-INFO-03: Debug Information Disabled in Production

**Requirement:** SEC-REQ-05
**Test Type:** Information Disclosure
**Priority:** MEDIUM
**OWASP Mapping:** A05:2021 - Security Misconfiguration

**Test Objective:**
Verify that debug-related endpoints and features are disabled in production.

**Test Setup:**
- Production configuration (DEBUG=False)
- Check for debug endpoints

**Test Steps:**
1. Request common debug endpoints:
   - `/debug` → 404
   - `/config` → 404
   - `/env` → 404
   - `/_debug_toolbar` → 404
2. Verify Flask debug mode off (app.debug == False)
3. Verify debug headers not present in responses

**Expected Results:**
- All debug endpoints return 404
- Flask debug mode disabled
- No debug-related response headers

**Security Assertion:**
Debug features are development-only and not accessible in production.

**Failure Criteria:**
- Any debug endpoint accessible
- Debug mode enabled in production
- Debug information in response headers

---

#### SEC-INFO-04: File Paths Not Exposed in Errors

**Requirement:** SEC-REQ-05
**Test Type:** Information Disclosure
**Priority:** MEDIUM
**OWASP Mapping:** A05:2021 - Security Misconfiguration

**Test Objective:**
Verify that error messages don't reveal file system structure.

**Test Setup:**
- Trigger errors that might reference files:
  - Config file not found
  - Import error
  - File permission error

**Test Steps:**
1. Mock configuration file missing
2. Trigger error during startup or config load
3. Verify error message doesn't contain absolute paths

**Expected Results:**
- Error message mentions "configuration file" but not path
- No paths like `/home/pi/anova-server/config/credentials.enc`
- Generic messages like "Configuration not found"

**Security Assertion:**
File system structure is not revealed, making it harder for attackers to target specific files.

**Failure Criteria:**
- Absolute file paths in error messages
- Directory structure revealed
- Filenames exposed (even without path)

---

### 3.6 Transport Security Tests (Deployment-Time)

---

#### SEC-TLS-01: HTTPS Required (Deployment Test)

**Requirement:** SEC-REQ-03
**Test Type:** Transport Security
**Priority:** HIGH
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Verify that Cloudflare Tunnel enforces HTTPS.

**Test Setup:**
- Deployed environment with Cloudflare Tunnel
- Public tunnel URL (e.g., `https://anova-xxxx.trycloudflare.com`)

**Test Steps:**
1. Access endpoint via HTTPS: `https://anova-xxxx.trycloudflare.com/health`
2. Verify connection uses TLS (check browser/curl)
3. Verify certificate is valid (not self-signed warning)

**Expected Results:**
- HTTPS connection successful
- Valid TLS certificate (issued by Cloudflare or trusted CA)
- No certificate warnings

**Security Assertion:**
All traffic is encrypted in transit, preventing man-in-the-middle attacks.

**Failure Criteria:**
- HTTP (plaintext) connection works
- Invalid or self-signed certificate
- TLS version < 1.2

**Test Method:**
```bash
# Verify HTTPS enforced
curl -v https://anova-xxxx.trycloudflare.com/health

# Check TLS version and certificate
openssl s_client -connect anova-xxxx.trycloudflare.com:443 -tls1_2
```

---

#### SEC-TLS-02: HTTP Requests Rejected (Deployment Test)

**Requirement:** SEC-REQ-03
**Test Type:** Transport Security
**Priority:** MEDIUM
**OWASP Mapping:** A02:2021 - Cryptographic Failures

**Test Objective:**
Verify that HTTP (plaintext) requests are rejected or redirected to HTTPS.

**Test Setup:**
- Deployed environment with Cloudflare Tunnel

**Test Steps:**
1. Attempt HTTP connection: `http://anova-xxxx.trycloudflare.com/health`
2. Verify request fails or redirects to HTTPS

**Expected Results:**
- HTTP request redirected to HTTPS (301 or 302)
- OR HTTP request rejected (connection refused)
- No plaintext communication allowed

**Security Assertion:**
System enforces encrypted transport, preventing accidental plaintext exposure.

**Failure Criteria:**
- HTTP request succeeds with plaintext response
- No redirect to HTTPS
- Credentials transmitted over HTTP

**Note:**
Cloudflare Tunnel typically handles this automatically. This test validates the deployment configuration.

---

## 4. Timing Attack Testing Methodology

### 4.1 Overview

Timing attacks exploit differences in execution time to learn secrets. In API key authentication, an attacker might measure comparison time to iteratively guess each character of the key.

**Example Vulnerable Code:**
```python
# VULNERABLE: Early rejection
def check_key_vulnerable(provided, expected):
    if len(provided) != len(expected):
        return False
    for i in range(len(provided)):
        if provided[i] != expected[i]:
            return False  # ← Returns immediately on mismatch
    return True
```

If this code takes 1μs per character, an attacker can measure:
- Key starts with 'a': 1μs (immediate rejection)
- Key starts with 's': 2μs (second character checked)
- Key starts with 'sk': 3μs (third character checked)

This allows brute-forcing each character position.

**Secure Code:**
```python
# SECURE: Constant-time comparison
import hmac

def check_key_secure(provided, expected):
    return hmac.compare_digest(provided, expected)
```

This checks all bytes regardless of where mismatch occurs.

---

### 4.2 Testing Approach

**Goal:** Verify that comparison time is independent of key correctness.

**Method:** Statistical hypothesis testing

**Null Hypothesis (H₀):** "API key comparison time is independent of key correctness"
**Alternative Hypothesis (H₁):** "API key comparison time correlates with key correctness"

**Decision Rule:**
- If timing difference is statistically significant (p < 0.05) → FAIL (timing leak detected)
- If timing difference is negligible (p > 0.05, Cohen's d < 0.2) → PASS (constant-time)

---

### 4.3 Implementation: Statistical Timing Test

**Test:** SEC-TIME-03 (Statistical Timing Analysis)

**Implementation:**

```python
import pytest
import time
import statistics
import scipy.stats as stats  # Install: pip install scipy

def test_sec_time_03_statistical_timing_analysis(client, monkeypatch):
    """
    SEC-TIME-03: Statistical analysis to detect timing leaks.

    Tests that API key comparison timing is independent of key correctness.
    """

    # === Test Setup ===

    VALID_KEY = "sk-anova-correct-key-12345678901234567890"

    # Test keys (all same length)
    test_keys = {
        "correct": VALID_KEY,
        "wrong_start": "sk-anova-Xorrect-key-12345678901234567890",  # First char different
        "wrong_end": "sk-anova-correct-key-1234567890123456789X",    # Last char different
        "all_different": "sk-anova-completely-wrong-test-key-000000"  # All different
    }

    monkeypatch.setenv("API_KEY", VALID_KEY)

    # === Data Collection ===

    SAMPLE_SIZE = 1000
    timings = {key_type: [] for key_type in test_keys.keys()}

    for key_type, test_key in test_keys.items():
        print(f"\nCollecting {SAMPLE_SIZE} samples for {key_type} key...")

        for i in range(SAMPLE_SIZE):
            # Measure timing
            start = time.perf_counter_ns()

            response = client.post(
                '/start-cook',
                headers={'Authorization': f'Bearer {test_key}'},
                json={
                    'temperature_celsius': 65.0,
                    'time_minutes': 90
                }
            )

            end = time.perf_counter_ns()
            timings[key_type].append(end - start)

            # Verify expected response status
            if key_type == "correct":
                # May be 200 (mock success) or 400 (validation error), but NOT 401
                assert response.status_code != 401
            else:
                assert response.status_code == 401

    # === Statistical Analysis ===

    # Calculate descriptive statistics
    stats_summary = {}
    for key_type, samples in timings.items():
        stats_summary[key_type] = {
            "mean": statistics.mean(samples),
            "stdev": statistics.stdev(samples),
            "median": statistics.median(samples),
            "count": len(samples)
        }

    print("\n=== Timing Statistics (nanoseconds) ===")
    for key_type, s in stats_summary.items():
        print(f"{key_type:15} | Mean: {s['mean']:12.2f} | StdDev: {s['stdev']:12.2f} | Median: {s['median']:12.2f}")

    # === Hypothesis Testing ===

    # Compare correct key timing to each incorrect key timing
    correct_times = timings["correct"]

    for key_type in ["wrong_start", "wrong_end", "all_different"]:
        incorrect_times = timings[key_type]

        # Welch's t-test (doesn't assume equal variance)
        t_stat, p_value = stats.ttest_ind(correct_times, incorrect_times, equal_var=False)

        # Effect size (Cohen's d)
        mean_diff = stats_summary["correct"]["mean"] - stats_summary[key_type]["mean"]
        pooled_stdev = ((stats_summary["correct"]["stdev"]**2 + stats_summary[key_type]["stdev"]**2) / 2) ** 0.5
        cohens_d = abs(mean_diff / pooled_stdev) if pooled_stdev > 0 else 0

        print(f"\n{key_type} vs correct:")
        print(f"  Mean difference: {mean_diff:12.2f} ns")
        print(f"  Welch's t-test p-value: {p_value:.6f}")
        print(f"  Cohen's d (effect size): {cohens_d:.4f}")

        # === Assertions ===

        # 1. Timing difference must be negligible (< 1 microsecond)
        assert abs(mean_diff) < 1000, \
            f"TIMING LEAK DETECTED: {abs(mean_diff):.0f}ns difference between {key_type} and correct key"

        # 2. Difference must not be statistically significant
        assert p_value > 0.05, \
            f"TIMING LEAK DETECTED: Statistically significant difference (p={p_value:.6f})"

        # 3. Effect size must be negligible (Cohen's d < 0.2)
        assert cohens_d < 0.2, \
            f"TIMING LEAK DETECTED: Measurable effect size (d={cohens_d:.4f})"

    # === Test Passed ===
    print("\n✓ SEC-TIME-03 PASSED: No timing leak detected")
    print(f"  All timing differences < 1μs")
    print(f"  All p-values > 0.05 (not significant)")
    print(f"  All effect sizes < 0.2 (negligible)")
```

---

### 4.4 Interpreting Results

**Pass Criteria:**

| Metric | Threshold | Interpretation |
|--------|-----------|----------------|
| Mean timing difference | < 1 microsecond (1000 ns) | Difference is too small to exploit over network |
| Welch's t-test p-value | > 0.05 | Difference is not statistically significant |
| Cohen's d effect size | < 0.2 | Effect is negligible |

**Fail Criteria (Timing Leak Detected):**

If any of these are true, the implementation is vulnerable:
- Mean timing difference > 1μs
- p-value < 0.05 (statistically significant)
- Cohen's d > 0.2 (small to medium effect size)

**Example Failure:**
```
wrong_start vs correct:
  Mean difference: 15230.00 ns  ← OVER THRESHOLD
  Welch's t-test p-value: 0.000003  ← SIGNIFICANT
  Cohen's d (effect size): 0.85  ← LARGE EFFECT

AssertionError: TIMING LEAK DETECTED: 15230ns difference between wrong_start and correct key
```

This indicates that the key comparison is NOT constant-time and could be exploited.

---

### 4.5 Limitations and Caveats

**Network Jitter:**
- These tests measure server-side timing (HTTP request/response)
- Network latency adds noise (typically 1-50ms)
- Timing differences < 1μs are undetectable over network in practice
- Tests are conservative: a real attacker faces additional challenges

**Local Testing:**
- Tests run locally (no network jitter)
- Makes timing differences easier to detect (good for testing)
- Real-world attacks would require thousands of requests to detect small differences

**When to Worry:**
- Timing differences > 100μs: Easily exploitable even over network
- Timing differences 1-100μs: Exploitable with many samples
- Timing differences < 1μs: Theoretically exploitable but impractical

**Best Practice:**
Use `hmac.compare_digest()` and verify with these tests. If tests pass, the implementation is secure against practical timing attacks.

---

## 5. Credential Leakage Detection

### 5.1 Overview

Credentials can leak through multiple channels:
- **Logs:** Application logs, web server logs, system logs
- **Error messages:** HTTP responses, stack traces
- **HTTP responses:** Success responses, headers
- **Debug endpoints:** Configuration dumps, environment variables

This section provides methodology to detect all credential leakage vectors.

---

### 5.2 What Constitutes Credential Leakage?

**Credentials to Protect:**

| Credential ID | Credential | Leak Risk | Detection Priority |
|---------------|------------|-----------|-------------------|
| CRED-05 | API_KEY | HIGH | CRITICAL |
| CRED-02 | ANOVA_PASSWORD | CRITICAL | CRITICAL |
| CRED-01 | ANOVA_EMAIL | MEDIUM | HIGH |
| CRED-03 | Firebase Access Token | HIGH | HIGH |
| CRED-04 | Firebase Refresh Token | HIGH | HIGH |

**Leak Vectors to Test:**

1. **Application Logs** (SEC-CRED-01)
2. **Error Messages** (SEC-CRED-02)
3. **HTTP Response Bodies** (SEC-CRED-03)
4. **HTTP Response Headers** (SEC-CRED-03)
5. **Public Endpoints** (SEC-CRED-04)
6. **Auth Error Responses** (SEC-CRED-05)

---

### 5.3 Implementation: Comprehensive Credential Leak Test

**Test:** SEC-CRED-01 (Credentials Not in Application Logs)

**Implementation:**

```python
import pytest
import re

def test_sec_cred_01_no_credentials_in_logs(client, caplog, monkeypatch):
    """
    SEC-CRED-01: Verify credentials never appear in log output.

    Tests all code paths that might log and verifies no credentials leak.
    """

    # === Test Setup ===

    # Define sensitive values
    API_KEY = "sk-anova-secret-test-key-12345678901234567890"
    ANOVA_PASSWORD = "SuperSecret123!Password"
    ANOVA_EMAIL = "test-user@example.com"
    DEVICE_ID = "test-device-abc123"

    # Set environment
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("ANOVA_PASSWORD", ANOVA_PASSWORD)
    monkeypatch.setenv("ANOVA_EMAIL", ANOVA_EMAIL)
    monkeypatch.setenv("DEVICE_ID", DEVICE_ID)

    # Sensitive patterns to search for
    sensitive_patterns = [
        # Full credentials
        API_KEY,
        ANOVA_PASSWORD,
        ANOVA_EMAIL,
        # Partial credentials (unique parts)
        "secret-test-key",
        "SuperSecret123",
        "test-user@example.com",
        # Header values
        f"Bearer {API_KEY}",
        # Pattern matches
        r"password['\"]?\s*[:=]\s*['\"]?" + re.escape(ANOVA_PASSWORD),
        r"api[_-]?key['\"]?\s*[:=]\s*['\"]?" + re.escape(API_KEY),
    ]

    # === Execute Test Scenarios ===

    caplog.clear()

    # Scenario 1: Successful authenticated request
    response = client.post(
        '/start-cook',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )

    # Scenario 2: Failed authentication (invalid key)
    response = client.post(
        '/start-cook',
        headers={'Authorization': 'Bearer sk-anova-wrong-key'},
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code == 401

    # Scenario 3: Missing authentication
    response = client.post(
        '/start-cook',
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code == 401

    # Scenario 4: Validation error
    response = client.post(
        '/start-cook',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={'temperature_celsius': 1.0, 'time_minutes': 90}  # Too low
    )
    assert response.status_code == 400

    # Scenario 5: Multiple endpoints
    client.get('/health')
    client.get('/status', headers={'Authorization': f'Bearer {API_KEY}'})

    # === Check All Log Records ===

    print(f"\n=== Analyzing {len(caplog.records)} log records ===")

    leaks_found = []

    for record in caplog.records:
        log_message = record.getMessage()

        # Check for each sensitive pattern
        for pattern in sensitive_patterns:
            if isinstance(pattern, str):
                # Exact string match
                if pattern in log_message:
                    leaks_found.append({
                        "pattern": pattern,
                        "log_level": record.levelname,
                        "log_message": log_message,
                        "location": f"{record.pathname}:{record.lineno}"
                    })
            else:
                # Regex pattern match
                if re.search(pattern, log_message, re.IGNORECASE):
                    leaks_found.append({
                        "pattern": pattern.pattern,
                        "log_level": record.levelname,
                        "log_message": log_message,
                        "location": f"{record.pathname}:{record.lineno}"
                    })

    # === Report Results ===

    if leaks_found:
        print("\n❌ CREDENTIAL LEAKS DETECTED:")
        for leak in leaks_found:
            print(f"\n  Pattern: {leak['pattern']}")
            print(f"  Level: {leak['log_level']}")
            print(f"  Location: {leak['location']}")
            print(f"  Message: {leak['log_message'][:200]}...")

        pytest.fail(f"CREDENTIAL LEAK: Found {len(leaks_found)} credential(s) in logs")

    print("\n✓ SEC-CRED-01 PASSED: No credentials found in logs")
    print(f"  Analyzed {len(caplog.records)} log records")
    print(f"  Tested {len(sensitive_patterns)} sensitive patterns")
    print(f"  0 leaks detected")
```

---

### 5.4 What to Look For in Logs

**Safe Log Patterns:**

```python
# ✓ SAFE: Generic messages
logger.info("Request: POST /start-cook")
logger.info("Authentication successful")
logger.warning("Authentication failed")
logger.error("Validation error: TEMPERATURE_TOO_LOW")

# ✓ SAFE: Redacted values
logger.debug(f"API key: {api_key[:8]}...")  # Only first 8 chars
logger.info(f"User: {email.split('@')[0]}@***")  # Redacted domain
```

**Unsafe Log Patterns:**

```python
# ✗ UNSAFE: Full credentials
logger.info(f"API key: {api_key}")  # Full API key exposed
logger.debug(f"Auth header: {request.headers.get('Authorization')}")  # Contains key
logger.info(f"Password: {password}")  # Password in plaintext

# ✗ UNSAFE: Request/response bodies that may contain credentials
logger.info(f"Request body: {request.json}")  # May contain API key in some endpoints
logger.debug(f"Response: {response.json()}")  # May contain tokens
```

---

### 5.5 Automated Credential Scanning

**Tool:** `detect-secrets` (optional, recommended for CI/CD)

**Installation:**
```bash
pip install detect-secrets
```

**Usage:**
```bash
# Scan codebase for hardcoded secrets
detect-secrets scan > .secrets.baseline

# Audit findings
detect-secrets audit .secrets.baseline

# Scan logs (if saved to file)
detect-secrets scan logs/*.log
```

**Integration:**
Add to CI/CD pipeline to prevent credential commits.

---

## 6. Security Test Data

### 6.1 Invalid Authentication Test Data

**Purpose:** Test authentication robustness against various invalid inputs.

```json
{
  "test_cases": [
    {
      "id": "auth-001",
      "description": "No Authorization header",
      "headers": {},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-002",
      "description": "Empty Authorization header",
      "headers": {"Authorization": ""},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-003",
      "description": "Wrong auth scheme (Basic instead of Bearer)",
      "headers": {"Authorization": "Basic abc123"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-004",
      "description": "Bearer with no token",
      "headers": {"Authorization": "Bearer"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-005",
      "description": "Bearer with whitespace token",
      "headers": {"Authorization": "Bearer    "},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-006",
      "description": "Token without Bearer prefix",
      "headers": {"Authorization": "sk-anova-key"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-007",
      "description": "SQL injection attempt",
      "headers": {"Authorization": "Bearer ' OR '1'='1"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-008",
      "description": "Path traversal attempt",
      "headers": {"Authorization": "Bearer ../../etc/passwd"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-009",
      "description": "Command injection attempt",
      "headers": {"Authorization": "Bearer ; rm -rf /"},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    },
    {
      "id": "auth-010",
      "description": "Extremely long token (potential buffer overflow)",
      "headers": {"Authorization": "Bearer " + "a" * 10000},
      "expected_status": 401,
      "expected_error": "UNAUTHORIZED"
    }
  ]
}
```

---

### 6.2 Food Safety Bypass Test Data

**Purpose:** Test that food safety validation cannot be bypassed.

```json
{
  "test_cases": [
    {
      "id": "safety-001",
      "description": "Negative temperature (dangerous)",
      "input": {"temperature_celsius": -100.0, "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "TEMPERATURE_TOO_LOW"
    },
    {
      "id": "safety-002",
      "description": "Zero temperature (dangerous)",
      "input": {"temperature_celsius": 0.0, "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "TEMPERATURE_TOO_LOW"
    },
    {
      "id": "safety-003",
      "description": "Extreme temperature (boiling)",
      "input": {"temperature_celsius": 999999.0, "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "TEMPERATURE_TOO_HIGH"
    },
    {
      "id": "safety-004",
      "description": "String temperature (type confusion)",
      "input": {"temperature_celsius": "65", "time_minutes": 90},
      "expected_status": 200,
      "note": "String should be coerced to float"
    },
    {
      "id": "safety-005",
      "description": "SQL injection in temperature",
      "input": {"temperature_celsius": "65; DROP TABLE users;", "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "INVALID_TEMPERATURE"
    },
    {
      "id": "safety-006",
      "description": "Null temperature",
      "input": {"temperature_celsius": null, "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "MISSING_TEMPERATURE"
    },
    {
      "id": "safety-007",
      "description": "Array temperature (type confusion)",
      "input": {"temperature_celsius": [65.0], "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "INVALID_TEMPERATURE"
    },
    {
      "id": "safety-008",
      "description": "Object temperature (type confusion)",
      "input": {"temperature_celsius": {"value": 65.0}, "time_minutes": 90},
      "expected_status": 400,
      "expected_error": "INVALID_TEMPERATURE"
    },
    {
      "id": "safety-009",
      "description": "Bypass flag attempt",
      "input": {
        "temperature_celsius": 1.0,
        "time_minutes": 90,
        "bypass_safety": true
      },
      "expected_status": 400,
      "expected_error": "TEMPERATURE_TOO_LOW",
      "note": "bypass_safety flag should be ignored"
    },
    {
      "id": "safety-010",
      "description": "Admin override attempt",
      "input": {
        "temperature_celsius": 1.0,
        "time_minutes": 90,
        "admin_override": true,
        "skip_validation": true
      },
      "expected_status": 400,
      "expected_error": "TEMPERATURE_TOO_LOW",
      "note": "All override flags should be ignored"
    },
    {
      "id": "safety-011",
      "description": "Unsafe poultry temperature",
      "input": {
        "temperature_celsius": 50.0,
        "time_minutes": 90,
        "food_type": "chicken"
      },
      "expected_status": 400,
      "expected_error": "POULTRY_TEMP_UNSAFE"
    },
    {
      "id": "safety-012",
      "description": "Unsafe ground meat temperature",
      "input": {
        "temperature_celsius": 55.0,
        "time_minutes": 90,
        "food_type": "ground beef"
      },
      "expected_status": 400,
      "expected_error": "GROUND_MEAT_TEMP_UNSAFE"
    }
  ]
}
```

---

### 6.3 Information Disclosure Test Patterns

**Purpose:** Patterns that should NEVER appear in responses or logs.

```python
# Patterns that indicate information disclosure
FORBIDDEN_PATTERNS = [
    # File system paths
    r"/home/\w+/",
    r"/usr/local/",
    r"/etc/",
    r"C:\\Users\\",
    r"C:\\Program Files\\",

    # Stack trace markers
    r"Traceback \(most recent call last\)",
    r"File \".*\.py\", line \d+",
    r"raise \w+Error",

    # Python internals
    r"<module '.*' from '.*'>",
    r"<function .* at 0x[0-9a-f]+>",

    # Database details
    r"SELECT .* FROM",
    r"INSERT INTO",
    r"Database connection",

    # Internal URLs/endpoints
    r"https://.*\.googleapis\.com/.*\?key=",
    r"firebase.*apiKey",

    # Version information (be careful, may be intentional)
    r"Python/\d+\.\d+\.\d+",
    r"Flask/\d+\.\d+\.\d+",

    # Credentials
    r"password['\"]?\s*[:=]",
    r"api[_-]?key['\"]?\s*[:=]",
    r"Bearer\s+sk-[a-zA-Z0-9\-_]+",
]

def check_for_information_disclosure(response_text: str) -> list[str]:
    """
    Check response for information disclosure patterns.

    Returns:
        List of pattern descriptions that matched (empty if clean)
    """
    matches = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, response_text, re.IGNORECASE):
            matches.append(pattern)
    return matches
```

---

## 7. Security Testing Tools

### 7.1 Static Analysis Tools

#### 7.1.1 Bandit - Python Security Linter

**Purpose:** Detect common security issues in Python code.

**Installation:**
```bash
pip install bandit
```

**Usage:**
```bash
# Scan entire codebase
bandit -r server/

# Generate JSON report
bandit -r server/ -f json -o bandit-report.json

# Focus on high/medium severity
bandit -r server/ -ll

# Exclude test files
bandit -r server/ --exclude */tests/*
```

**Configuration (.bandit):**
```yaml
# .bandit
tests:
  - B201  # flask_debug_true
  - B501  # request_with_no_cert_validation
  - B506  # yaml_load
  - B608  # hardcoded_sql_expressions
  - B105  # hardcoded_password_string
  - B106  # hardcoded_password_funcarg
  - B107  # hardcoded_password_default

exclude_dirs:
  - /tests/
  - /venv/
```

**Expected Issues to Address:**
- B105: Hardcoded passwords (ensure using environment variables)
- B201: Flask debug mode (ensure disabled in production)

---

#### 7.1.2 Safety - Dependency Vulnerability Scanner

**Purpose:** Check dependencies for known security vulnerabilities.

**Installation:**
```bash
pip install safety
```

**Usage:**
```bash
# Check installed packages
safety check

# Check requirements.txt
safety check -r requirements.txt

# Generate JSON report
safety check --json > safety-report.json

# Continue on error (for CI)
safety check --continue-on-error
```

**Integration:**
Add to CI/CD to prevent deploying vulnerable dependencies.

---

### 7.2 Dynamic Analysis Tools

#### 7.2.1 Pytest - Unit and Integration Testing

**Purpose:** Automated security test execution.

**Installation:**
```bash
pip install pytest pytest-flask pytest-cov
```

**Usage:**
```bash
# Run all security tests
pytest tests/security/ -v

# Run with coverage
pytest tests/security/ --cov=server --cov-report=html

# Run specific test category
pytest tests/security/test_authentication.py -v

# Run timing tests (may be slow)
pytest tests/security/test_timing_attacks.py -v -s
```

---

#### 7.2.2 Custom Timing Harness

**Purpose:** Measure API response timing for timing attack detection.

**Implementation:**
```python
# tests/security/timing_harness.py

import time
import statistics
from typing import List, Dict, Callable

class TimingHarness:
    """Measure timing for timing attack detection."""

    def __init__(self, sample_size: int = 1000):
        self.sample_size = sample_size

    def measure(self, func: Callable, label: str) -> Dict:
        """
        Measure timing for a function over multiple samples.

        Args:
            func: Function to measure (should make HTTP request)
            label: Label for this measurement

        Returns:
            Dictionary with timing statistics
        """
        timings = []

        for i in range(self.sample_size):
            start = time.perf_counter_ns()
            func()
            end = time.perf_counter_ns()
            timings.append(end - start)

        return {
            "label": label,
            "count": len(timings),
            "mean": statistics.mean(timings),
            "stdev": statistics.stdev(timings),
            "median": statistics.median(timings),
            "min": min(timings),
            "max": max(timings)
        }

    def compare(self, results_a: Dict, results_b: Dict) -> Dict:
        """
        Compare two timing measurements.

        Returns:
            Dictionary with comparison statistics
        """
        mean_diff = abs(results_a["mean"] - results_b["mean"])

        # Simple threshold check
        is_constant_time = mean_diff < 1000  # < 1 microsecond

        return {
            "mean_difference_ns": mean_diff,
            "is_constant_time": is_constant_time,
            "threshold_ns": 1000
        }
```

---

### 7.3 Fuzzing Tools

#### 7.3.1 Hypothesis - Property-Based Testing

**Purpose:** Generate random inputs to find edge cases.

**Installation:**
```bash
pip install hypothesis
```

**Usage:**
```python
from hypothesis import given, strategies as st

@given(
    temp=st.floats(min_value=-1000, max_value=1000),
    time=st.integers(min_value=-100, max_value=10000)
)
def test_validation_robustness(temp, time, client):
    """
    Fuzz test: validation should handle all inputs gracefully.
    """
    response = client.post(
        '/start-cook',
        headers={'Authorization': 'Bearer test-key'},
        json={
            'temperature_celsius': temp,
            'time_minutes': time
        }
    )

    # Should never crash (200, 400, or 401, but not 500)
    assert response.status_code in [200, 400, 401]
```

---

## 8. Production Security Checklist

### 8.1 Pre-Deployment Security Verification

**Complete this checklist before deploying to production:**

#### Authentication & Authorization

- [ ] API_KEY is set with strong value (32+ cryptographically random characters)
- [ ] API key generation: `python -c "import secrets; print(f'sk-anova-{secrets.token_urlsafe(32)}')"`
- [ ] API_KEY not committed to git repository
- [ ] All protected endpoints require authentication (verified via SEC-AUTH-06)
- [ ] `/health` is the ONLY unauthenticated endpoint
- [ ] Constant-time comparison used (`hmac.compare_digest()`)
- [ ] Timing attack tests pass (SEC-TIME-01 through SEC-TIME-04)

#### Credential Management

- [ ] Credentials stored in encrypted file OR environment variables
- [ ] Encrypted config file has 600 permissions (owner read/write only)
- [ ] No credentials in git history (`git log -S "password"`)
- [ ] No credentials in log output (verified via SEC-CRED-01)
- [ ] No credentials in error messages (verified via SEC-CRED-02)
- [ ] `.env` file in `.gitignore`
- [ ] `config/credentials.enc` in `.gitignore` (if using plain JSON for dev)

#### Input Validation

- [ ] Food safety validation implemented (SEC-VAL-01, SEC-VAL-02)
- [ ] Validation happens before Anova API call (SEC-VAL-03)
- [ ] All validation error codes match API specification
- [ ] Type coercion handled safely (strings to floats)
- [ ] Extreme values rejected (negative, extremely large)

#### Transport Security

- [ ] Cloudflare Tunnel configured
- [ ] HTTPS enforced (verified via SEC-TLS-01)
- [ ] HTTP requests rejected or redirected (SEC-TLS-02)
- [ ] Valid TLS certificate (not self-signed)
- [ ] TLS version >= 1.2

#### Information Disclosure

- [ ] DEBUG=false in production environment
- [ ] Flask debug mode disabled (`app.debug == False`)
- [ ] No stack traces in error responses (SEC-INFO-02)
- [ ] Error messages are generic (SEC-INFO-01)
- [ ] No debug endpoints accessible (SEC-INFO-03)
- [ ] File paths not exposed in errors (SEC-INFO-04)

#### Logging & Monitoring

- [ ] Logs configured to file or syslog (not just console)
- [ ] Log rotation configured (to prevent disk filling)
- [ ] Sensitive data filtered from logs (SEC-CRED-01)
- [ ] Log level appropriate for production (INFO or WARNING)
- [ ] Health check endpoint working (`GET /health`)

#### Dependency Security

- [ ] `safety check` passes (no known vulnerabilities)
- [ ] `bandit` scan passes (no high-severity issues)
- [ ] Dependencies up to date (`pip list --outdated`)
- [ ] No unused dependencies in requirements.txt

#### Testing

- [ ] All security tests pass (`pytest tests/security/`)
- [ ] Timing attack tests pass (SEC-TIME-XX)
- [ ] Credential leak tests pass (SEC-CRED-XX)
- [ ] Authentication tests pass (SEC-AUTH-XX)
- [ ] Integration tests pass (`pytest tests/`)

#### Documentation

- [ ] API key documented in deployment guide
- [ ] Security incident response plan documented
- [ ] Admin contact information available
- [ ] Backup/recovery procedure documented

---

### 8.2 Post-Deployment Verification

**Run these checks after deployment:**

```bash
# 1. Verify HTTPS enforced
curl -v https://your-anova-tunnel.trycloudflare.com/health

# 2. Verify authentication required
curl https://your-anova-tunnel.trycloudflare.com/status
# Should return: 401 Unauthorized

# 3. Verify health check works
curl https://your-anova-tunnel.trycloudflare.com/health
# Should return: {"status": "ok", ...}

# 4. Verify valid API key works
curl -X POST https://your-anova-tunnel.trycloudflare.com/start-cook \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"temperature_celsius": 65.0, "time_minutes": 90}'
# Should NOT return: 401

# 5. Check TLS certificate
openssl s_client -connect your-anova-tunnel.trycloudflare.com:443 -tls1_2
# Should show valid certificate chain

# 6. Verify logs don't contain credentials
sudo journalctl -u anova-server | grep -i "password\|api.key\|bearer"
# Should return: nothing
```

---

## 9. Security Test Implementation Guide

### 9.1 Test File Structure

**Organize security tests by category:**

```
tests/
├── security/
│   ├── __init__.py
│   ├── conftest.py                      # Security test fixtures
│   ├── test_authentication.py           # SEC-AUTH-XX tests
│   ├── test_timing_attacks.py           # SEC-TIME-XX tests
│   ├── test_credential_security.py      # SEC-CRED-XX tests
│   ├── test_input_validation_security.py # SEC-VAL-XX tests
│   ├── test_information_disclosure.py   # SEC-INFO-XX tests
│   └── test_transport_security.py       # SEC-TLS-XX tests (deployment)
```

---

### 9.2 Pytest Fixtures for Security Testing

**File:** `tests/security/conftest.py`

```python
import pytest
import os
from server.app import create_app
from server.config import Config

@pytest.fixture
def secure_app():
    """
    Flask app configured for security testing.

    Uses test credentials that we can verify don't leak.
    """
    test_config = Config(
        ANOVA_EMAIL="test-security@example.com",
        ANOVA_PASSWORD="SecureTestPassword123!",
        DEVICE_ID="test-device-security-123",
        API_KEY="sk-anova-test-security-key-abcdefghijklmnop",
        DEBUG=False  # Production mode for security tests
    )

    app = create_app(test_config)
    return app

@pytest.fixture
def secure_client(secure_app):
    """Test client for security testing."""
    return secure_app.test_client()

@pytest.fixture
def valid_api_key():
    """Valid API key for security tests."""
    return "sk-anova-test-security-key-abcdefghijklmnop"

@pytest.fixture
def valid_auth_header(valid_api_key):
    """Valid Authorization header dict."""
    return {'Authorization': f'Bearer {valid_api_key}'}

@pytest.fixture
def sensitive_values():
    """
    Dictionary of sensitive values to check for leakage.

    Use this fixture in leak detection tests.
    """
    return {
        "api_key": "sk-anova-test-security-key-abcdefghijklmnop",
        "password": "SecureTestPassword123!",
        "email": "test-security@example.com",
        "device_id": "test-device-security-123"
    }
```

---

### 9.3 Example Test Implementation

**File:** `tests/security/test_authentication.py`

```python
import pytest

def test_sec_auth_01_valid_api_key(secure_client, valid_auth_header):
    """SEC-AUTH-01: Valid API key grants access."""
    response = secure_client.post(
        '/start-cook',
        headers=valid_auth_header,
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    # Should not be 401 (may be 200 or 400 validation error)
    assert response.status_code != 401, "Valid API key was rejected"

def test_sec_auth_02_missing_header(secure_client):
    """SEC-AUTH-02: Missing Authorization header rejected."""
    response = secure_client.post(
        '/start-cook',
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'
    assert 'Authorization' in data['message']

def test_sec_auth_03_invalid_bearer_format(secure_client):
    """SEC-AUTH-03: Invalid Bearer format rejected."""
    test_cases = [
        ('Basic abc123', 'Wrong auth scheme'),
        ('Bearer', 'Missing token'),
        ('sk-anova-key', 'No Bearer prefix'),
        ('', 'Empty header'),
    ]

    for auth_value, description in test_cases:
        response = secure_client.post(
            '/start-cook',
            headers={'Authorization': auth_value},
            json={'temperature_celsius': 65.0, 'time_minutes': 90}
        )
        assert response.status_code == 401, \
            f"Failed to reject: {description}"
        data = response.get_json()
        assert data['error'] == 'UNAUTHORIZED'

def test_sec_auth_04_invalid_api_key(secure_client):
    """SEC-AUTH-04: Invalid API key rejected."""
    response = secure_client.post(
        '/start-cook',
        headers={'Authorization': 'Bearer sk-anova-WRONG-KEY'},
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data['error'] == 'UNAUTHORIZED'
    assert data['message'] == 'Invalid API key'
    # Verify message doesn't reveal correct key
    assert 'sk-anova-test-security-key' not in data['message']

def test_sec_auth_05_case_sensitive(secure_client, valid_api_key):
    """SEC-AUTH-05: API key comparison is case-sensitive."""
    # Correct case should work
    response = secure_client.post(
        '/start-cook',
        headers={'Authorization': f'Bearer {valid_api_key}'},
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code != 401

    # Wrong case should fail
    wrong_case = valid_api_key.swapcase()
    response = secure_client.post(
        '/start-cook',
        headers={'Authorization': f'Bearer {wrong_case}'},
        json={'temperature_celsius': 65.0, 'time_minutes': 90}
    )
    assert response.status_code == 401

def test_sec_auth_06_all_endpoints_protected(secure_client):
    """SEC-AUTH-06: All endpoints except /health require auth."""
    # /health should be public
    response = secure_client.get('/health')
    assert response.status_code == 200

    # All other endpoints should require auth
    protected_endpoints = [
        ('POST', '/start-cook', {'temperature_celsius': 65, 'time_minutes': 90}),
        ('GET', '/status', None),
        ('POST', '/stop-cook', None),
    ]

    for method, endpoint, json_data in protected_endpoints:
        if method == 'POST':
            response = secure_client.post(endpoint, json=json_data)
        else:
            response = secure_client.get(endpoint)

        assert response.status_code == 401, \
            f"{method} {endpoint} should require authentication"
```

---

### 9.4 Running Security Tests

```bash
# Run all security tests
pytest tests/security/ -v

# Run specific category
pytest tests/security/test_authentication.py -v

# Run with coverage
pytest tests/security/ --cov=server.middleware --cov-report=html

# Run timing tests (verbose output for debugging)
pytest tests/security/test_timing_attacks.py -v -s

# Run security tests in CI (fail fast)
pytest tests/security/ -x --tb=short

# Generate security test report
pytest tests/security/ --html=security-report.html --self-contained-html
```

---

## 10. Continuous Security Testing

### 10.1 GitHub Actions Integration

**File:** `.github/workflows/security-tests.yml`

```yaml
name: Security Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    # Run weekly on Mondays at 9am UTC
    - cron: '0 9 * * 1'

jobs:
  security-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run Security Tests
        run: |
          pytest tests/security/ -v --tb=short
        env:
          # Test credentials (not real)
          ANOVA_EMAIL: test@example.com
          ANOVA_PASSWORD: test-password
          DEVICE_ID: test-device-id
          API_KEY: sk-anova-test-key

      - name: Run Bandit Security Linter
        run: |
          bandit -r server/ -f json -o bandit-report.json
          bandit -r server/ -ll  # Show high/medium issues
        continue-on-error: true

      - name: Check Dependencies for Vulnerabilities
        run: |
          safety check --json > safety-report.json
          safety check --continue-on-error

      - name: Upload Security Reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
            htmlcov/

      - name: Fail on Security Issues
        run: |
          # Fail if any CRITICAL security tests failed
          pytest tests/security/ --tb=no -q
```

---

### 10.2 Pre-Commit Hooks

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: security-tests
        name: Security Tests
        entry: pytest tests/security/ -x --tb=short
        language: system
        pass_filenames: false
        always_run: true

      - id: bandit
        name: Bandit Security Linter
        entry: bandit -r server/ -ll
        language: system
        pass_filenames: false

      - id: detect-secrets
        name: Detect Secrets
        entry: detect-secrets scan
        language: system
        pass_filenames: false
```

**Setup:**
```bash
pip install pre-commit
pre-commit install
```

---

## 11. Traceability Matrix

### 11.1 Security Requirements to Tests Mapping

| Requirement | Description | Tests | Priority | OWASP Category |
|-------------|-------------|-------|----------|----------------|
| SEC-REQ-01 | API key authentication | SEC-AUTH-01 through SEC-AUTH-06 | CRITICAL | A01:2021 - Broken Access Control |
| SEC-REQ-02 | Credentials encrypted at rest | (Implementation verification, not test-automated) | CRITICAL | A02:2021 - Cryptographic Failures |
| SEC-REQ-03 | HTTPS only | SEC-TLS-01, SEC-TLS-02 | HIGH | A02:2021 - Cryptographic Failures |
| SEC-REQ-04 | Food safety validation enforced | SEC-VAL-01, SEC-VAL-02, SEC-VAL-03 | CRITICAL | A03:2021 - Injection |
| SEC-REQ-05 | No credentials in logs | SEC-CRED-01, SEC-CRED-02, SEC-CRED-03, SEC-CRED-04, SEC-CRED-05 | CRITICAL | A01:2021 - Broken Access Control |
| SEC-REQ-06 | Timing attack resistance | SEC-TIME-01, SEC-TIME-02, SEC-TIME-03, SEC-TIME-04 | HIGH | A02:2021 - Cryptographic Failures |

---

### 11.2 Threat to Mitigation to Test Mapping

| Threat ID | Threat | Mitigation | Verification Test |
|-----------|--------|------------|-------------------|
| THR-01 | Unauthorized API access | API key authentication | SEC-AUTH-01 through SEC-AUTH-06 |
| THR-02 | Timing attacks | Constant-time comparison | SEC-TIME-01 through SEC-TIME-04 |
| THR-03 | Credential exposure | Log sanitization | SEC-CRED-01 through SEC-CRED-05 |
| THR-04 | Food safety bypass | Server-side validation | SEC-VAL-01 through SEC-VAL-03 |
| THR-05 | MITM attacks | HTTPS enforcement | SEC-TLS-01, SEC-TLS-02 |
| THR-06 | Information disclosure | Generic error messages | SEC-INFO-01 through SEC-INFO-04 |

---

### 11.3 Test Coverage Summary

| Category | Test Count | Priority | Coverage |
|----------|-----------|----------|----------|
| Authentication Security | 6 | CRITICAL | SEC-AUTH-01 to SEC-AUTH-06 |
| Timing Attack Resistance | 4 | HIGH | SEC-TIME-01 to SEC-TIME-04 |
| Credential Security | 5 | CRITICAL | SEC-CRED-01 to SEC-CRED-05 |
| Input Validation Security | 3 | CRITICAL | SEC-VAL-01 to SEC-VAL-03 |
| Information Disclosure | 4 | HIGH | SEC-INFO-01 to SEC-INFO-04 |
| Transport Security | 2 | HIGH | SEC-TLS-01 to SEC-TLS-02 |
| **Total** | **24** | | |

---

## 12. Security Test Maintenance

### 12.1 When to Update Security Tests

Security tests should be updated when:

**Code Changes:**
- [ ] New authentication mechanism added
- [ ] New endpoints added (verify auth required)
- [ ] Validation logic modified
- [ ] Error handling changed
- [ ] Logging changes made

**Security Incidents:**
- [ ] Vulnerability discovered in production
- [ ] Penetration test findings
- [ ] Security audit recommendations
- [ ] CVE reported in dependencies

**External Changes:**
- [ ] OWASP Top 10 updated
- [ ] New attack vectors published
- [ ] Regulatory requirements change
- [ ] Industry best practices evolve

**Scheduled:**
- [ ] Quarterly security test review
- [ ] Annual penetration test
- [ ] Dependency vulnerability scan (weekly via CI)

---

### 12.2 Security Test Review Checklist

**Perform quarterly review:**

#### Authentication & Authorization
- [ ] All endpoints have authentication tests
- [ ] New endpoints added to SEC-AUTH-06
- [ ] API key format still matches tests
- [ ] Timing attack tests still pass with current implementation

#### Credential Management
- [ ] New credentials added to leak detection (SEC-CRED-01)
- [ ] New log statements checked for credential leakage
- [ ] Error messages reviewed for information disclosure

#### Input Validation
- [ ] Food safety limits still match specification
- [ ] New input fields have validation tests
- [ ] Bypass attempts updated with new attack techniques

#### Dependencies
- [ ] `safety check` passes (no known vulnerabilities)
- [ ] `bandit` scan passes (no new security issues)
- [ ] Dependencies up to date

#### Documentation
- [ ] Security test documentation updated
- [ ] New threats added to threat model
- [ ] Incident response plan reviewed

---

### 12.3 Regression Testing for Security

**When security bugs are fixed:**

1. **Document the bug:**
   - Create ADR (Architecture Decision Record)
   - Document root cause
   - Document fix

2. **Create regression test:**
   - Add test that would have caught the bug
   - Verify test fails without fix
   - Verify test passes with fix

3. **Update security checklist:**
   - Add item to prevent recurrence
   - Update deployment checklist if relevant

**Example:**
```python
def test_sec_regression_001_api_key_leak_in_error():
    """
    Regression test for incident SEC-INC-2026-001.

    Bug: Error message echoed provided API key back to client.
    Fix: Changed error message to generic "Invalid API key".

    This test ensures the bug doesn't reoccur.
    """
    response = client.post(
        '/start-cook',
        headers={'Authorization': 'Bearer sk-anova-attacker-key'},
        json={'temperature_celsius': 65, 'time_minutes': 90}
    )

    assert response.status_code == 401
    data = response.get_json()

    # CRITICAL: Error message must not contain provided key
    assert 'sk-anova-attacker-key' not in str(data), \
        "SECURITY REGRESSION: API key leaked in error message (SEC-INC-2026-001)"
```

---

### 12.4 Security Metrics Dashboard

**Track these metrics over time:**

| Metric | Target | Frequency | Owner |
|--------|--------|-----------|-------|
| Security tests passing | 100% | Every commit | CI/CD |
| Timing attack tests passing | 100% | Every commit | CI/CD |
| Credential leak tests passing | 100% | Every commit | CI/CD |
| Known vulnerabilities in dependencies | 0 critical, 0 high | Weekly | CI/CD |
| Bandit security issues | 0 high, 0 medium | Every commit | CI/CD |
| Time to fix critical security bug | < 24 hours | Per incident | Team |
| Security test coverage | > 80% | Monthly | Team |

---

## 13. Appendices

### Appendix A: Security Testing Glossary

| Term | Definition |
|------|------------|
| **Constant-time comparison** | Algorithm that takes the same time regardless of input, preventing timing attacks |
| **Timing attack** | Exploiting timing differences to learn secrets (e.g., correct password length) |
| **Information disclosure** | Unintentional revelation of sensitive data through errors, logs, or responses |
| **Credential leakage** | Exposure of credentials (passwords, API keys) through logs, errors, or responses |
| **Effect size (Cohen's d)** | Statistical measure of difference magnitude between two groups |
| **p-value** | Probability that observed difference is due to chance (< 0.05 = significant) |
| **False positive** | Test incorrectly flags secure code as vulnerable |
| **False negative** | Test incorrectly passes vulnerable code as secure |

---

### Appendix B: Related Documents

- **02-Security Architecture** - Security requirements and threat model
- **03-Component Architecture** - Component design and security boundaries
- **05-API Specification** - API contract and error codes
- **09-Integration Test Specification** - Functional testing approach
- **CLAUDE.md** - Implementation patterns and anti-patterns

---

### Appendix C: Security Contact Information

**For security incidents or questions:**

- **Project Owner:** [Add contact info]
- **Security Incident Reporting:** [Add process]
- **External Security Researchers:** [Add responsible disclosure process]

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Claude Code | Initial comprehensive security test specification |

---

**End of Document**
