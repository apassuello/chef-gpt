"""
Unit tests for input validation and food safety enforcement.

Tests all validation logic including:
- Temperature range validation (40-100°C)
- Time range validation (1-5999 minutes)
- Food-specific safety rules (poultry, ground meat)
- Type coercion and error handling

Test coverage goal: >80%

Reference: CLAUDE.md Section "Testing Strategy > Critical Test Cases for Validators"
Reference: CLAUDE.md lines 825-842 (test case table)
"""

import pytest
from server.validators import validate_start_cook, _is_poultry, _is_ground_meat
from server.exceptions import ValidationError


# ==============================================================================
# TEMPERATURE VALIDATION TESTS
# ==============================================================================

def test_valid_parameters():
    """TC-VAL-01: Valid parameters should pass."""
    data = {"temperature_celsius": 65.0, "time_minutes": 90}
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 65.0
    assert result["time_minutes"] == 90
    assert result["food_type"] is None


def test_temperature_too_low():
    """TC-VAL-02: Temperature below 40°C should fail."""
    data = {"temperature_celsius": 39.9, "time_minutes": 90}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "TEMPERATURE_TOO_LOW"
    assert "danger zone" in exc_info.value.message.lower()


def test_temperature_too_high():
    """TC-VAL-03: Temperature above 100°C should fail."""
    data = {"temperature_celsius": 100.1, "time_minutes": 90}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "TEMPERATURE_TOO_HIGH"
    assert "100" in exc_info.value.message  # References water boiling point


def test_temperature_exactly_minimum():
    """TC-VAL-04: Temperature exactly at minimum (40.0°C) should pass."""
    data = {"temperature_celsius": 40.0, "time_minutes": 90}
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 40.0


def test_temperature_exactly_maximum():
    """TC-VAL-05: Temperature exactly at maximum (100.0°C) should pass."""
    data = {"temperature_celsius": 100.0, "time_minutes": 90}
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 100.0


# ==============================================================================
# TIME VALIDATION TESTS
# ==============================================================================

def test_time_zero():
    """TC-VAL-06: Time of zero should fail."""
    data = {"temperature_celsius": 65.0, "time_minutes": 0}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "TIME_TOO_SHORT"


def test_time_negative():
    """TC-VAL-07: Negative time should fail."""
    data = {"temperature_celsius": 65.0, "time_minutes": -1}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "TIME_TOO_SHORT"


def test_time_exactly_maximum():
    """TC-VAL-08: Time exactly at maximum (5999) should pass."""
    data = {"temperature_celsius": 65.0, "time_minutes": 5999}
    result = validate_start_cook(data)
    assert result["time_minutes"] == 5999


def test_time_above_maximum():
    """TC-VAL-09: Time above maximum (6000) should fail."""
    data = {"temperature_celsius": 65.0, "time_minutes": 6000}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "TIME_TOO_LONG"


# ==============================================================================
# FOOD SAFETY VALIDATION TESTS
# ==============================================================================

def test_poultry_temp_unsafe():
    """TC-VAL-10: Chicken at 56°C should fail (below poultry minimum)."""
    data = {"temperature_celsius": 56.0, "time_minutes": 90, "food_type": "chicken"}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "POULTRY_TEMP_UNSAFE"


def test_poultry_temp_safe():
    """TC-VAL-11: Chicken at 57°C should pass (poultry minimum)."""
    data = {"temperature_celsius": 57.0, "time_minutes": 90, "food_type": "chicken"}
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 57.0
    assert result["food_type"] == "chicken"


def test_ground_meat_temp_unsafe():
    """TC-VAL-12: Ground beef at 59°C should fail (below ground meat minimum)."""
    data = {"temperature_celsius": 59.0, "time_minutes": 90, "food_type": "ground beef"}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "GROUND_MEAT_TEMP_UNSAFE"


def test_ground_meat_temp_safe():
    """TC-VAL-13: Ground beef at 60°C should pass (ground meat minimum)."""
    data = {"temperature_celsius": 60.0, "time_minutes": 90, "food_type": "ground beef"}
    result = validate_start_cook(data)
    assert result["temperature_celsius"] == 60.0
    assert result["food_type"] == "ground beef"


# ==============================================================================
# TYPE COERCION TESTS
# ==============================================================================

def test_float_time_truncation():
    """TC-VAL-14: Float time should be truncated to integer."""
    data = {"temperature_celsius": 65.0, "time_minutes": 90.7}
    result = validate_start_cook(data)
    assert result["time_minutes"] == 90
    assert isinstance(result["time_minutes"], int)


# ==============================================================================
# MISSING FIELD TESTS
# ==============================================================================

def test_missing_temperature():
    """TC-VAL-15: Missing temperature should fail."""
    data = {"time_minutes": 90}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "MISSING_TEMPERATURE"
    assert "temperature_celsius" in exc_info.value.message


def test_missing_time():
    """TC-VAL-16: Missing time should fail."""
    data = {"temperature_celsius": 65.0}
    with pytest.raises(ValidationError) as exc_info:
        validate_start_cook(data)
    assert exc_info.value.error_code == "MISSING_TIME"
    assert "time_minutes" in exc_info.value.message


# ==============================================================================
# HELPER FUNCTION TESTS
# ==============================================================================

def test_is_poultry_chicken():
    """TC-HELP-01: Test _is_poultry recognizes chicken."""
    assert _is_poultry("chicken breast") is True
    assert _is_poultry("grilled chicken") is True
    assert _is_poultry("chicken") is True


def test_is_poultry_turkey():
    """TC-HELP-02: Test _is_poultry recognizes turkey."""
    assert _is_poultry("turkey") is True
    assert _is_poultry("roast turkey") is True


def test_is_poultry_false():
    """TC-HELP-03: Test _is_poultry returns False for non-poultry."""
    assert _is_poultry("beef") is False
    assert _is_poultry("pork") is False
    assert _is_poultry("steak") is False
    assert _is_poultry("lamb") is False


def test_is_ground_meat_burger():
    """TC-HELP-04: Test _is_ground_meat recognizes ground beef."""
    assert _is_ground_meat("ground beef") is True
    assert _is_ground_meat("burger") is True
    assert _is_ground_meat("hamburger patty") is True


def test_is_ground_meat_false():
    """TC-HELP-05: Test _is_ground_meat returns False for whole cuts."""
    assert _is_ground_meat("steak") is False
    assert _is_ground_meat("chicken breast") is False
    assert _is_ground_meat("pork chop") is False
    assert _is_ground_meat("ribeye") is False


# ==============================================================================
# IMPLEMENTATION NOTES
# ==============================================================================
# Test implementation checklist:
# - Uncomment imports once validators module is implemented
# - Implement each test with proper assertions
# - Test both success and failure cases
# - Verify error codes match specification
# - Check error messages are user-friendly
# - Test edge cases (boundaries, empty strings, etc.)
#
# Coverage goal: >80% for validators.py
#
# Reference: CLAUDE.md Section "Testing Strategy" (lines 813-942)
