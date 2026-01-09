# 05 - API Specification

> **Document Type:** API Specification (OpenAPI 3.0)  
> **Status:** Draft  
> **Version:** 2.0 (Merged)  
> **Last Updated:** 2025-01-08  
> **Depends On:** 01-System Context, 02-Security Architecture, 03-Component Architecture  
> **Blocks:** Implementation, Custom GPT Configuration

---

## 1. Overview

This document specifies the complete HTTP API for the Anova Control Server. The API enables ChatGPT (via Custom GPT Actions) to control an Anova Precision Cooker 3.0.

### 1.1 Design Principles

| Principle | Rationale |
|-----------|-----------|
| **RESTful** | Standard HTTP semantics for predictability |
| **JSON-only** | Single content type simplifies client/server |
| **Stateless** | Server maintains no session state; each request self-contained |
| **Fail-safe** | Invalid inputs rejected; errors don't affect device state |
| **Safety-first** | Food safety validation at API level, not just GPT |

### 1.2 Base URL

- **Development:** `https://{ngrok-subdomain}.ngrok.io`
- **Production:** `https://{tunnel-name}.cfargotunnel.com`

---

## 2. OpenAPI Specification

```yaml
openapi: 3.0.3
info:
  title: Anova Sous Vide Control API
  description: |
    API for controlling an Anova Precision Cooker 3.0 via ChatGPT Custom GPT.
    
    This API enforces food safety rules at the server level. Requests with
    unsafe parameters will be rejected with detailed error messages.
    
    ## Food Safety Rules
    - Temperature must be between 40°C and 100°C
    - Poultry requires minimum 57°C (with extended time) or 65°C (standard)
    - Ground meat requires minimum 60°C
    
    ## Authentication
    All endpoints except /health require API key authentication via Bearer token.
  version: 1.0.0
  contact:
    name: System Administrator

servers:
  - url: https://{tunnel-name}.cfargotunnel.com
    description: Production server (Cloudflare Tunnel)
  - url: https://{subdomain}.ngrok.io
    description: Development server (ngrok)

security:
  - bearerAuth: []

tags:
  - name: Cooking
    description: Control cooking operations
  - name: Status
    description: Monitor device status
  - name: Health
    description: Server health checks

paths:
  /start-cook:
    post:
      operationId: startCooking
      summary: Start a cooking session
      description: |
        Initiates a sous vide cooking session with specified temperature and duration.
        
        The device will:
        1. Begin heating water to target temperature
        2. Start the timer when target is reached
        3. Maintain temperature until timer completes
        
        **Food Safety Rules Enforced:**
        - Temperature must be 40-100°C
        - Poultry: minimum 57°C (extended time) or 65°C (standard)
        - Ground meat: minimum 60°C
        
        **Satisfies:** FR-01, FR-04, FR-05, FR-07, FR-08
      tags:
        - Cooking
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/StartCookRequest'
            examples:
              chicken:
                summary: Chicken breast (safe)
                value:
                  temperature_celsius: 65.0
                  time_minutes: 90
                  food_type: "chicken breast"
              steak_medium_rare:
                summary: Medium-rare steak
                value:
                  temperature_celsius: 54.0
                  time_minutes: 120
                  food_type: "ribeye steak"
              salmon:
                summary: Salmon fillet
                value:
                  temperature_celsius: 52.0
                  time_minutes: 45
                  food_type: "salmon"
      responses:
        '200':
          description: Cooking session started successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StartCookResponse'
              example:
                success: true
                message: "Started cooking at 65.0°C for 90 minutes. Water heating to target temperature."
                cook_id: "550e8400-e29b-41d4-a716-446655440000"
                device_state: "preheating"
                target_temp_celsius: 65.0
                time_minutes: 90
                estimated_completion: "2025-01-08T14:30:00Z"
        '400':
          description: Invalid parameters (validation failed)
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              examples:
                temp_too_low:
                  summary: Temperature in danger zone
                  value:
                    error: "TEMPERATURE_TOO_LOW"
                    message: "Temperature 35.0°C is below the safe minimum of 40.0°C. Food below this temperature is in the bacterial danger zone."
                poultry_unsafe:
                  summary: Poultry temperature too low
                  value:
                    error: "POULTRY_TEMP_UNSAFE"
                    message: "Temperature 55.0°C is not safe for poultry. Minimum is 57.0°C with extended time (3+ hours) or 65.0°C for standard cooking."
                ground_meat_unsafe:
                  summary: Ground meat temperature too low
                  value:
                    error: "GROUND_MEAT_TEMP_UNSAFE"
                    message: "Temperature 55.0°C is not safe for ground meat. Minimum is 60.0°C because bacteria are mixed throughout."
        '401':
          $ref: '#/components/responses/Unauthorized'
        '409':
          description: Device already cooking
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: "DEVICE_BUSY"
                message: "Device already has an active cooking session. Stop the current cook first, or wait for it to complete."
        '503':
          $ref: '#/components/responses/DeviceOffline'

  /status:
    get:
      operationId: getStatus
      summary: Get current cooking status
      description: |
        Returns the current state of the Anova device including:
        - Current water temperature
        - Target temperature (if cooking)
        - Time remaining (if cooking)
        - Device state (idle, preheating, cooking, done)
        
        **Satisfies:** FR-02, FR-06
      tags:
        - Status
      responses:
        '200':
          description: Current device status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StatusResponse'
              examples:
                idle:
                  summary: Device idle
                  value:
                    device_online: true
                    state: "idle"
                    current_temp_celsius: 22.5
                    target_temp_celsius: null
                    time_remaining_minutes: null
                    time_elapsed_minutes: null
                    is_running: false
                preheating:
                  summary: Device preheating
                  value:
                    device_online: true
                    state: "preheating"
                    current_temp_celsius: 45.2
                    target_temp_celsius: 54.0
                    time_remaining_minutes: null
                    time_elapsed_minutes: null
                    is_running: true
                cooking:
                  summary: Device cooking
                  value:
                    device_online: true
                    state: "cooking"
                    current_temp_celsius: 54.0
                    target_temp_celsius: 54.0
                    time_remaining_minutes: 87
                    time_elapsed_minutes: 33
                    is_running: true
                done:
                  summary: Cook complete
                  value:
                    device_online: true
                    state: "done"
                    current_temp_celsius: 54.0
                    target_temp_celsius: 54.0
                    time_remaining_minutes: 0
                    time_elapsed_minutes: 120
                    is_running: false
        '401':
          $ref: '#/components/responses/Unauthorized'
        '503':
          $ref: '#/components/responses/DeviceOffline'

  /stop-cook:
    post:
      operationId: stopCooking
      summary: Stop current cooking session
      description: |
        Stops the current cooking session. The device will stop heating
        but water temperature will naturally decrease.
        
        **Behavior:**
        - If cooking: stops heating, returns success
        - If idle: returns NO_ACTIVE_COOK error (409)
        
        **Satisfies:** FR-03, FR-06
      tags:
        - Cooking
      responses:
        '200':
          description: Cooking stopped successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StopCookResponse'
              example:
                success: true
                message: "Cooking stopped"
                device_state: "idle"
                final_temp_celsius: 54.0
        '401':
          $ref: '#/components/responses/Unauthorized'
        '409':
          description: No active cooking session
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                error: "NO_ACTIVE_COOK"
                message: "No active cooking session to stop."
        '503':
          $ref: '#/components/responses/DeviceOffline'

  /health:
    get:
      operationId: healthCheck
      summary: Health check endpoint
      description: |
        Returns server health status. Does not require device connectivity.
        Used for uptime monitoring.
        
        **No authentication required.**
        
        **Satisfies:** QR-10
      tags:
        - Health
      security: []  # No auth required
      responses:
        '200':
          description: Server is healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
              example:
                status: "ok"
                version: "1.0.0"
                timestamp: "2025-01-08T12:00:00Z"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: API Key
      description: |
        API key authentication.
        Include in Authorization header: `Authorization: Bearer sk-anova-xxxxx`

  schemas:
    StartCookRequest:
      type: object
      required:
        - temperature_celsius
        - time_minutes
      properties:
        temperature_celsius:
          type: number
          format: float
          minimum: 40.0
          maximum: 100.0
          description: |
            Target water temperature in Celsius.
            
            **Safety limits:**
            - Absolute minimum: 40°C (danger zone)
            - Absolute maximum: 100°C (water boils)
            - Poultry minimum: 57°C (with 3+ hours) or 65°C
            - Ground meat minimum: 60°C
          example: 65.0
        time_minutes:
          type: integer
          minimum: 1
          maximum: 5999
          description: |
            Cooking duration in minutes.
            Maximum is 5999 minutes (99h 59m) per device limit.
            Timer starts when water reaches target temperature.
          example: 90
        food_type:
          type: string
          maxLength: 100
          description: |
            Optional description of food being cooked.
            Used for food-specific safety validation.
            Include keywords like "chicken", "ground beef", etc.
          example: "chicken breast"

    StartCookResponse:
      type: object
      required:
        - success
        - cook_id
        - device_state
        - target_temp_celsius
        - time_minutes
      properties:
        success:
          type: boolean
          example: true
        message:
          type: string
          description: Human-readable status message
          example: "Started cooking at 65.0°C for 90 minutes. Water heating to target temperature."
        cook_id:
          type: string
          format: uuid
          description: Unique identifier for this cooking session
          example: "550e8400-e29b-41d4-a716-446655440000"
        device_state:
          type: string
          enum: [preheating, cooking]
          example: "preheating"
        target_temp_celsius:
          type: number
          format: float
          example: 65.0
        time_minutes:
          type: integer
          example: 90
        estimated_completion:
          type: string
          format: date-time
          description: ISO 8601 timestamp of estimated completion
          example: "2025-01-08T14:30:00Z"

    StatusResponse:
      type: object
      required:
        - device_online
        - state
        - current_temp_celsius
      properties:
        device_online:
          type: boolean
          description: Whether device is reachable
          example: true
        state:
          type: string
          enum: [idle, preheating, cooking, done, unknown]
          description: |
            Current device state:
            - `idle`: Device is off, not cooking
            - `preheating`: Heating water to target temperature
            - `cooking`: At temperature, timer running
            - `done`: Timer complete, maintaining temperature
            - `unknown`: Could not determine state
          example: "cooking"
        current_temp_celsius:
          type: number
          description: Current water temperature
          example: 54.0
        target_temp_celsius:
          type: number
          nullable: true
          description: Target temperature (null if idle)
          example: 54.0
        time_remaining_minutes:
          type: integer
          nullable: true
          description: Minutes remaining on timer (null if not timing)
          example: 87
        time_elapsed_minutes:
          type: integer
          nullable: true
          description: Minutes elapsed since timer started
          example: 33
        is_running:
          type: boolean
          description: Whether device is actively heating/cooking
          example: true

    StopCookResponse:
      type: object
      required:
        - success
        - device_state
      properties:
        success:
          type: boolean
          example: true
        message:
          type: string
          example: "Cooking stopped"
        device_state:
          type: string
          enum: [idle]
          example: "idle"
        final_temp_celsius:
          type: number
          nullable: true
          description: Temperature at time of stop
          example: 54.0

    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [ok, degraded]
          description: Server health status
          example: "ok"
        version:
          type: string
          description: API version
          example: "1.0.0"
        timestamp:
          type: string
          format: date-time
          description: Current server time (ISO 8601)
          example: "2025-01-08T12:00:00Z"

    ErrorResponse:
      type: object
      required:
        - error
        - message
      properties:
        error:
          type: string
          description: Error code for programmatic handling
          example: "TEMPERATURE_TOO_LOW"
        message:
          type: string
          description: Human-readable error with actionable guidance
          example: "Temperature 35.0°C is below the safe minimum of 40.0°C."

  responses:
    Unauthorized:
      description: Authentication failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error: "UNAUTHORIZED"
            message: "Missing or invalid Authorization header"

    DeviceOffline:
      description: Device is not connected
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error: "DEVICE_OFFLINE"
            message: "Device is offline or not connected to WiFi. Please check that the Anova is plugged in and connected to your WiFi network."
```

---

## 3. Error Code Specification

### 3.1 Client Errors (4xx)

| Error Code | HTTP Status | Condition | Message Template | Recovery Action |
|------------|-------------|-----------|------------------|-----------------|
| MISSING_BODY | 400 | No request body | "Request body is required" | Add JSON body |
| MISSING_TEMPERATURE | 400 | temperature_celsius missing | "temperature_celsius is required" | Add field |
| MISSING_TIME | 400 | time_minutes missing | "time_minutes is required" | Add field |
| INVALID_TEMPERATURE | 400 | Not a number | "temperature_celsius must be a number" | Fix type |
| INVALID_TIME | 400 | Not an integer | "time_minutes must be a number" | Fix type |
| TEMPERATURE_TOO_LOW | 400 | temp < 40°C | "Temperature {X}°C is below the safe minimum of 40.0°C. Food below this temperature is in the bacterial danger zone." | Increase temp |
| TEMPERATURE_TOO_HIGH | 400 | temp > 100°C | "Temperature {X}°C exceeds the safe maximum of 100.0°C. Water boils at 100°C." | Decrease temp |
| TIME_TOO_SHORT | 400 | time < 1 | "Time must be at least 1 minute" | Increase time |
| TIME_TOO_LONG | 400 | time > 5999 | "Time {X} minutes exceeds maximum of 5999 minutes (99h 59m)" | Decrease time |
| POULTRY_TEMP_UNSAFE | 400 | poultry AND temp < 57°C | "Temperature {X}°C is not safe for poultry. Minimum is 57.0°C with extended time (3+ hours) or 65.0°C for standard cooking." | Increase temp |
| GROUND_MEAT_TEMP_UNSAFE | 400 | ground meat AND temp < 60°C | "Temperature {X}°C is not safe for ground meat. Minimum is 60.0°C because bacteria are mixed throughout." | Increase temp |
| UNAUTHORIZED | 401 | Invalid API key | "Missing or invalid Authorization header" | Fix API key |
| DEVICE_BUSY | 409 | Device already cooking | "Device already has an active cooking session. Stop the current cook first, or wait for it to complete." | Stop first |
| NO_ACTIVE_COOK | 409 | Stop when idle | "No active cooking session to stop." | No action needed |

### 3.2 Server Errors (5xx)

| Error Code | HTTP Status | Condition | Message Template | Recovery Action |
|------------|-------------|-----------|------------------|-----------------|
| DEVICE_OFFLINE | 503 | Device not connected | "Device is offline or not connected to WiFi. Please check that the Anova is plugged in and connected to your WiFi network." | Check device WiFi |
| AUTH_FAILED | 502 | Anova auth failed | "Failed to authenticate with Anova. Please verify credentials." | Check credentials |
| ANOVA_API_ERROR | 502 | Anova returned error | "Anova API error: {details}" | Retry; contact admin |
| NETWORK_ERROR | 503 | Network issue | "Network error communicating with Anova" | Retry later |
| TIMEOUT | 503 | Request timed out | "Request to Anova timed out" | Retry |
| INTERNAL_ERROR | 500 | Unexpected error | "An unexpected error occurred" | Contact admin |

---

## 4. Response Time Requirements

| Endpoint | Target (p50) | Target (p95) | Target (p99) | Test Method |
|----------|--------------|--------------|--------------|-------------|
| POST /start-cook | < 1s | < 2s | < 5s | Load test with mock Anova |
| GET /status | < 500ms | < 1s | < 2s | Load test with mock Anova |
| POST /stop-cook | < 1s | < 2s | < 5s | Load test with mock Anova |
| GET /health | < 100ms | < 200ms | < 500ms | Load test (no external calls) |

**ChatGPT Constraint:** All endpoints must complete within ~30 seconds (ChatGPT action timeout).

---

## 5. Rate Limiting Specification

| Endpoint | Rate Limit | Window | Exceeded Response |
|----------|------------|--------|-------------------|
| POST /start-cook | 10 requests | 1 minute | 429 Too Many Requests |
| GET /status | 60 requests | 1 minute | 429 Too Many Requests |
| POST /stop-cook | 10 requests | 1 minute | 429 Too Many Requests |
| GET /health | 120 requests | 1 minute | 429 Too Many Requests |

**Justification:** These limits prevent accidental loops from ChatGPT while allowing normal interactive use. Status can be polled more frequently for progress updates.

**429 Response Format:**
```json
{
  "error": "RATE_LIMITED",
  "message": "Too many requests. Please wait before retrying.",
  "retry_after_seconds": 30
}
```

---

## 6. Idempotency Specification

| Endpoint | Idempotent | Behavior on Duplicate Call |
|----------|------------|---------------------------|
| POST /start-cook | No | Returns DEVICE_BUSY (409) if already cooking |
| GET /status | Yes | Same response for same device state |
| POST /stop-cook | No | First call stops; subsequent return NO_ACTIVE_COOK (409) |
| GET /health | Yes | Same response for same server state |

---

## 7. Concurrency Specification

| Scenario | Expected Behavior | Test Method |
|----------|-------------------|-------------|
| Simultaneous /start-cook requests | First succeeds, second gets DEVICE_BUSY | Send 2 requests within 100ms |
| /status during /start-cook | Both complete; status may show transitional state | Concurrent request test |
| /stop-cook during /start-cook | Stop takes precedence; final state is idle | Race condition test |

---

## 8. Data Validation Rules

### 8.1 Temperature Validation

| Rule ID | Rule | Rationale |
|---------|------|-----------|
| VAL-T01 | 40.0 ≤ temperature ≤ 100.0 | Below 40°C is danger zone; above 100°C water boils |
| VAL-T02 | Precision: 0.1°C | Anova device precision limit |
| VAL-T03 | Type: float or integer | Accept both "65" and "65.0" |
| VAL-T04 | Poultry: temp ≥ 57.0°C | Minimum for pasteurization |
| VAL-T05 | Ground meat: temp ≥ 60.0°C | Bacteria throughout |

### 8.2 Time Validation

| Rule ID | Rule | Rationale |
|---------|------|-----------|
| VAL-TM01 | 1 ≤ time_minutes ≤ 5999 | Minimum useful cook; max 99h 59m |
| VAL-TM02 | Type: integer | No fractional minutes |
| VAL-TM03 | Truncate floats to integer | 90.7 → 90 |

### 8.3 String Validation

| Rule ID | Rule | Rationale |
|---------|------|-----------|
| VAL-S01 | food_type max 100 chars | Prevent abuse |
| VAL-S02 | Strip leading/trailing whitespace | Normalization |
| VAL-S03 | Reject null bytes | Security |

---

## 9. Test Scenarios

### 9.1 POST /start-cook Tests

| Test ID | Scenario | Input | Expected Output | Validates |
|---------|----------|-------|-----------------|-----------|
| TC-SC-01 | Valid chicken cook | temp=65, time=90, food="chicken" | 200, success=true, state=preheating | FR-01 |
| TC-SC-02 | Temperature too low | temp=35, time=60 | 400, error=TEMPERATURE_TOO_LOW | FR-04 |
| TC-SC-03 | Temperature too high | temp=105, time=60 | 400, error=TEMPERATURE_TOO_HIGH | FR-04 |
| TC-SC-04 | Temperature at minimum boundary | temp=40, time=60 | 200, success=true | FR-04 |
| TC-SC-05 | Temperature at maximum boundary | temp=100, time=60 | 200, success=true | FR-04 |
| TC-SC-06 | Time zero | temp=65, time=0 | 400, error=TIME_TOO_SHORT | FR-05 |
| TC-SC-07 | Time negative | temp=65, time=-10 | 400, error=TIME_TOO_SHORT | FR-05 |
| TC-SC-08 | Time at maximum boundary | temp=65, time=5999 | 200, success=true | FR-05 |
| TC-SC-09 | Time exceeds maximum | temp=65, time=6000 | 400, error=TIME_TOO_LONG | FR-05 |
| TC-SC-10 | Device offline | temp=65, time=90 | 503, error=DEVICE_OFFLINE | FR-06 |
| TC-SC-11 | Device already cooking | temp=65, time=90 | 409, error=DEVICE_BUSY | FR-01 |
| TC-SC-12 | Missing temperature | time=90 | 400, error=MISSING_TEMPERATURE | FR-04 |
| TC-SC-13 | Missing time | temp=65 | 400, error=MISSING_TIME | FR-05 |
| TC-SC-14 | Non-numeric temperature | temp="hot", time=90 | 400, error=INVALID_TEMPERATURE | FR-04 |
| TC-SC-15 | Float time (truncate) | temp=65, time=90.5 | 200, time_minutes=90 | FR-05 |
| TC-SC-16 | Poultry at 56°C | temp=56, time=90, food="chicken" | 400, error=POULTRY_TEMP_UNSAFE | FR-07 |
| TC-SC-17 | Poultry at 57°C | temp=57, time=180, food="chicken" | 200, success=true | FR-07 |
| TC-SC-18 | Ground meat at 59°C | temp=59, time=60, food="ground beef" | 400, error=GROUND_MEAT_TEMP_UNSAFE | FR-08 |
| TC-SC-19 | Ground meat at 60°C | temp=60, time=60, food="ground beef" | 200, success=true | FR-08 |
| TC-SC-20 | No auth header | temp=65, time=90 | 401, error=UNAUTHORIZED | QR-33 |

### 9.2 GET /status Tests

| Test ID | Scenario | Precondition | Expected Output | Validates |
|---------|----------|--------------|-----------------|-----------|
| TC-ST-01 | Device idle | No active cook | 200, state=idle, time_remaining=null | FR-02 |
| TC-ST-02 | Device heating | Cook started, not at temp | 200, state=preheating, current < target | FR-02 |
| TC-ST-03 | Device cooking | At temp, timer running | 200, state=cooking, time_remaining > 0 | FR-02 |
| TC-ST-04 | Cook complete | Timer finished | 200, state=done | FR-02 |
| TC-ST-05 | Device offline | Network disconnected | 503, error=DEVICE_OFFLINE | FR-06 |
| TC-ST-06 | Temperature accuracy | Device at 65.0°C | 200, current_temp ≈ 65.0 (±0.5) | QR-01 |

### 9.3 POST /stop-cook Tests

| Test ID | Scenario | Precondition | Expected Output | Validates |
|---------|----------|--------------|-----------------|-----------|
| TC-SP-01 | Stop active cook | Cook in progress | 200, success=true, state=idle | FR-03 |
| TC-SP-02 | Stop when idle | No active cook | 409, error=NO_ACTIVE_COOK | FR-03 |
| TC-SP-03 | Device offline | Network disconnected | 503, error=DEVICE_OFFLINE | FR-06 |
| TC-SP-04 | Stop returns final state | Cook at 65°C | 200, final_temp ≈ 65 | FR-03 |

### 9.4 GET /health Tests

| Test ID | Scenario | Precondition | Expected Output | Validates |
|---------|----------|--------------|-----------------|-----------|
| TC-HE-01 | Server healthy | Server running | 200, status=ok | QR-10 |
| TC-HE-02 | Response time | - | Response < 500ms | QR-01 |
| TC-HE-03 | No auth required | No auth header | 200, status=ok | - |

---

## 10. Backward Compatibility Commitment

| Aspect | Commitment |
|--------|------------|
| Endpoint paths | Will not change in v1.x |
| Required request fields | Will not add new required fields in v1.x |
| Response fields | May add optional fields; will not remove existing |
| Error codes | May add new codes; will not change existing meanings |
| HTTP status codes | Stable for documented scenarios |

---

## 11. Request/Response Examples

### 11.1 Start Cooking - Success

**Request:**
```bash
curl -X POST https://anova-xxxxx.cfargotunnel.com/start-cook \
  -H "Authorization: Bearer sk-anova-xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature_celsius": 54.0,
    "time_minutes": 120,
    "food_type": "ribeye steak"
  }'
```

**Response (200):**
```json
{
  "success": true,
  "message": "Started cooking at 54.0°C for 120 minutes. Water heating to target temperature.",
  "cook_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_state": "preheating",
  "target_temp_celsius": 54.0,
  "time_minutes": 120,
  "estimated_completion": "2025-01-08T14:30:00Z"
}
```

### 11.2 Start Cooking - Food Safety Rejection

**Request:**
```bash
curl -X POST https://anova-xxxxx.cfargotunnel.com/start-cook \
  -H "Authorization: Bearer sk-anova-xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature_celsius": 50.0,
    "time_minutes": 90,
    "food_type": "chicken breast"
  }'
```

**Response (400):**
```json
{
  "error": "POULTRY_TEMP_UNSAFE",
  "message": "Temperature 50.0°C is not safe for poultry. Minimum is 57.0°C with extended time (3+ hours) or 65.0°C for standard cooking."
}
```

### 11.3 Status - Cooking in Progress

**Request:**
```bash
curl -X GET https://anova-xxxxx.cfargotunnel.com/status \
  -H "Authorization: Bearer sk-anova-xxxxx"
```

**Response (200):**
```json
{
  "device_online": true,
  "state": "cooking",
  "current_temp_celsius": 54.0,
  "target_temp_celsius": 54.0,
  "time_remaining_minutes": 87,
  "time_elapsed_minutes": 33,
  "is_running": true
}
```

### 11.4 Status - Device Offline

**Request:**
```bash
curl -X GET https://anova-xxxxx.cfargotunnel.com/status \
  -H "Authorization: Bearer sk-anova-xxxxx"
```

**Response (503):**
```json
{
  "error": "DEVICE_OFFLINE",
  "message": "Device is offline or not connected to WiFi. Please check that the Anova is plugged in and connected to your WiFi network."
}
```

---

## 12. ChatGPT Custom GPT Configuration

### 12.1 Actions Configuration

Copy the OpenAPI specification (Section 2) into the Custom GPT Actions configuration.

### 12.2 Authentication Setup

1. In Custom GPT Actions, select "API Key" authentication
2. Auth Type: Bearer
3. Enter your generated API key: `sk-anova-xxxxx`

### 12.3 Server URL

Update the `servers` section with your actual Cloudflare Tunnel URL:

```yaml
servers:
  - url: https://anova-abc123.cfargotunnel.com
```

---

## 13. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-08 | Claude | Initial draft |
| 2.0 | 2025-01-08 | Claude | Merged: rate limiting + performance targets + food safety + actionable errors |

---

## 14. Traceability Matrix

| Requirement | Endpoint | Test Cases |
|-------------|----------|------------|
| FR-01 | POST /start-cook | TC-SC-01, TC-SC-04, TC-SC-05, TC-SC-08, TC-SC-11 |
| FR-02 | GET /status | TC-ST-01 through TC-ST-06 |
| FR-03 | POST /stop-cook | TC-SP-01 through TC-SP-04 |
| FR-04 | POST /start-cook (validation) | TC-SC-02 through TC-SC-05, TC-SC-12, TC-SC-14 |
| FR-05 | POST /start-cook (validation) | TC-SC-06 through TC-SC-09, TC-SC-13, TC-SC-15 |
| FR-06 | All endpoints | TC-SC-10, TC-ST-05, TC-SP-03 |
| FR-07 | POST /start-cook (poultry) | TC-SC-16, TC-SC-17 |
| FR-08 | POST /start-cook (ground meat) | TC-SC-18, TC-SC-19 |
| QR-01 | All endpoints | Response time tests |
| QR-10 | GET /health | TC-HE-01 |
| QR-33 | All protected endpoints | TC-SC-20 |
