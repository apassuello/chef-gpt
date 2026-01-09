# 02 - Security Architecture

> **Document Type:** Security Architecture  
> **Status:** Draft  
> **Version:** 2.0 (Merged)  
> **Last Updated:** 2025-01-08  
> **Depends On:** 01-System Context  
> **Blocks:** 05-API Specification

---

## 1. Executive Summary

This document defines how the Anova AI Sous Vide Assistant handles authentication, authorization, and security. The core principle is **defense in depth**: credentials stay local, all inputs are validated, and security is enforced at multiple layers.

**Key Security Properties:**
- Anova credentials never leave the local server
- ChatGPT sees only cooking commands and status responses
- All API inputs are validated server-side (not just at GPT layer)
- Food safety rules are enforced as security controls

---

## 2. Security Objectives

| Objective ID | Objective | Priority | Rationale |
|--------------|-----------|----------|-----------|
| SEC-OBJ-01 | Protect Anova Credentials | Critical | Account compromise could affect user's other Anova devices |
| SEC-OBJ-02 | Prevent Unsafe Cooking Parameters | Critical | Food safety is a legal and health concern |
| SEC-OBJ-03 | Ensure System Availability | High | User depends on system for cooking |
| SEC-OBJ-04 | Maintain Privacy | High | Cooking habits should not be logged or shared |
| SEC-OBJ-05 | Prevent Unauthorized Access | Medium | Single-user system; ChatGPT is semi-trusted |

---

## 3. Credential Inventory

### 3.1 Secrets Managed by This System

| Secret ID | Secret | Purpose | Storage Location | Rotation Policy |
|-----------|--------|---------|------------------|-----------------|
| CRED-01 | Anova Email | Account identification | Server config file | When user changes it |
| CRED-02 | Anova Password | Account authentication | Server config file (encrypted) | When user changes it |
| CRED-03 | Firebase Access Token | API authentication | Memory only | Auto-refresh before expiry |
| CRED-04 | Firebase Refresh Token | Token renewal | Memory or encrypted file | Long-lived; refresh as needed |
| CRED-05 | API Key | ChatGPT authentication | Server config file | Manually if compromised |

### 3.2 Secrets NOT Managed by This System

| Secret | Owner | Notes |
|--------|-------|-------|
| OpenAI API Key | OpenAI/User | Not needed; using Custom GPT |
| Cloudflare API Token | Admin | Only used for tunnel setup |
| SSH Keys | Admin | For server access only |

---

## 4. Authentication Flows

### 4.1 Overall Authentication Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATION ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   ChatGPT    │      │  Anova Control   │      │   Anova Cloud    │
│   Platform   │      │     Server       │      │   (Firebase)     │
└──────┬───────┘      └────────┬─────────┘      └────────┬─────────┘
       │                       │                         │
       │  1. API Request       │                         │
       │  (Bearer API key)     │                         │
       │──────────────────────►│                         │
       │                       │                         │
       │                       │  2. Check token cache   │
       │                       │  ┌───────────────────┐  │
       │                       │  │ Token valid?      │  │
       │                       │  │ Yes → Use it      │  │
       │                       │  │ No → Refresh/Auth │  │
       │                       │  └───────────────────┘  │
       │                       │                         │
       │                       │  3. If needed: Auth     │
       │                       │─────────────────────────►
       │                       │  (email/password)       │
       │                       │                         │
       │                       │  4. Receive tokens      │
       │                       │◄─────────────────────────
       │                       │  (access + refresh)     │
       │                       │                         │
       │                       │  5. API call with token │
       │                       │─────────────────────────►
       │                       │  Authorization: Bearer  │
       │                       │                         │
       │                       │  6. Response            │
       │                       │◄─────────────────────────
       │                       │                         │
       │  7. Formatted response│                         │
       │◄──────────────────────│                         │
       │                       │                         │
```

### 4.2 Firebase Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FIREBASE AUTHENTICATION FLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Initial Authentication (on server startup or token expiry)
────────────────────────────────────────────────────────────────────

    Server                                     Firebase Auth
       │                                            │
       │  POST /identitytoolkit/v3/relyingparty/   │
       │       verifyPassword                       │
       │  {                                         │
       │    "email": "user@example.com",            │
       │    "password": "secret",                   │
       │    "returnSecureToken": true               │
       │  }                                         │
       │───────────────────────────────────────────►│
       │                                            │
       │  200 OK                                    │
       │  {                                         │
       │    "idToken": "eyJhbG...",                 │
       │    "refreshToken": "AGEh...",              │
       │    "expiresIn": "3600"                     │
       │  }                                         │
       │◄───────────────────────────────────────────│
       │                                            │

Step 2: Token Refresh (before idToken expires)
────────────────────────────────────────────────────────────────────

    Server                                     Firebase Auth
       │                                            │
       │  POST /v1/token                            │
       │  {                                         │
       │    "grant_type": "refresh_token",          │
       │    "refresh_token": "AGEh..."              │
       │  }                                         │
       │───────────────────────────────────────────►│
       │                                            │
       │  200 OK                                    │
       │  {                                         │
       │    "id_token": "eyJhbG...",                │
       │    "refresh_token": "AGEh...",             │
       │    "expires_in": "3600"                    │
       │  }                                         │
       │◄───────────────────────────────────────────│
       │                                            │
```

### 4.3 Token Lifecycle Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOKEN LIFECYCLE                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Server Starts   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
              ┌─────│  Token Cached?   │─────┐
              │     └──────────────────┘     │
              │ No                           │ Yes
              ▼                              ▼
     ┌──────────────────┐          ┌──────────────────┐
     │ Authenticate     │          │  Token Valid?    │
     │ (email/password) │          │  (check expiry)  │
     └────────┬─────────┘          └────────┬─────────┘
              │                             │
              │                    ┌────────┴────────┐
              │                    │ Yes             │ No
              │                    ▼                 ▼
              │           ┌──────────────┐  ┌──────────────────┐
              │           │  Use Token   │  │  Refresh Token   │
              │           └──────────────┘  └────────┬─────────┘
              │                                      │
              ▼                                      ▼
     ┌──────────────────┐                   ┌──────────────────┐
     │  Store Tokens    │                   │  Refresh Failed? │
     │  (memory/file)   │                   └────────┬─────────┘
     └────────┬─────────┘                           │
              │                            ┌────────┴────────┐
              │                            │ Yes             │ No
              │                            ▼                 ▼
              │                   ┌──────────────┐  ┌──────────────┐
              │                   │ Re-auth with │  │  Use New     │
              │                   │ credentials  │  │  Token       │
              │                   └──────────────┘  └──────────────┘
              │
              ▼
     ┌──────────────────────────────────────────────────────────┐
     │                    READY FOR API CALLS                   │
     └──────────────────────────────────────────────────────────┘
```

### 4.4 Token Storage Strategy

| Token Type | Storage Location | Persistence | Security |
|------------|------------------|-------------|----------|
| Access Token (idToken) | Memory | Process lifetime | Encrypted if persisted |
| Refresh Token | Encrypted file | Survives restart | AES-256 or OS keychain |
| Credentials (email/pwd) | Config file | Permanent | File permissions + encryption |

---

## 5. Credential Storage

### 5.1 Storage Options Evaluated

| Option | Security | Complexity | Recommendation |
|--------|----------|------------|----------------|
| Environment Variables | Medium | Low | ✓ Development |
| Encrypted Config File | High | Medium | ✓ Production |
| OS Keychain/Secret Store | Highest | High | Future enhancement |
| Plain Text Config | Low | Lowest | ✗ Never |

### 5.2 Recommended Approach: Encrypted Config File

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CREDENTIAL STORAGE (PRODUCTION)                          │
└─────────────────────────────────────────────────────────────────────────────┘

File: /home/pi/anova-assistant/config/credentials.enc

Encryption: AES-256-GCM
Key Derivation: PBKDF2 with device-specific salt

┌────────────────────────────────────────────────────────────────┐
│  credentials.enc (encrypted)                                   │
│                                                                │
│  Decrypts to:                                                  │
│  {                                                             │
│    "anova_email": "user@example.com",                          │
│    "anova_password": "user_password",                          │
│    "device_id": "abc123def456",                                │
│    "refresh_token": "AGEh..." (if persisted)                   │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘

Decryption Key: Derived from machine-specific identifier
                (MAC address, CPU serial, etc.)
                + admin-provided passphrase (optional)

File Permissions: 600 (owner read/write only)
Owner: pi (or dedicated service user)
```

### 5.3 Development vs. Production

| Environment | Storage Method | Notes |
|-------------|----------------|-------|
| Development | `.env` file + python-dotenv | Gitignored; simple |
| Production | Encrypted config file | Survives restarts; secure |

---

## 6. API Authentication (ChatGPT → Server)

### 6.1 Options Evaluated

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| No Auth | Simplest | Anyone with URL can control device | ✗ Not recommended |
| API Key in Header | Simple; ChatGPT supports it | Key management | ✓ Recommended |
| IP Allowlist | Very restrictive | OpenAI IPs change; hard to maintain | ✗ Impractical |
| OAuth 2.0 | Industry standard | Overkill for single-user | ✗ Over-engineered |

### 6.2 Recommended: API Key Authentication

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API KEY AUTHENTICATION                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Request from ChatGPT:
──────────────────────
POST /start-cook HTTP/1.1
Host: anova-xxxx.cfargotunnel.com
Authorization: Bearer sk-anova-xxxxxxxxxxxxx
Content-Type: application/json

{
    "temperature_celsius": 55.0,
    "time_minutes": 120
}

Server Validation:
──────────────────────
1. Extract Authorization header
2. Verify "Bearer " prefix
3. Compare key to stored value (constant-time comparison)
4. If mismatch → 401 Unauthorized
5. If match → Process request
```

### 6.3 API Key Generation

```bash
# Generate a secure API key (run once, store securely)
python -c "import secrets; print(f'sk-anova-{secrets.token_urlsafe(32)}')"

# Example output: sk-anova-7Kq3mN_xPz9rT2wL5vB8jC4hF6gD1aE0nM
```

### 6.4 ChatGPT Action Configuration

```yaml
# In Custom GPT Actions configuration:
security:
  - bearerAuth: []
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: API Key
```

---

## 7. Trust Model

### 7.1 Trust Levels

| Entity | Trust Level | What It Can Do | What It Cannot Do |
|--------|-------------|----------------|-------------------|
| End User | Low | Send natural language requests | Access server directly; modify config |
| ChatGPT | Partial | Call defined API endpoints | See credentials; bypass validation |
| Anova Server | Full | All operations; holds credentials | N/A (fully trusted) |
| Anova Cloud | Trusted | Control device; report status | Access our server's secrets |
| Admin | Full | All operations including credential access | N/A (fully trusted) |

### 7.2 What ChatGPT Can See

| Data Type | Visible to ChatGPT | Notes |
|-----------|-------------------|-------|
| Temperature requests | ✓ Yes | Part of normal operation |
| Time requests | ✓ Yes | Part of normal operation |
| Device status | ✓ Yes | Current temp, timer, state |
| Error messages | ✓ Yes | Actionable errors only |
| Anova email/password | ✗ Never | Stays on local server |
| Firebase tokens | ✗ Never | Stays on local server |
| API key | ✓ Yes (its own) | ChatGPT stores this to call us |

---

## 8. Threat Model

### 8.1 Threat Actors

| Actor ID | Actor | Motivation | Capability | Likelihood |
|----------|-------|------------|------------|------------|
| TA-01 | Internet Scanner | Find vulnerable services | Automated scanning | High |
| TA-02 | Opportunistic Attacker | Curiosity; mischief | Basic hacking skills | Medium |
| TA-03 | Targeted Attacker | Control specific device | Advanced skills | Low |
| TA-04 | Malicious User Input | Test boundaries | Natural language prompts | Medium |

### 8.2 STRIDE Threat Analysis

| Threat ID | Category | Description | Impact | Mitigation |
|-----------|----------|-------------|--------|------------|
| THR-01 | **S**poofing | Attacker impersonates ChatGPT | Unauthorized commands | API key authentication |
| THR-02 | **T**ampering | Modified requests in transit | Wrong cooking parameters | HTTPS only (Cloudflare) |
| THR-03 | **R**epudiation | User denies cooking action | Disputes over food safety | Logging (no personal data) |
| THR-04 | **I**nformation Disclosure | Credentials leaked | Account compromise | Encrypted storage; no logging of secrets |
| THR-05 | **D**enial of Service | Server overwhelmed | Can't control device | Rate limiting; fail-safe (use app) |
| THR-06 | **E**levation of Privilege | Attacker gains admin access | Full system compromise | SSH key auth only; no password login |

### 8.3 Threat Mitigations Detail

#### THR-01: Spoofing (Unauthorized API Access)
```
Threat: Attacker discovers Cloudflare URL and sends commands

Mitigations:
├── API Key required for all endpoints (except /health)
├── Key is 256-bit random value (infeasible to guess)
├── Constant-time comparison prevents timing attacks
├── Rate limiting on failed auth attempts
└── Cloudflare provides DDoS protection

Residual Risk: Low (if API key not leaked)
```

#### THR-04: Information Disclosure (Credential Leak)
```
Threat: Anova credentials exposed to unauthorized party

Mitigations:
├── Credentials stored encrypted at rest
├── Credentials never sent to ChatGPT
├── Credentials never written to logs
├── File permissions restrict access (600)
├── SSH key auth only (no password exposure)
└── Config file not in git repo

Detection:
├── Monitor for unexpected Anova app sessions
├── Check for credential change notifications from Anova
└── Review server logs for auth failures

Response:
├── Change Anova password immediately
├── Revoke refresh tokens
├── Generate new API key
└── Investigate leak source

Residual Risk: Low (with proper operational security)
```

---

## 9. Input Validation (Security Layer)

### 9.1 Validation Philosophy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEFENSE IN DEPTH: INPUT VALIDATION                       │
└─────────────────────────────────────────────────────────────────────────────┘

Layer 1: ChatGPT (Informative, not enforced)
─────────────────────────────────────────────
GPT instructions say "don't suggest unsafe temps"
BUT: GPT can hallucinate or be prompt-injected
NOT TRUSTED for enforcement

Layer 2: API Schema (First enforcement layer)
─────────────────────────────────────────────
OpenAPI schema defines types and ranges
Flask validates against schema
REJECTS malformed requests early

Layer 3: Business Logic (Final enforcement)
─────────────────────────────────────────────
Food safety rules checked in code
Additional contextual validation
FINAL authority on what's allowed
```

### 9.2 Food Safety Validation Rules (Security-Critical)

| Rule ID | Parameter | Condition | Action | Rationale |
|---------|-----------|-----------|--------|-----------|
| VAL-T01 | temperature_celsius | < 40.0 | REJECT | Below danger zone minimum |
| VAL-T02 | temperature_celsius | > 100.0 | REJECT | Above water boiling point |
| VAL-T03 | temperature_celsius | poultry AND < 57.0 | REJECT | Unsafe pasteurization |
| VAL-T04 | temperature_celsius | ground_meat AND < 60.0 | REJECT | Bacteria throughout |
| VAL-TM01 | time_minutes | < 1 | REJECT | Minimum useful time |
| VAL-TM02 | time_minutes | > 5999 | REJECT | Exceeds Anova limit |

### 9.3 Food Safety as Security Control

```python
# This is a SECURITY CONTROL, not just convenience
SAFETY_RULES = {
    "min_temp_absolute": 40.0,      # Below this: bacterial danger zone
    "max_temp_absolute": 100.0,     # Above this: water boils
    "poultry_min_temp": 57.0,       # With extended time
    "poultry_safe_temp": 65.0,      # Standard safe
    "ground_meat_min_temp": 60.0,   # Bacteria mixed throughout
}

def validate_safety(temp_c: float, time_min: int, food_type: str | None) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message)
    
    This function is a SECURITY BOUNDARY. It must:
    - Never be bypassed
    - Always fail-safe (reject if uncertain)
    - Log rejections for monitoring
    """
    # Implementation in 03-Component-Architecture
```

---

## 10. Logging and Monitoring

### 10.1 What to Log

| Event ID | Event | Log Level | Data Logged | Data NOT Logged |
|----------|-------|-----------|-------------|-----------------|
| LOG-01 | Server startup | INFO | Timestamp, version | - |
| LOG-02 | API request received | INFO | Endpoint, timestamp | Request body if contains secrets |
| LOG-03 | Auth failure | WARNING | Timestamp, IP (if available) | API key value |
| LOG-04 | Validation failure | WARNING | Parameter name, violation type | Actual value if sensitive |
| LOG-05 | Anova API error | ERROR | Error type, code | Tokens |
| LOG-06 | Cook started | INFO | Temp, time | User identity |
| LOG-07 | Cook stopped | INFO | Timestamp | - |

### 10.2 What NEVER to Log

| Data Type | Reason |
|-----------|--------|
| Anova email | Privacy |
| Anova password | Security |
| Firebase tokens | Security |
| API key | Security |
| Full request bodies | May contain sensitive data |

---

## 11. Security Requirements Traceability

| Security Req ID | Requirement | Implementation | Test |
|-----------------|-------------|----------------|------|
| SEC-REQ-01 | API key required for protected endpoints | middleware.py: require_api_key() | TC-AUTH-01 |
| SEC-REQ-02 | Credentials encrypted at rest | config.py: AES-256 encryption | TC-CRED-01 |
| SEC-REQ-03 | Credentials never logged | Logger filter excludes patterns | TC-LOG-01 |
| SEC-REQ-04 | HTTPS only | Cloudflare Tunnel configuration | TC-TLS-01 |
| SEC-REQ-05 | Food safety validation | validators.py: validate_safety() | TC-SAFE-01 through TC-SAFE-08 |
| SEC-REQ-06 | Constant-time key comparison | hmac.compare_digest() | TC-AUTH-02 |

---

## 12. Incident Response

### 12.1 Credential Compromise Response

```
IF: Anova credentials may be compromised

IMMEDIATE (within 1 hour):
1. Change Anova account password via official app
2. Revoke all Anova sessions if possible
3. Delete cached tokens on server
4. Restart server to force re-authentication

FOLLOW-UP (within 24 hours):
5. Generate new API key for ChatGPT
6. Update Custom GPT with new key
7. Review logs for unauthorized access
8. Investigate how compromise occurred
9. Document incident and lessons learned
```

### 12.2 Server Compromise Response

```
IF: Server may be compromised (SSH, malware, etc.)

IMMEDIATE:
1. Disconnect server from network (if physical access)
2. Change Anova password from another device
3. Revoke SSH keys

RECOVERY:
4. Wipe and reinstall Raspberry Pi OS
5. Redeploy from clean codebase
6. Generate new credentials and API key
7. Verify integrity before reconnecting

FOLLOW-UP:
8. Investigate compromise vector
9. Implement additional controls if needed
```

---

## 13. Security Checklist

### 13.1 Pre-Deployment Checklist

| Check ID | Check | Status |
|----------|-------|--------|
| SEC-CHK-01 | Credentials stored in encrypted file with 600 permissions | ☐ |
| SEC-CHK-02 | API key generated and stored securely | ☐ |
| SEC-CHK-03 | SSH password auth disabled (key only) | ☐ |
| SEC-CHK-04 | Cloudflare Tunnel configured with HTTPS | ☐ |
| SEC-CHK-05 | No secrets in git repository | ☐ |
| SEC-CHK-06 | Log files don't contain credentials (verify manually) | ☐ |
| SEC-CHK-07 | Food safety validation tested with edge cases | ☐ |

### 13.2 Ongoing Security Tasks

| Task | Frequency | Owner |
|------|-----------|-------|
| Review logs for anomalies | Weekly | Admin |
| Check for Anova API changes | Monthly | Admin |
| Rotate API key | Annually or if compromised | Admin |
| Verify file permissions | After any config change | Admin |

---

## 14. Architecture Decision Records (Security)

### ADR-SEC-001: API Key vs. No Auth

**Decision:** Require API key for all endpoints except `/health`

**Rationale:**
- Cloudflare URL is obscure but not secret
- Anyone who discovers URL could control device without auth
- API key adds meaningful barrier with minimal complexity
- ChatGPT Custom GPT supports Bearer token auth natively

**Trade-off:** Admin must manage API key; slight increase in complexity

### ADR-SEC-002: Encrypted Config vs. Environment Variables

**Decision:** Use encrypted config file in production; env vars in development

**Rationale:**
- Env vars don't persist reliably across reboots on Pi
- Encrypted file survives restarts
- Encryption key derived from hardware prevents theft via SD card
- Env vars simpler for development iteration

**Trade-off:** Additional implementation complexity for encryption

### ADR-SEC-003: No User Authentication

**Decision:** Single-user system; trust ChatGPT as user proxy

**Rationale:**
- Only one household uses this system
- ChatGPT requires user's OpenAI account
- Adding user auth to our server adds complexity without benefit
- If multi-user needed later, can add

**Trade-off:** Anyone with Custom GPT access can control device

---

## 15. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-08 | Claude | Initial draft |
| 2.0 | 2025-01-08 | Claude | Added formal IDs, traceability matrix |

---

## 16. Next Steps

With Security Architecture complete:

1. **05-API Specification** - Incorporate auth scheme from this document
2. **03-Component Architecture** - Define where auth logic lives
3. **Implementation** - Follow security controls defined here
