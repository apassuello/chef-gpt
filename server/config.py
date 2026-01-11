"""
Configuration management for development and production environments.

Development: Loads from environment variables (.env file, gitignored)
Production: Loads from encrypted JSON file (for Raspberry Pi persistence)

Required environment variables:
- ANOVA_EMAIL: Anova account email
- ANOVA_PASSWORD: Anova account password
- DEVICE_ID: Anova device ID

Optional environment variables:
- API_KEY: Bearer token for ChatGPT authentication (None = no auth)
- DEBUG: Enable debug mode (default: False)

Reference: CLAUDE.md Section "Configuration Management"
Reference: docs/03-component-architecture.md Section 4.4.1 (COMP-CFG-01)
"""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Self

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """
    Application configuration with credentials and safety constants.

    Supports multiple configuration sources with priority order:
    1. Environment variables (highest priority)
    2. Encrypted file (production)
    3. Plain JSON file (development only)

    Safety constants are hardcoded and non-configurable to prevent
    misconfiguration from bypassing food safety rules.
    """

    # Anova credentials (required)
    ANOVA_EMAIL: str
    ANOVA_PASSWORD: str
    DEVICE_ID: str

    # Optional API key for ChatGPT auth
    API_KEY: str | None = None

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    DEBUG: bool = False

    # Safety limits (hardcoded, non-configurable)
    # These match validators.py constants
    MIN_TEMP_CELSIUS: float = 40.0
    MAX_TEMP_CELSIUS: float = 100.0
    MAX_TIME_MINUTES: int = 5999

    @classmethod
    def load(cls) -> Self:
        """
        Load configuration from available source.

        Priority order:
        1. Environment variables (if ANOVA_EMAIL env var exists)
        2. Encrypted file (config/credentials.enc)
        3. Plain JSON file (config/credentials.json)

        Returns:
            Config instance with all required fields populated

        Raises:
            ValueError: No configuration source found or required fields missing
            NotImplementedError: Encrypted file exists but decryption not implemented

        Specification: COMP-CFG-01 (docs/03-component-architecture.md Section 4.4.1)
        """
        # Try environment first (development/testing)
        if os.getenv("ANOVA_EMAIL"):
            logger.info("Loading configuration from environment variables")
            return cls._from_env()

        # Try encrypted file (production)
        config_path = Path(__file__).parent.parent / "config" / "credentials.enc"
        if config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            return cls._from_encrypted_file(config_path)

        # Try plain JSON (development only)
        plain_config = Path(__file__).parent.parent / "config" / "credentials.json"
        if plain_config.exists():
            logger.warning("Loading from plain JSON config - use encrypted file in production!")
            return cls._from_json_file(plain_config)

        # No config source found
        raise ValueError(
            "Configuration not found. Set ANOVA_EMAIL, ANOVA_PASSWORD, "
            "and DEVICE_ID environment variables, or provide config/credentials.enc"
        )

    @classmethod
    def _from_env(cls) -> Self:
        """
        Load configuration from environment variables.

        Returns:
            Config instance

        Raises:
            ValueError: If required environment variables are missing
        """
        email = os.environ.get("ANOVA_EMAIL")
        password = os.environ.get("ANOVA_PASSWORD")
        device_id = os.environ.get("DEVICE_ID")

        # Validate required fields
        if not all([email, password, device_id]):
            missing = []
            if not email:
                missing.append("ANOVA_EMAIL")
            if not password:
                missing.append("ANOVA_PASSWORD")
            if not device_id:
                missing.append("DEVICE_ID")

            raise ValueError(f"Missing required environment variables: {missing}")

        # Parse DEBUG env var
        debug = os.environ.get("DEBUG", "").lower() == "true"

        return cls(
            ANOVA_EMAIL=email,
            ANOVA_PASSWORD=password,
            DEVICE_ID=device_id,
            API_KEY=os.environ.get("API_KEY"),
            DEBUG=debug
        )

    @classmethod
    def _from_json_file(cls, path: Path) -> Self:
        """
        Load configuration from plain JSON file.

        Development only - plain JSON files are not secure for production.

        Args:
            path: Path to JSON config file

        Returns:
            Config instance

        Raises:
            ValueError: If JSON is invalid or missing required fields
            FileNotFoundError: If file doesn't exist
        """
        with open(path) as f:
            data = json.load(f)

        # Validate required fields
        required = ["anova_email", "anova_password", "device_id"]
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"JSON config missing required fields: {missing}")

        return cls(
            ANOVA_EMAIL=data["anova_email"],
            ANOVA_PASSWORD=data["anova_password"],
            DEVICE_ID=data["device_id"],
            API_KEY=data.get("api_key"),
            DEBUG=data.get("debug", False)
        )

    @classmethod
    def _from_encrypted_file(cls, path: Path) -> Self:
        """
        Load configuration from encrypted file.

        Uses AES-256-GCM with key derived from machine identifier.
        This is a placeholder for Phase 2B implementation.

        Args:
            path: Path to encrypted config file

        Returns:
            Config instance

        Raises:
            NotImplementedError: Encrypted file loading not yet implemented

        TODO: Implement with cryptography library in Phase 2B
        TODO: Use Fernet symmetric encryption
        TODO: Derive key from ENCRYPTION_KEY environment variable
        """
        raise NotImplementedError(
            "Encrypted config loading not yet implemented. "
            "Use environment variables or plain JSON for now."
        )


# ==============================================================================
# LEGACY FUNCTION-BASED API (DEPRECATED)
# ==============================================================================
# These functions are kept for backward compatibility but should not be used.
# Use Config.load() instead.


def load_config():
    """
    DEPRECATED: Use Config.load() instead.

    Load configuration from environment.
    """
    config = Config.load()
    return {
        "anova_email": config.ANOVA_EMAIL,
        "anova_password": config.ANOVA_PASSWORD,
        "device_id": config.DEVICE_ID,
        "api_key": config.API_KEY,
        "debug": config.DEBUG
    }


def load_encrypted_config(filepath: str):
    """
    DEPRECATED: Use Config._from_encrypted_file() instead.

    Load encrypted configuration file (production).
    """
    return Config._from_encrypted_file(Path(filepath))


def save_encrypted_config(filepath: str, config):
    """
    DEPRECATED: Not implemented.

    Save configuration as encrypted file (production).
    """
    raise NotImplementedError("save_encrypted_config not yet implemented")


def validate_config(config):
    """
    DEPRECATED: Validation now happens in Config._from_env() and Config._from_json_file().

    Validate configuration has all required fields.
    """
    raise NotImplementedError("validate_config not yet implemented - use Config.load() instead")


def get_encryption_key():
    """
    DEPRECATED: Not implemented.

    Get encryption key from environment.
    """
    raise NotImplementedError("get_encryption_key not yet implemented")


# ==============================================================================
# SECURITY NOTES
# ==============================================================================
# CRITICAL - Configuration security:
# ✅ .env file must be in .gitignore
# ✅ Encrypted file permissions must be 0600
# ✅ Validate all required vars at startup
# ✅ Log errors without exposing credential values
#
# ❌ NEVER commit credentials to git
# ❌ NEVER log plaintext passwords or API keys
# ❌ NEVER expose credentials in error messages
#
# Reference: CLAUDE.md Section "Anti-Patterns > 4. Never Hardcode Credentials"
