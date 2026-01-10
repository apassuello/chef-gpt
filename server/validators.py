"""
Input validation and food safety enforcement.

This module contains ALL validation logic for the application.
It enforces food safety rules at the API level (not just GPT level).
Food safety is NON-NEGOTIABLE - these checks cannot be bypassed.

Validation order (fail fast):
1. Required fields present
2. Type validation (with coercion)
3. Range validation (absolute limits)
4. Food safety validation (context-specific)

Reference: CLAUDE.md Section "Code Patterns > 2. Validation Pattern"
Food Safety Rules: CLAUDE.md Section "Food Safety Rules"
Specification: docs/03-component-architecture.md Section 4.2.1
"""

from typing import Any, Dict, Optional
from .exceptions import ValidationError


# ==============================================================================
# FOOD SAFETY CONSTANTS
# ==============================================================================
# These values are CRITICAL and must NEVER be changed without consulting
# food safety guidelines. Source: CLAUDE.md "Food Safety Rules"

# Temperature limits (Celsius)
MIN_TEMP_CELSIUS = 40.0  # Below this is bacterial danger zone (4-60°C)
MAX_TEMP_CELSIUS = 100.0  # Water boils at 100°C; device cannot exceed this

# Food-specific minimum temperatures (Celsius)
POULTRY_MIN_TEMP = 57.0  # Chicken/turkey with 3+ hour cook time for pasteurization
POULTRY_SAFE_TEMP = 65.0  # Standard safe temperature for poultry (1-2 hour cook)
GROUND_MEAT_MIN_TEMP = 60.0  # Ground beef/pork - bacteria mixed throughout
PORK_MIN_TEMP = 57.0  # Whole muscle pork (modern pork safe with pink center)
BEEF_RARE_TEMP = 52.0  # Rare beef/lamb - bacteria only on surface

# Time limits (minutes)
MIN_TIME_MINUTES = 1  # Practical minimum
MAX_TIME_MINUTES = 5999  # Device limit (99h 59m)

# Danger zone
DANGER_ZONE_MIN = 4.0  # °C
DANGER_ZONE_MAX = 60.0  # °C
DANGER_ZONE_MAX_HOURS = 4  # Maximum time allowed in danger zone


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

def validate_start_cook(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate parameters for starting a cook.

    Enforces:
    - Temperature range (40°C - 100°C)
    - Time range (1 - 5999 minutes)
    - Food safety rules (poultry, ground meat)

    Validation order (fail fast):
    1. Required fields present
    2. Type validation (with coercion)
    3. Range validation (absolute limits)
    4. Food safety validation (context-specific)

    Args:
        data: Request data from ChatGPT containing:
            - temperature_celsius (float): Target temperature
            - time_minutes (int): Cook time in minutes
            - food_type (str, optional): Type of food being cooked

    Returns:
        Dict with validated and normalized parameters:
            - temperature_celsius (float): Rounded to 1 decimal place
            - time_minutes (int): Truncated to integer
            - food_type (str | None): Normalized lowercase food type

    Raises:
        ValidationError: If validation fails with specific error code:
            - MISSING_TEMPERATURE: temperature_celsius field missing
            - MISSING_TIME: time_minutes field missing
            - INVALID_TEMPERATURE: temperature not a valid number
            - INVALID_TIME: time not a valid number
            - TEMPERATURE_TOO_LOW: temp < 40°C (danger zone)
            - TEMPERATURE_TOO_HIGH: temp > 100°C (water boils)
            - TIME_TOO_SHORT: time < 1 minute
            - TIME_TOO_LONG: time > 5999 minutes
            - POULTRY_TEMP_UNSAFE: poultry temp < 57°C
            - GROUND_MEAT_TEMP_UNSAFE: ground meat temp < 60°C

    TODO: Implement validation logic from CLAUDE.md "Validation Pattern" (lines 258-342)
    TODO: Check required fields first (temperature_celsius, time_minutes)
    TODO: Coerce types (float for temp, int for time) and catch TypeError/ValueError
    TODO: Check absolute temperature limits (40-100°C)
    TODO: Check time limits (1-5999 minutes)
    TODO: Check food-specific safety rules using _is_poultry() and _is_ground_meat()
    TODO: Return validated dict with rounded temp, truncated time, normalized food_type
    TODO: Write tests for ALL 16 test cases in CLAUDE.md "Testing Strategy"

    Example:
        >>> validate_start_cook({"temperature_celsius": 65.0, "time_minutes": 90})
        {"temperature_celsius": 65.0, "time_minutes": 90, "food_type": None}

        >>> validate_start_cook({"temperature_celsius": 56, "time_minutes": 90, "food_type": "chicken"})
        ValidationError: POULTRY_TEMP_UNSAFE
    """
    # 1. Check required fields
    if "temperature_celsius" not in data:
        raise ValidationError(
            "MISSING_TEMPERATURE",
            "temperature_celsius is required"
        )

    if "time_minutes" not in data:
        raise ValidationError(
            "MISSING_TIME",
            "time_minutes is required"
        )

    # 2. Type validation with coercion
    try:
        temp = float(data["temperature_celsius"])
    except (TypeError, ValueError):
        raise ValidationError(
            "INVALID_TEMPERATURE",
            "temperature_celsius must be a number"
        )

    try:
        time = int(data["time_minutes"])
    except (TypeError, ValueError):
        raise ValidationError(
            "INVALID_TIME",
            "time_minutes must be a number"
        )

    # Extract optional food_type
    food_type = data.get("food_type", "").lower().strip() if data.get("food_type") else None

    # 3. Range validation - Temperature
    if temp < MIN_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_LOW",
            f"Temperature {temp}°C is below the safe minimum of {MIN_TEMP_CELSIUS}°C. "
            f"Food below this temperature is in the bacterial danger zone."
        )

    if temp > MAX_TEMP_CELSIUS:
        raise ValidationError(
            "TEMPERATURE_TOO_HIGH",
            f"Temperature {temp}°C exceeds the safe maximum of {MAX_TEMP_CELSIUS}°C. "
            f"Water boils at 100°C."
        )

    # 4. Range validation - Time
    if time < MIN_TIME_MINUTES:
        raise ValidationError(
            "TIME_TOO_SHORT",
            f"Time {time} minutes is below the minimum of {MIN_TIME_MINUTES} minute."
        )

    if time > MAX_TIME_MINUTES:
        raise ValidationError(
            "TIME_TOO_LONG",
            f"Time {time} minutes exceeds the device maximum of {MAX_TIME_MINUTES} minutes."
        )

    # TODO: Add food safety validation

    # Return validated data
    return {
        "temperature_celsius": round(temp, 1),
        "time_minutes": time,
        "food_type": food_type
    }


def _is_poultry(food_type: str) -> bool:
    """
    Check if food type is poultry.

    Poultry includes: chicken, turkey, duck, hen, fowl, goose.
    Poultry has higher minimum safe temperatures due to salmonella risk.

    Args:
        food_type: Normalized (lowercase, stripped) food type string

    Returns:
        True if food_type contains poultry keywords, False otherwise

    Example:
        >>> _is_poultry("chicken breast")
        True
        >>> _is_poultry("beef")
        False
    """
    poultry_keywords = ["chicken", "turkey", "duck", "poultry", "hen", "fowl", "goose"]
    return any(kw in food_type for kw in poultry_keywords)


def _is_ground_meat(food_type: str) -> bool:
    """
    Check if food type is ground meat.

    Ground meat includes: ground beef, ground pork, hamburger, sausage, mince.
    Ground meat requires higher minimum temps because bacteria are mixed throughout.

    Args:
        food_type: Normalized (lowercase, stripped) food type string

    Returns:
        True if food_type contains ground meat keywords, False otherwise

    Example:
        >>> _is_ground_meat("ground beef")
        True
        >>> _is_ground_meat("steak")
        False
    """
    ground_keywords = ["ground", "mince", "burger", "sausage"]
    return any(kw in food_type for kw in ground_keywords)


def validate_device_id(device_id: Optional[str]) -> str:
    """
    Validate device ID is present and not empty.

    Args:
        device_id: Device ID from request or config

    Returns:
        Validated device ID string

    Raises:
        ValidationError: If device_id is None or empty with error code MISSING_DEVICE_ID

    TODO: Implement validation
    TODO: Check if device_id is None or empty string
    TODO: Raise ValidationError with code "MISSING_DEVICE_ID" if invalid
    """
    raise NotImplementedError("validate_device_id not yet implemented")


# ==============================================================================
# VALIDATION ERROR CODES
# ==============================================================================
# Reference: CLAUDE.md Section "Food Safety Rules > Validation Error Codes"
#
# These error codes MUST match the API specification:
# - TEMPERATURE_TOO_LOW: temp < 40.0°C (HTTP 400)
# - TEMPERATURE_TOO_HIGH: temp > 100.0°C (HTTP 400)
# - POULTRY_TEMP_UNSAFE: Poultry AND temp < 57.0°C (HTTP 400)
# - GROUND_MEAT_TEMP_UNSAFE: Ground meat AND temp < 60.0°C (HTTP 400)
# - TIME_TOO_SHORT: time < 1 minute (HTTP 400)
# - TIME_TOO_LONG: time > 5999 minutes (HTTP 400)
# - MISSING_TEMPERATURE: temperature_celsius field missing (HTTP 400)
# - MISSING_TIME: time_minutes field missing (HTTP 400)
# - INVALID_TEMPERATURE: temperature not a valid number (HTTP 400)
# - INVALID_TIME: time not a valid number (HTTP 400)
# - MISSING_DEVICE_ID: device_id missing or empty (HTTP 400)
