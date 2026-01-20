"""
Predefined cooking scenarios for demos.

Each scenario defines a complete sous vide cook with:
- Food type and description
- Target temperature
- Cook time
- Expected behavior description

Usage:
    from demo.scenarios import SCENARIOS, get_scenario

    scenario = get_scenario("chicken")
    print(f"Cooking {scenario['name']} at {scenario['temp']}°C")
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CookScenario:
    """A predefined cooking scenario."""

    name: str
    description: str
    temp_celsius: float
    time_minutes: int
    food_type: str
    expected_result: str


# Predefined scenarios optimized for demo
SCENARIOS: dict[str, CookScenario] = {
    "chicken": CookScenario(
        name="Tender Chicken Breast",
        description="Juicy, perfectly cooked chicken breast",
        temp_celsius=65.0,
        time_minutes=90,
        food_type="chicken breast",
        expected_result="Tender, moist chicken with perfect texture",
    ),
    "steak": CookScenario(
        name="Medium-Rare Ribeye",
        description="Restaurant-quality steak cooked edge-to-edge",
        temp_celsius=54.0,
        time_minutes=120,
        food_type="ribeye steak",
        expected_result="Pink, juicy steak from edge to edge",
    ),
    "salmon": CookScenario(
        name="Silky Salmon Fillet",
        description="Delicate, melt-in-your-mouth salmon",
        temp_celsius=52.0,
        time_minutes=45,
        food_type="salmon fillet",
        expected_result="Translucent, silky salmon with perfect flake",
    ),
    "pork": CookScenario(
        name="Juicy Pork Chop",
        description="Tender pork chop that stays pink",
        temp_celsius=60.0,
        time_minutes=90,
        food_type="pork chop",
        expected_result="Moist, slightly pink pork with great texture",
    ),
    "eggs": CookScenario(
        name="Perfect Soft Eggs",
        description="Creamy, custard-like eggs",
        temp_celsius=63.0,
        time_minutes=60,
        food_type="eggs",
        expected_result="Silky yolk with just-set whites",
    ),
    "quick": CookScenario(
        name="Quick Demo",
        description="Fast demo for testing (5 minutes)",
        temp_celsius=60.0,
        time_minutes=5,
        food_type="demo",
        expected_result="Completes quickly to show full lifecycle",
    ),
    "ultra_quick": CookScenario(
        name="Ultra Quick Demo",
        description="Ultra-fast demo (1 minute)",
        temp_celsius=55.0,
        time_minutes=1,
        food_type="demo",
        expected_result="Completes in seconds with time acceleration",
    ),
}


def get_scenario(name: str) -> CookScenario:
    """
    Get a cooking scenario by name.

    Args:
        name: Scenario name (chicken, steak, salmon, etc.)

    Returns:
        CookScenario object

    Raises:
        KeyError: If scenario name not found
    """
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}")
    return SCENARIOS[name]


def list_scenarios() -> list[dict[str, Any]]:
    """
    List all available scenarios.

    Returns:
        List of scenario info dicts
    """
    return [
        {
            "name": key,
            "title": scenario.name,
            "description": scenario.description,
            "temp": scenario.temp_celsius,
            "time": scenario.time_minutes,
        }
        for key, scenario in SCENARIOS.items()
    ]


def print_scenarios() -> None:
    """Print all available scenarios to stdout."""
    print("\nAvailable Demo Scenarios:")
    print("-" * 60)
    for key, scenario in SCENARIOS.items():
        print(f"\n  {key}:")
        print(f"    {scenario.name}")
        print(f"    {scenario.temp_celsius}°C for {scenario.time_minutes} minutes")
        print(f"    {scenario.description}")
    print()
