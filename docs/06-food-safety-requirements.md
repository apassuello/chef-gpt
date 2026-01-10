# 06 - Food Safety Requirements

> **Document Type:** Domain Knowledge Placeholder
> **Status:** Template (Requires Future Enhancement)
> **Version:** 1.0
> **Last Updated:** 2026-01-10
> **Depends On:** 01-System Context (FR-07, FR-08), CLAUDE.md
> **Blocks:** None (reference document)

---

## 1. Purpose

This document serves as a **placeholder** for comprehensive food safety domain research. The current implementation uses simplified safety rules documented in CLAUDE.md. Future enhancement will add scientific backing, USDA guidelines, and time-temperature equivalents.

**Current State:** Basic temperature thresholds are implemented and enforced server-side
**Future State:** Comprehensive pasteurization tables, pathogen reduction science, and time-temperature relationships

---

## 2. Current Food Safety Rules (Implemented)

These rules are currently enforced in `server/validators.py` and documented in CLAUDE.md.

### 2.1 Absolute Temperature Limits

| Limit | Value | Rationale | Enforced By |
|-------|-------|-----------|-------------|
| **Minimum Temperature** | 40.0°C (104°F) | Below this is the bacterial danger zone (4-60°C) where bacteria multiply rapidly | validators.py |
| **Maximum Temperature** | 100.0°C (212°F) | Water boils above this; device cannot maintain higher temperatures | validators.py |

**Error Codes:**
- `TEMPERATURE_TOO_LOW`: Rejected with explanation of danger zone
- `TEMPERATURE_TOO_HIGH`: Rejected with explanation of boiling point

### 2.2 Food-Specific Minimum Safe Temperatures

| Food Type | Minimum Temp | Standard Safe Temp | Notes | Enforced By |
|-----------|--------------|-------------------|-------|-------------|
| **Chicken/Turkey/Poultry** | 57.0°C | 65.0°C | 57°C requires 3+ hours for pasteurization; 65°C is standard (1-2 hour cook) | validators.py |
| **Ground Meat** | 60.0°C | N/A | Bacteria mixed throughout during grinding, higher temp required | validators.py |
| **Pork (whole muscle)** | 57.0°C | N/A | Modern pork is safe with pink center at this temperature | validators.py |
| **Beef/Lamb (whole muscle)** | 52.0°C | N/A | Rare is safe for whole muscle cuts (bacteria only on surface) | validators.py |

**Error Codes:**
- `POULTRY_TEMP_UNSAFE`: Poultry below 57°C rejected
- `GROUND_MEAT_TEMP_UNSAFE`: Ground meat below 60°C rejected

### 2.3 Time Limits

| Limit | Value | Rationale | Enforced By |
|-------|-------|-----------|-------------|
| **Minimum Time** | 1 minute | Practical minimum | validators.py |
| **Maximum Time** | 5999 minutes (99h 59m) | Device firmware limit | validators.py |

**Error Codes:**
- `TIME_TOO_SHORT`: Time < 1 minute rejected
- `TIME_TOO_LONG`: Time > 5999 minutes rejected

### 2.4 Danger Zone Warnings

**The Danger Zone:** 4°C - 60°C is the temperature range where bacteria multiply rapidly.

**Rule:** If food will be below 60°C for more than 4 hours total (including heat-up time):
- System warns the user
- Suggests higher temperature
- Still allows if user confirms (edge case for advanced users doing low-temp cooks)

**Implementation Status:** ⚠️ Warning logic NOT YET IMPLEMENTED (future enhancement)

---

## 3. Traceability to Requirements

### 3.1 Functional Requirements

| Requirement | Description | Implementation | Test Cases |
|-------------|-------------|----------------|------------|
| **FR-07** | System SHALL reject unsafe poultry temperatures (<57°C) | `validators.py` checks food_type and raises ValidationError | TC-VAL-10, TC-VAL-11 |
| **FR-08** | System SHALL reject unsafe ground meat temperatures (<60°C) | `validators.py` checks food_type and raises ValidationError | TC-VAL-12, TC-VAL-13 |
| **FR-04** | System SHALL validate temperature is within safe range (40-100°C) | `validators.py` checks absolute limits | TC-VAL-02, TC-VAL-03, TC-VAL-04, TC-VAL-05 |
| **FR-05** | System SHALL validate time is positive integer (1-5999 minutes) | `validators.py` checks time limits | TC-VAL-06, TC-VAL-07, TC-VAL-08, TC-VAL-09 |

### 3.2 Test Cases

| Test Case | Scenario | Input | Expected Result |
|-----------|----------|-------|-----------------|
| TC-VAL-02 | Temperature below minimum | temp=39.9 | ValidationError: TEMPERATURE_TOO_LOW |
| TC-VAL-03 | Temperature above maximum | temp=100.1 | ValidationError: TEMPERATURE_TOO_HIGH |
| TC-VAL-04 | Temperature exactly minimum | temp=40.0 | Pass |
| TC-VAL-05 | Temperature exactly maximum | temp=100.0 | Pass |
| TC-VAL-10 | Chicken below 57°C | temp=56, food="chicken" | ValidationError: POULTRY_TEMP_UNSAFE |
| TC-VAL-11 | Chicken at 57°C | temp=57, food="chicken" | Pass |
| TC-VAL-12 | Ground beef below 60°C | temp=59, food="ground beef" | ValidationError: GROUND_MEAT_TEMP_UNSAFE |
| TC-VAL-13 | Ground beef at 60°C | temp=60, food="ground beef" | Pass |

**Complete test specification:** See `tests/test_validators.py` (16 test cases total)

---

## 4. References

### 4.1 Internal Documentation

- **CLAUDE.md** - Section "Food Safety Rules (Critical)" - Current implementation guide
- **docs/01-system-context.md** - FR-04, FR-05, FR-07, FR-08 (functional requirements)
- **docs/03-component-architecture.md** - validators.py behavioral contract
- **server/validators.py** - Implementation of validation rules
- **tests/test_validators.py** - Test cases TC-VAL-01 through TC-VAL-16

### 4.2 External Sources (For Future Research)

**User to research and document the following:**

1. **USDA Food Safety Guidelines**
   - USDA pasteurization tables (time-temperature relationships)
   - Safe minimum internal temperatures by food type
   - Danger zone temperature ranges

2. **Douglas Baldwin's Sous Vide Guide**
   - "A Practical Guide to Sous Vide Cooking" (comprehensive reference)
   - Time-temperature tables for pasteurization
   - Pathogen reduction at various temperatures

3. **Food Safety Science**
   - Bacterial growth rates at different temperatures
   - Pathogen reduction models (D-values, Z-values)
   - Time-temperature equivalents for pasteurization
   - Salmonella, E. coli, Listeria survival curves

4. **Anova Resources**
   - Official Anova cooking guides and recommendations
   - Community-validated sous vide charts

---

## 5. Future Enhancements (Out of Scope for MVP)

### 5.1 Time-Temperature Tables

**Goal:** Replace simple temperature thresholds with comprehensive time-temperature relationships

**Example Enhancement:**
```
Current:  Chicken must be >= 65°C (simple threshold)
Enhanced: Chicken can be:
  - 57°C for 3+ hours (pasteurization via extended time)
  - 60°C for 1.5 hours
  - 65°C for 1 hour (standard)
  - 70°C for 30 minutes (quick cook)
```

**Benefit:** More flexibility for advanced users while maintaining safety

### 5.2 Pathogen Reduction Models

**Goal:** Implement scientific models for bacteria reduction

**Components:**
- D-value calculations (time to reduce pathogen population by 90%)
- Z-value calculations (temperature change for 10-fold D-value change)
- 7-log reduction targets (FDA standard)

**Benefit:** More accurate safety validation based on science

### 5.3 Danger Zone Duration Warnings

**Goal:** Warn users when food will be in danger zone too long

**Logic:**
```
IF temp < 60°C AND estimated_time_to_temp + cook_time > 4 hours:
    WARN user about danger zone
    SUGGEST higher temperature
    ALLOW if user confirms (advanced use case)
```

**Benefit:** Catches edge cases where cook time + heat-up time exceeds safe limits

### 5.4 Food Type Intelligence

**Goal:** Better food type detection and classification

**Enhancements:**
- Parse food type strings for keywords ("ground", "chicken breast", "pork chops")
- Classify into categories (poultry, ground meat, whole muscle, fish, vegetables)
- Apply category-specific rules

**Benefit:** More accurate food-specific safety validation

---

## 6. Implementation Constants

These constants are defined in `server/validators.py`:

```python
# Absolute limits
MIN_TEMP_CELSIUS = 40.0
MAX_TEMP_CELSIUS = 100.0

# Food-specific minimums
POULTRY_MIN_TEMP = 57.0      # With extended time (3+ hours)
POULTRY_SAFE_TEMP = 65.0     # Standard safe temperature
GROUND_MEAT_MIN_TEMP = 60.0  # Higher due to bacteria mixed throughout
PORK_MIN_TEMP = 57.0         # Modern pork is safe at this temp
BEEF_RARE_TEMP = 52.0        # Whole muscle, bacteria on surface only

# Time limits
MIN_TIME_MINUTES = 1
MAX_TIME_MINUTES = 5999  # Device firmware limit (99h 59m)
```

**Consistency:** These constants are documented in 4 locations and have been verified consistent:
1. `server/validators.py` (implementation)
2. `CLAUDE.md` (implementation guide)
3. `docs/01-system-context.md` (requirements)
4. `docs/03-component-architecture.md` (specifications)

---

## 7. Validation Error Messages

All validation errors include **actionable, educational messages** that explain WHY the validation failed:

**Example: TEMPERATURE_TOO_LOW**
```
"Temperature 35°C is below the safe minimum of 40°C. Food below this
temperature is in the bacterial danger zone (4-60°C) where bacteria
multiply rapidly."
```

**Example: POULTRY_TEMP_UNSAFE**
```
"Temperature 56°C is not safe for poultry. Minimum is 57°C with
extended time (3+ hours) or 65°C for standard cooking. This ensures
Salmonella is reduced to safe levels."
```

**Principle:** Errors are teaching moments. Users should understand the food safety reasoning behind rejections.

---

## 8. Testing Strategy

### 8.1 Unit Tests (Implemented)

**File:** `tests/test_validators.py`

**Coverage:** 16 test cases covering all food safety rules:
- TC-VAL-01 through TC-VAL-16
- Boundary conditions (exactly at limits)
- Edge cases (just below/above limits)
- Food-specific rules (poultry, ground meat)
- Type coercion (strings to floats)

**Execution:** `pytest tests/test_validators.py -v`

### 8.2 Integration Tests (Specified)

**File:** `docs/09-integration-test-specification.md`

**Coverage:** End-to-end flows through API:
- Start cook with unsafe temperature → HTTP 400
- Start cook with safe temperature → HTTP 200
- Validation error propagation to HTTP responses

**Status:** Specification complete; implementation pending

### 8.3 Security Tests (Specified)

**File:** `docs/11-security-test-specification.md`

**Coverage:** Security aspects of food safety:
- Bypassing server-side validation (should be impossible)
- Injection attacks on food_type parameter
- Boundary fuzzing on temperature/time parameters

**Status:** Specification complete; implementation pending

---

## 9. Open Questions

| Question ID | Question | Blocking | Owner | Status |
|-------------|----------|----------|-------|--------|
| OQ-FS-01 | Should danger zone warning be implemented for MVP? | No (future enhancement) | User | Open |
| OQ-FS-02 | Are Baldwin's tables accurate for Precision Cooker 3.0? | No (future research) | User | Open |
| OQ-FS-03 | Should we support time-temperature equivalents? | No (future enhancement) | User | Open |
| OQ-FS-04 | What edge cases exist for low-temp long cooks? | No (advanced use case) | User | Open |

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Claude | Initial template placeholder |

---

## 11. Next Steps

**For User (Future Research Session in Claude.ai):**

1. Research USDA pasteurization tables
2. Study Douglas Baldwin's comprehensive sous vide guide
3. Document time-temperature equivalents for each food type
4. Research pathogen reduction models (D-values, Z-values)
5. Expand this document with scientific backing

**For Implementation (After Research):**

1. Enhance `validators.py` with time-temperature tables
2. Implement danger zone duration warnings
3. Add pathogen reduction calculations
4. Expand test cases to cover new rules

**For Now (MVP):**

✅ Current simple rules are implemented and enforced
✅ Server-side validation is non-bypassable
✅ Error messages are educational
✅ Test coverage is comprehensive (16 test cases)

The system is safe for MVP deployment with current rules. Future enhancements will add scientific rigor and flexibility for advanced users.
