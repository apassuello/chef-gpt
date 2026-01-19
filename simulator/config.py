"""
Configuration management for the Anova Simulator.

Loads configuration from environment variables and/or config files.

Reference: docs/SIMULATOR-SPECIFICATION.md Section 10
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
import yaml


@dataclass
class Config:
    """
    Simulator configuration loaded from environment or file.

    Environment variables (prefixed with SIM_):
        SIM_WS_PORT: WebSocket server port (default: 8765)
        SIM_AUTH_PORT: Firebase mock port (default: 8764)
        SIM_CONTROL_PORT: Test control API port (default: 8766)
        SIM_TIME_SCALE: Time acceleration factor (default: 1.0)
        SIM_AMBIENT_TEMP: Initial water temperature (default: 22.0)
        SIM_HEATING_RATE: Degrees C per minute (default: 1.0)
        SIM_COOKER_ID: Device identifier (default: anova sim-0000000000)
        SIM_LOG_LEVEL: Logging level (default: INFO)
    """
    # Server ports
    ws_port: int = 8765
    firebase_port: int = 8764
    control_port: int = 8766

    # Physics
    ambient_temp: float = 22.0
    heating_rate: float = 1.0
    cooling_rate: float = 0.5
    temp_tolerance: float = 0.5
    temp_oscillation: float = 0.2

    # Timing
    time_scale: float = 1.0
    broadcast_interval_idle: float = 30.0
    broadcast_interval_cooking: float = 2.0

    # Device
    cooker_id: str = "anova sim-0000000000"
    device_type: str = "pro"
    firmware_version: str = "3.3.01"

    # Auth
    valid_tokens: List[str] = field(default_factory=lambda: ["valid-test-token"])
    expired_tokens: List[str] = field(default_factory=lambda: ["expired-test-token"])

    # Firebase mock credentials (email -> password mapping)
    firebase_credentials: dict = field(default_factory=lambda: {
        "test@example.com": "testpassword123",
    })
    token_expiry: int = 3600  # Token expiry in seconds

    # Validation
    min_temp_celsius: float = 40.0
    max_temp_celsius: float = 100.0
    min_timer_seconds: int = 60
    max_timer_seconds: int = 359940

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        All environment variables are prefixed with SIM_.
        """
        return cls(
            ws_port=int(os.getenv("SIM_WS_PORT", "8765")),
            firebase_port=int(os.getenv("SIM_AUTH_PORT", "8764")),
            control_port=int(os.getenv("SIM_CONTROL_PORT", "8766")),
            time_scale=float(os.getenv("SIM_TIME_SCALE", "1.0")),
            ambient_temp=float(os.getenv("SIM_AMBIENT_TEMP", "22.0")),
            heating_rate=float(os.getenv("SIM_HEATING_RATE", "1.0")),
            cooling_rate=float(os.getenv("SIM_COOLING_RATE", "0.5")),
            cooker_id=os.getenv("SIM_COOKER_ID", "anova sim-0000000000"),
            log_level=os.getenv("SIM_LOG_LEVEL", "INFO"),
        )

    @classmethod
    def from_file(cls, filepath: str) -> "Config":
        """
        Load configuration from YAML file.

        Args:
            filepath: Path to simulator.yaml

        Returns:
            Config instance
        """
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)

        sim_config = data.get("simulator", {})
        ports = sim_config.get("ports", {})
        physics = sim_config.get("physics", {})
        timing = sim_config.get("timing", {})
        device = sim_config.get("device", {})
        auth = sim_config.get("auth", {})

        return cls(
            ws_port=ports.get("websocket", 8765),
            firebase_port=ports.get("firebase", 8764),
            control_port=ports.get("control", 8766),
            ambient_temp=physics.get("ambient_temp", 22.0),
            heating_rate=physics.get("heating_rate", 1.0),
            cooling_rate=physics.get("cooling_rate", 0.5),
            temp_tolerance=physics.get("temp_tolerance", 0.5),
            temp_oscillation=physics.get("temp_oscillation", 0.2),
            time_scale=timing.get("time_scale", 1.0),
            broadcast_interval_idle=timing.get("state_broadcast_idle", 30.0),
            broadcast_interval_cooking=timing.get("state_broadcast_cooking", 2.0),
            cooker_id=device.get("cooker_id", "anova sim-0000000000"),
            device_type=device.get("type", "pro"),
            firmware_version=device.get("firmware_version", "3.3.01"),
            valid_tokens=auth.get("valid_tokens", ["valid-test-token"]),
            expired_tokens=auth.get("expired_tokens", ["expired-test-token"]),
        )

    @classmethod
    def load(cls, config_file: Optional[str] = None) -> "Config":
        """
        Load configuration from file (if exists) with env overrides.

        Priority:
        1. Environment variables (highest)
        2. Config file
        3. Defaults (lowest)
        """
        # Start with defaults
        config = cls()

        # Load from file if provided and exists
        if config_file and os.path.exists(config_file):
            config = cls.from_file(config_file)
        elif os.path.exists("simulator.yaml"):
            config = cls.from_file("simulator.yaml")

        # Override with environment variables
        if os.getenv("SIM_WS_PORT"):
            config.ws_port = int(os.getenv("SIM_WS_PORT"))
        if os.getenv("SIM_AUTH_PORT"):
            config.firebase_port = int(os.getenv("SIM_AUTH_PORT"))
        if os.getenv("SIM_CONTROL_PORT"):
            config.control_port = int(os.getenv("SIM_CONTROL_PORT"))
        if os.getenv("SIM_TIME_SCALE"):
            config.time_scale = float(os.getenv("SIM_TIME_SCALE"))
        if os.getenv("SIM_AMBIENT_TEMP"):
            config.ambient_temp = float(os.getenv("SIM_AMBIENT_TEMP"))
        if os.getenv("SIM_HEATING_RATE"):
            config.heating_rate = float(os.getenv("SIM_HEATING_RATE"))
        if os.getenv("SIM_COOKER_ID"):
            config.cooker_id = os.getenv("SIM_COOKER_ID")
        if os.getenv("SIM_LOG_LEVEL"):
            config.log_level = os.getenv("SIM_LOG_LEVEL")

        return config
