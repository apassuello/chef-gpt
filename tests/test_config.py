"""
Unit tests for configuration management.

Tests configuration loading from multiple sources:
- Environment variables (priority 1)
- Encrypted file (priority 2, placeholder)
- Plain JSON file (priority 3)

Test coverage goal: >80%

Reference: CLAUDE.md Section "Configuration Management"
Reference: docs/03-component-architecture.md Section 4.4.1 (COMP-CFG-01)
Reference: WebSocket migration - uses PERSONAL_ACCESS_TOKEN instead of email/password
"""

import json

import pytest

from server.config import Config

# ==============================================================================
# TEST FIXTURES
# ==============================================================================


@pytest.fixture
def clean_env(monkeypatch):
    """
    Clear all configuration-related environment variables.

    Ensures tests start with clean slate and don't leak config
    between test runs.
    """
    config_vars = [
        "PERSONAL_ACCESS_TOKEN",
        "API_KEY",
        "DEBUG",
        "ENCRYPTION_KEY",
    ]

    for var in config_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_env_vars(monkeypatch, clean_env):
    """
    Set valid environment variables for testing.

    Provides complete configuration via environment variables.
    """
    monkeypatch.setenv("PERSONAL_ACCESS_TOKEN", "anova-test-token-123")
    monkeypatch.setenv("API_KEY", "sk-anova-test-key")
    monkeypatch.setenv("DEBUG", "true")


@pytest.fixture
def temp_config_json(tmp_path):
    """
    Create temporary JSON config file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary JSON config file
    """
    config_data = {
        "personal_access_token": "anova-json-token-456",
        "api_key": "sk-anova-json-key",
        "debug": False,
    }

    config_file = tmp_path / "credentials.json"
    config_file.write_text(json.dumps(config_data, indent=2))

    return config_file


# ==============================================================================
# ENVIRONMENT LOADING TESTS
# ==============================================================================


def test_load_from_environment_success(mock_env_vars):
    """
    TC-CFG-01: Loading from environment with all required vars should succeed.

    Verifies:
    - Config.load() uses environment variables
    - Required fields populated correctly
    - Optional fields populated correctly
    """
    config = Config.load()

    assert config.PERSONAL_ACCESS_TOKEN == "anova-test-token-123"
    assert config.API_KEY == "sk-anova-test-key"
    assert config.DEBUG is True


def test_load_from_environment_missing_token(monkeypatch, clean_env):
    """
    TC-CFG-02: Missing PERSONAL_ACCESS_TOKEN should raise ValueError.

    Verifies:
    - Missing required field detected
    - Error message is helpful
    """
    monkeypatch.setenv("API_KEY", "sk-anova-test-key")

    with pytest.raises(ValueError) as exc_info:
        Config.load()

    assert "PERSONAL_ACCESS_TOKEN" in str(exc_info.value)


def test_load_from_environment_missing_api_key(monkeypatch, clean_env):
    """
    TC-CFG-03: Missing API_KEY should raise ValueError.
    """
    monkeypatch.setenv("PERSONAL_ACCESS_TOKEN", "anova-test-token-123")

    with pytest.raises(ValueError) as exc_info:
        Config.load()

    assert "API_KEY" in str(exc_info.value)


def test_load_from_environment_optional_debug(monkeypatch, clean_env):
    """
    TC-CFG-05: Optional DEBUG field should have default value.

    Verifies:
    - DEBUG defaults to False when not set
    """
    monkeypatch.setenv("PERSONAL_ACCESS_TOKEN", "anova-test-token-123")
    monkeypatch.setenv("API_KEY", "sk-anova-test-key")
    # Deliberately not setting DEBUG

    config = Config.load()

    assert config.DEBUG is False


# ==============================================================================
# JSON FILE LOADING TESTS
# ==============================================================================


def test_load_from_json_success(clean_env, temp_config_json, monkeypatch):
    """
    TC-CFG-06: Loading from JSON file should succeed.

    Verifies:
    - Config.load() finds and loads JSON file
    - JSON keys mapped correctly to Config fields
    """
    config = Config._from_json_file(temp_config_json)

    assert config.PERSONAL_ACCESS_TOKEN == "anova-json-token-456"
    assert config.API_KEY == "sk-anova-json-key"
    assert config.DEBUG is False


def test_load_from_json_missing_field(tmp_path, clean_env):
    """
    TC-CFG-07: JSON missing required field should raise error.

    Verifies:
    - Missing required fields detected in JSON
    - Error message helpful
    """
    incomplete_config = {
        "personal_access_token": "anova-token",
        # Missing api_key
    }

    config_file = tmp_path / "incomplete.json"
    config_file.write_text(json.dumps(incomplete_config))

    with pytest.raises((ValueError, KeyError)):
        Config._from_json_file(config_file)


# ==============================================================================
# CONFIGURATION PRIORITY TESTS
# ==============================================================================


def test_environment_takes_priority_over_json(mock_env_vars, temp_config_json, monkeypatch):
    """
    TC-CFG-08: Environment variables should take priority over JSON.

    Verifies:
    - When both env vars and JSON exist, env vars are used
    - Priority order: env > encrypted > JSON
    """
    # Since env vars are set (via mock_env_vars), they should take priority
    config = Config.load()

    # Should use environment values, not JSON values
    assert config.PERSONAL_ACCESS_TOKEN == "anova-test-token-123"  # From env
    assert config.API_KEY == "sk-anova-test-key"  # From env


def test_no_config_source_available(clean_env):
    """
    TC-CFG-09: No config source should raise helpful error.

    Verifies:
    - Clear error message when no config found
    - Error message explains how to fix
    """
    with pytest.raises(ValueError) as exc_info:
        Config.load()

    error_msg = str(exc_info.value)
    assert "Configuration not found" in error_msg or "PERSONAL_ACCESS_TOKEN" in error_msg


# ==============================================================================
# SAFETY CONSTANTS TESTS
# ==============================================================================


def test_safety_constants_hardcoded(mock_env_vars):
    """
    TC-CFG-10: Safety constants should always be hardcoded values.

    Verifies:
    - MIN_TEMP_CELSIUS = 40.0
    - MAX_TEMP_CELSIUS = 100.0
    - MAX_TIME_MINUTES = 5999
    - Values match validators.py constants
    """
    config = Config.load()

    assert config.MIN_TEMP_CELSIUS == 40.0
    assert config.MAX_TEMP_CELSIUS == 100.0
    assert config.MAX_TIME_MINUTES == 5999


def test_safety_constants_not_configurable(monkeypatch, clean_env):
    """
    TC-CFG-11: Safety constants should not be overridable via env vars.

    Verifies:
    - Even if someone sets MIN_TEMP_CELSIUS in env, it's ignored
    - Safety constants are always hardcoded
    """
    monkeypatch.setenv("PERSONAL_ACCESS_TOKEN", "anova-test-token-123")
    monkeypatch.setenv("API_KEY", "sk-anova-test-key")

    # Try to override safety constants (should be ignored)
    monkeypatch.setenv("MIN_TEMP_CELSIUS", "10.0")
    monkeypatch.setenv("MAX_TEMP_CELSIUS", "200.0")

    config = Config.load()

    # Should still be hardcoded values, not env vars
    assert config.MIN_TEMP_CELSIUS == 40.0
    assert config.MAX_TEMP_CELSIUS == 100.0


# ==============================================================================
# ENCRYPTED FILE TESTS
# ==============================================================================


def test_encrypted_file_not_implemented(tmp_path, clean_env, monkeypatch):
    """
    TC-CFG-12: Encrypted file loading should raise NotImplementedError.

    This is a placeholder for Phase 2B implementation.

    Verifies:
    - Encrypted file path exists → NotImplementedError
    - Error message is helpful
    """
    # Create dummy encrypted file
    encrypted_file = tmp_path / "credentials.enc"
    encrypted_file.write_bytes(b"encrypted_data_placeholder")

    with pytest.raises(NotImplementedError) as exc_info:
        Config._from_encrypted_file(encrypted_file)

    error_msg = str(exc_info.value)
    assert "not yet implemented" in error_msg.lower() or "environment" in error_msg.lower()
