"""
Configuration management for development and production environments.

Development: Loads from .env file (gitignored)
Production: Loads from encrypted JSON file (for Raspberry Pi persistence)

Required environment variables:
- ANOVA_EMAIL: Anova account email
- ANOVA_PASSWORD: Anova account password
- DEVICE_ID: Anova device ID
- API_KEY: Bearer token for ChatGPT authentication
- DEBUG: Enable debug mode (optional, default: False)
- ENCRYPTION_KEY: Fernet encryption key (production only)

Reference: CLAUDE.md Section "Configuration Management"
Reference: docs/02-security-architecture.md Section 4.3
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv


# ==============================================================================
# CONFIGURATION LOADING
# ==============================================================================

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment.

    Development mode:
    - Loads from .env file using python-dotenv
    - .env file is gitignored (never commit credentials!)

    Production mode:
    - Loads from encrypted JSON file (credentials.enc)
    - Falls back to .env if encrypted file doesn't exist

    Returns:
        Configuration dictionary with keys:
            - anova_email: Anova account email
            - anova_password: Anova account password
            - device_id: Anova device ID
            - api_key: API key for ChatGPT authentication
            - debug: Debug mode flag (default: False)

    Raises:
        RuntimeError: If required environment variables are missing

    TODO: Implement from CLAUDE.md lines 1044-1055
    TODO: Load from .env file using load_dotenv()
    TODO: Get required env vars: ANOVA_EMAIL, ANOVA_PASSWORD, DEVICE_ID, API_KEY
    TODO: Validate all required vars are present (raise RuntimeError if missing)
    TODO: Return dict with configuration values
    TODO: Support DEBUG env var (optional, default: False)

    Example .env file:
        ANOVA_EMAIL=user@example.com
        ANOVA_PASSWORD=secret123
        DEVICE_ID=abc123
        API_KEY=sk-anova-your-key
        DEBUG=true

    Security notes:
    - .env file must be in .gitignore (never commit!)
    - Validate required vars are present at startup
    - Log errors without exposing credential values
    """
    raise NotImplementedError("load_config not yet implemented - see CLAUDE.md lines 1044-1055")


def load_encrypted_config(filepath: str) -> Dict[str, Any]:
    """
    Load encrypted configuration file (production).

    Used on Raspberry Pi to persist credentials across reboots securely.
    Credentials are encrypted using Fernet symmetric encryption.

    Args:
        filepath: Path to encrypted config file (e.g., '/opt/anova-assistant/credentials.enc')

    Returns:
        Decrypted configuration dictionary

    Raises:
        FileNotFoundError: If encrypted file doesn't exist
        ValueError: If decryption fails (wrong key or corrupted file)
        RuntimeError: If ENCRYPTION_KEY environment variable missing

    TODO: Implement from CLAUDE.md lines 1070-1080
    TODO: Get ENCRYPTION_KEY from environment
    TODO: Create Fernet instance with encryption key
    TODO: Read encrypted file
    TODO: Decrypt and parse JSON
    TODO: Return configuration dict

    Security notes:
    - Encryption key derived from hardware or environment
    - File permissions must be 0600 (owner read/write only)
    - Never log decrypted credentials

    Reference: CLAUDE.md lines 1063-1095
    Reference: docs/02-security-architecture.md Section 4.3
    """
    raise NotImplementedError("load_encrypted_config not yet implemented - see CLAUDE.md lines 1070-1080")


def save_encrypted_config(filepath: str, config: Dict[str, Any]) -> None:
    """
    Save configuration as encrypted file (production).

    Encrypts credentials and saves to file with restrictive permissions.
    Used during initial Raspberry Pi setup.

    Args:
        filepath: Path to save encrypted config (e.g., '/opt/anova-assistant/credentials.enc')
        config: Configuration dictionary to encrypt

    Raises:
        RuntimeError: If ENCRYPTION_KEY environment variable missing

    TODO: Implement from CLAUDE.md lines 1082-1094
    TODO: Get ENCRYPTION_KEY from environment
    TODO: Create Fernet instance with encryption key
    TODO: Convert config dict to JSON string
    TODO: Encrypt JSON string
    TODO: Write encrypted bytes to file
    TODO: Set file permissions to 0600 (owner read/write only)

    Security notes:
    - File permissions MUST be 0600 (owner only)
    - Directory permissions should be 0700
    - Never log plaintext credentials during encryption

    Reference: CLAUDE.md lines 1082-1094
    Reference: docs/02-security-architecture.md Section 4.3
    """
    raise NotImplementedError("save_encrypted_config not yet implemented - see CLAUDE.md lines 1082-1094")


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration has all required fields.

    Args:
        config: Configuration dictionary to validate

    Raises:
        RuntimeError: If required fields are missing

    TODO: Implement validation
    TODO: Check required keys: anova_email, anova_password, device_id, api_key
    TODO: Raise RuntimeError with clear message if any required key missing
    TODO: Validate values are not empty strings
    """
    raise NotImplementedError("validate_config not yet implemented")


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_encryption_key() -> bytes:
    """
    Get encryption key from environment.

    Returns:
        Encryption key as bytes (Fernet-compatible)

    Raises:
        RuntimeError: If ENCRYPTION_KEY not set

    TODO: Implement encryption key retrieval
    TODO: Get ENCRYPTION_KEY from environment
    TODO: Validate key is valid Fernet key (44 bytes base64-encoded)
    TODO: Return key as bytes

    Note: In production, encryption key can be:
    - Derived from hardware (CPU serial number)
    - Stored in environment variable
    - Generated on first run and persisted securely
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
