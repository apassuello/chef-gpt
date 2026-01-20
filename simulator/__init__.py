"""
Anova Precision Cooker 3.0 Simulator.

A WebSocket-based simulator that faithfully replicates the Anova Cloud API
for integration and validation testing.

Usage:
    from simulator import AnovaSimulator

    sim = AnovaSimulator(time_scale=60.0)
    sim.start()
    # ... run tests ...
    sim.stop()

Reference: docs/SIMULATOR-SPECIFICATION.md
"""

from .config import Config
from .types import CookerState, DeviceState, SimulatorConfig

__version__ = "1.0.0"
__all__ = [
    "Config",
    "CookerState",
    "DeviceState",
    "SimulatorConfig",
]
