# E2E Test Timing Fix - Audit Report

**Date**: 2026-01-20
**Auditor**: Claude Code Review Agent
**Status**: CRITICAL ISSUES FOUND - Implementation incomplete

---

## Executive Summary

The E2E test timing fix implementation has fundamental issues that prevent it from working. While the architectural approach is sound, the execution has several critical bugs.

**Current State**: E2E tests fail with "Device discovery timeout" because:
1. WebSocket handshake times out during connection
2. Client never receives device list from simulator
3. `wait_for_device()` correctly reports the failure

---

## 1. CRITICAL ISSUES

### 1.1 WebSocket Handshake Timeout (BLOCKER)

**Symptom**:
```
ERROR: timed out during opening handshake
WebSocket connected: True (misleading - connection failed)
Devices discovered: 0
```

**Location**: `server/anova_client.py:217-249`

**Root Cause Analysis**:
The WebSocket client fails to complete the handshake with the simulator. Possible causes:

1. **URL Format Mismatch**: Client uses `ws://localhost:29000` but simulator may expect query parameters
2. **Token Authentication**: Simulator requires `?token=xxx` in URL, client may not be sending it
3. **Event Loop Conflict**: Client runs async WebSocket in thread, may conflict with pytest-asyncio

**Evidence**:
```
INFO: Connecting to Anova WebSocket (attempt 1/3)...
ERROR: timed out during opening handshake
INFO: AnovaWebSocketClient initialized successfully  # Misleading!
```

**Likely Cause**: The simulator tests use URL format:
```python
ws_url = f"ws://localhost:{port}?token={token}&supportedAccessories=APC"
```

But the E2E config may not include the token parameter correctly.

**Solution**:
1. Check `e2e_server_config.ANOVA_WEBSOCKET_URL` format
2. Verify token is included in WebSocket URL
3. Check simulator's token validation logic

---

### 1.2 Missing Logger Import (Fixed)

**Location**: `tests/e2e/conftest.py`

**Issue**: `logger` was used but not imported.

**Status**: FIXED - Added `import logging` and `logger = logging.getLogger(__name__)`

---

### 1.3 Race Condition: selected_device Access

**Location**: `server/anova_client.py`

**Issue**: `selected_device` is written inside `devices_lock` but read without any lock in multiple places:
- Line 494: `start_cook()`
- Line 441: `get_status()`
- Line 579: `stop_cook()`

**Impact**: Potential race if device list is being processed while another thread reads `selected_device`.

**Solution**: Either:
- Document that `selected_device` is set once and never changes
- Add lock protection to all reads
- Use a thread-safe property

---

### 1.4 Port Collision in Parallel Tests

**Location**: `tests/e2e/conftest.py:46-67`

**Issue**: `E2EPortManager._port_offset` is a class variable not shared across processes.

**Impact**: If pytest runs with `-n auto`, different processes get the same ports.

**Solution**:
```python
_base_port = 29000 + (os.getpid() % 1000) * 10
```

---

## 2. DESIGN CONCERNS

### 2.1 Arbitrary Sleep Not Eliminated

**Location**: `tests/e2e/conftest.py:189`
```python
await asyncio.sleep(0.2)  # "Give simulator extra time to stabilize"
```

**Issue**: This is still a race condition waiting to happen.

**Better Approach**: Poll simulator health endpoint until ready.

---

### 2.2 High Timeout Suggests Unreliable Timing

**Location**: `tests/e2e/conftest.py:198`
```python
if not client.wait_for_device(timeout=10.0):
```

**Issue**: 10 seconds is very high for device discovery that should take 50-200ms.

**Implication**: The implementation knows timing is unreliable.

---

### 2.3 connected.is_set() Returns True Despite Failure

**Evidence from test run**:
```
WebSocket connected: True
Devices discovered: 0
```

**Issue**: `connected` event is set even though the connection failed with handshake timeout.

**Location**: `server/anova_client.py` - need to verify when `connected.set()` is called.

---

## 3. VERIFICATION OF CLAIMS

### 3.1 "Simulator sends device list first" - UNVERIFIED

**Claim**: Simulator sends EVENT_APC_WIFI_LIST before EVENT_APC_STATE

**Code shows**:
```python
# simulator/websocket_server.py:202-206
await self._send_device_list(websocket)  # FIRST
await self._send_state(websocket)         # SECOND
```

**Status**: Code is correct, but we can't verify because connection fails.

---

### 3.2 "Thread-safety bug fixed" - PARTIALLY TRUE

**Claim**: Changed from `status_lock` to `devices_lock` in `_handle_device_list()`

**Status**: Lock change is correct, but `selected_device` access still has race conditions.

---

### 3.3 "Typical discovery time 50-200ms" - UNVERIFIED

**Claim**: Device discovery should complete quickly.

**Reality**: Tests use 10s timeout, suggesting this claim is not validated.

---

## 4. TEST GAPS

### 4.1 Missing: WebSocket Connection Integration Test

No test verifies the actual WebSocket connection path:
1. Client connects to simulator
2. Simulator sends EVENT_APC_WIFI_LIST
3. Client receives and processes it
4. `device_discovered` event is set

**Current tests**: Mock the WebSocket, bypassing the real connection.

---

### 4.2 Missing: Message Order Verification

No test verifies EVENT_APC_WIFI_LIST is processed before EVENT_APC_STATE.

---

### 4.3 Missing: Handshake Parameter Test

No test verifies the WebSocket URL format expected by simulator matches what client sends.

---

## 5. IMMEDIATE ACTION ITEMS

### Priority 1: Fix WebSocket Connection (BLOCKER)

1. **Check E2E config WebSocket URL**:
   ```python
   # In tests/e2e/conftest.py, verify:
   e2e_server_config.ANOVA_WEBSOCKET_URL
   ```
   Should include token: `ws://localhost:29000?token=e2e-test-token&supportedAccessories=APC`

2. **Check simulator token validation**:
   - What tokens does simulator accept in E2E mode?
   - Is token validation enabled?

3. **Add connection debugging**:
   ```python
   logger.debug(f"Connecting to: {self.websocket_url}")
   ```

### Priority 2: Fix Race Conditions

1. Protect `selected_device` reads with lock
2. Or document single-assignment pattern

### Priority 3: Add Integration Tests

1. Test real WebSocket connection (not mocked)
2. Test message ordering
3. Test URL format compatibility

---

## 6. CONFIRMED ROOT CAUSE OF E2E FAILURE

**CONFIRMED**: The WebSocket URL is missing required authentication parameters.

**Location**: `tests/e2e/conftest.py:133`

**Current (BROKEN)**:
```python
ANOVA_WEBSOCKET_URL=f"ws://localhost:{e2e_ports['ws_port']}"
```

**Required (WORKING)**:
```python
ANOVA_WEBSOCKET_URL=f"ws://localhost:{e2e_ports['ws_port']}?token=e2e-test-token&supportedAccessories=APC"
```

**Why This Causes Failure**:
1. Client connects without token in URL
2. Simulator requires `?token=xxx` for authentication
3. Simulator rejects connection → handshake timeout
4. Client logs "timed out during opening handshake"
5. Device list never received → `wait_for_device()` times out

**Evidence**:
- Simulator tests use: `f"ws://localhost:{port}?token=test-token&supportedAccessories=APC"`
- E2E config uses: `f"ws://localhost:{port}"` (NO TOKEN!)
- Comment says "Must match simulator's valid_tokens" but token not in URL

---

## 7. RECOMMENDED FIX SEQUENCE

1. **Verify E2E WebSocket URL includes token** - Check `_create_e2e_config()` function
2. **Add logging to WebSocket connection** - See what URL client actually uses
3. **Run single E2E test with verbose logging** - Capture full connection flow
4. **Fix URL if needed** - Add token parameter
5. **Re-run E2E tests** - Verify fix works
6. **Run 5x to check for flakiness** - Confirm reliability
7. **Update documentation** - Document actual findings

---

## 8. FILES TO INVESTIGATE

| File | What to Check |
|------|---------------|
| `tests/e2e/conftest.py:85-95` | How is `e2e_server_config` created? Does URL include token? |
| `tests/e2e/conftest.py:120-140` | How is `e2e_simulator` configured? What tokens does it accept? |
| `server/anova_client.py:217-249` | What URL is actually used for connection? |
| `simulator/websocket_server.py:170-185` | What authentication does simulator require? |

---

## 9. CONCLUSION

The E2E test timing fix has the right architectural approach:
- Event-based waiting instead of arbitrary sleeps
- Simulator sends device list for discovery
- Client signals when devices are discovered

However, the implementation has a fundamental bug: **the WebSocket connection itself is failing**, likely due to URL format mismatch. The device discovery improvements can't work if the connection never succeeds.

**Next Step**: Investigate WebSocket URL configuration in E2E tests.
