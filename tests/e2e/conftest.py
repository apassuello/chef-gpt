"""
Pytest fixtures for end-to-end testing.

These fixtures set up the complete stack:
- Anova simulator (WebSocket server + physics simulation)
- Control API for test setup and state inspection
- Real Flask server with WebSocket client connected to simulator

This enables true E2E testing where HTTP requests flow through the
real Flask routes → real WebSocket client → local simulator.

Reference: Plan Phase 2 - E2E Test Infrastructure
"""

import asyncio
import threading
import time
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from flask import Flask
from flask.testing import FlaskClient

from server.anova_client import AnovaWebSocketClient
from server.config import Config
from server.middleware import register_error_handlers, setup_request_logging
from server.routes import api
from simulator.config import Config as SimConfig
from simulator.control_api import ControlAPI
from simulator.server import AnovaSimulator

# =============================================================================
# PORT MANAGEMENT
# =============================================================================


class E2EPortManager:
    """
    Manages port allocation for E2E test isolation.

    Uses higher port range (29000+) to avoid conflicts with unit tests.
    """

    _base_port = 29000
    _port_offset = 0
    _lock = threading.Lock()

    @classmethod
    def get_ports(cls) -> dict[str, int]:
        """
        Get unique ports for a test.

        Returns:
            Dict with ws_port, control_port, and flask_port
        """
        with cls._lock:
            ws_port = cls._base_port + cls._port_offset
            control_port = ws_port + 1
            flask_port = ws_port + 2
            cls._port_offset += 10
            return {
                "ws_port": ws_port,
                "control_port": control_port,
                "flask_port": flask_port,
            }


@pytest.fixture
def e2e_ports() -> dict[str, int]:
    """Get unique ports for E2E test isolation."""
    return E2EPortManager.get_ports()


# =============================================================================
# SIMULATOR FIXTURES
# =============================================================================


@pytest.fixture
def e2e_sim_config(e2e_ports) -> SimConfig:
    """
    Configuration for the E2E simulator.

    Uses accelerated time (60x) for reasonable test duration.
    """
    return SimConfig(
        ws_port=e2e_ports["ws_port"],
        control_port=e2e_ports["control_port"],
        firebase_port=e2e_ports["ws_port"] + 3,  # Not used but required
        time_scale=60.0,  # 1 minute = 1 second
        heating_rate=60.0,  # Fast heating for tests
        ambient_temp=22.0,
        valid_tokens=["e2e-test-token"],
    )


@pytest_asyncio.fixture
async def e2e_simulator(e2e_sim_config) -> AsyncGenerator[tuple[AnovaSimulator, ControlAPI], None]:
    """
    Running simulator with Control API for E2E tests.

    Yields:
        Tuple of (simulator, control_api)
    """
    simulator = AnovaSimulator(config=e2e_sim_config)
    await simulator.start(start_control=True)

    yield simulator, simulator.control_api

    await simulator.stop()


# =============================================================================
# FLASK APP FIXTURES
# =============================================================================


@pytest.fixture
def e2e_server_config(e2e_ports) -> Config:
    """
    Server configuration pointing to local simulator.

    Uses ws://localhost URL which bypasses PAT format validation.
    """
    return Config(
        PERSONAL_ACCESS_TOKEN="e2e-test-token",  # Must match simulator's valid_tokens
        API_KEY="e2e-api-key-12345",
        ANOVA_WEBSOCKET_URL=f"ws://localhost:{e2e_ports['ws_port']}",
        DEBUG=True,
    )


def _create_e2e_app_sync(config: Config) -> Flask:
    """
    Create Flask app with real WebSocket client (synchronous helper).

    This is called from the async fixture but must run synchronously
    because the WebSocket client uses its own background thread.
    """
    app = Flask(__name__)

    # Store config in app
    app.config["ANOVA_CONFIG"] = config
    app.config["API_KEY"] = config.API_KEY
    app.config["DEBUG"] = config.DEBUG
    app.config["TESTING"] = True

    # Create real WebSocket client connected to simulator
    anova_client = AnovaWebSocketClient(config)
    app.config["ANOVA_CLIENT"] = anova_client

    # Register blueprint and middleware
    app.register_blueprint(api)
    register_error_handlers(app)
    setup_request_logging(app)

    return app


@pytest_asyncio.fixture
async def e2e_app(e2e_simulator, e2e_server_config) -> AsyncGenerator[Flask, None]:
    """
    Flask app with real WebSocket client connected to simulator.

    This fixture:
    1. Waits for simulator to be ready
    2. Creates Flask app with real WebSocket client
    3. WebSocket client connects to local simulator

    Yields:
        Flask app ready for testing
    """
    simulator, control = e2e_simulator

    # Give simulator a moment to fully initialize
    await asyncio.sleep(0.1)

    # Create app in sync context (WebSocket client uses threading)
    app = _create_e2e_app_sync(e2e_server_config)

    # Give WebSocket client time to connect and receive device list
    time.sleep(0.5)

    yield app

    # Cleanup: shutdown WebSocket client
    client = app.config.get("ANOVA_CLIENT")
    if client:
        client.shutdown()


@pytest.fixture
def e2e_client(e2e_app) -> FlaskClient:
    """
    Flask test client for making HTTP requests.

    Usage:
        def test_something(e2e_client, e2e_auth_headers):
            response = e2e_client.get('/health')
            assert response.status_code == 200
    """
    return e2e_app.test_client()


@pytest.fixture
def e2e_auth_headers() -> dict[str, str]:
    """Valid authentication headers for E2E tests."""
    return {
        "Authorization": "Bearer e2e-api-key-12345",
        "Content-Type": "application/json",
    }


@pytest.fixture
def e2e_invalid_auth_headers() -> dict[str, str]:
    """Invalid authentication headers for testing auth rejection."""
    return {
        "Authorization": "Bearer wrong-api-key",
        "Content-Type": "application/json",
    }


# =============================================================================
# CONTROL API HELPERS
# =============================================================================


@pytest.fixture
def control_url(e2e_ports) -> str:
    """Control API base URL for direct test manipulation."""
    return f"http://localhost:{e2e_ports['control_port']}"


@pytest_asyncio.fixture
async def reset_simulator(e2e_simulator) -> AsyncGenerator[None, None]:
    """
    Fixture that resets simulator state before and after each test.

    Usage:
        def test_something(e2e_client, reset_simulator):
            # Simulator is reset to idle state
            pass
    """
    simulator, control = e2e_simulator
    simulator.reset()
    yield
    simulator.reset()


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def valid_e2e_cook_requests() -> dict[str, dict[str, Any]]:
    """
    Collection of valid cook requests for E2E testing.

    These use short times (1-2 minutes) that complete quickly
    with 60x time acceleration.
    """
    return {
        "quick_chicken": {
            "temperature_celsius": 65.0,
            "time_minutes": 2,  # 2 seconds at 60x
            "food_type": "chicken breast",
        },
        "quick_steak": {
            "temperature_celsius": 54.0,
            "time_minutes": 1,  # 1 second at 60x
            "food_type": "ribeye steak",
        },
        "minimum_temp": {
            "temperature_celsius": 40.0,
            "time_minutes": 1,
        },
        "maximum_temp": {
            "temperature_celsius": 100.0,
            "time_minutes": 1,
        },
    }


@pytest.fixture
def invalid_e2e_cook_requests() -> dict[str, dict[str, Any]]:
    """
    Collection of invalid cook requests for validation E2E testing.
    """
    return {
        "temp_too_low": {
            "temperature_celsius": 35.0,
            "time_minutes": 60,
            "expected_error": "TEMPERATURE_TOO_LOW",
            "expected_status": 400,
        },
        "temp_too_high": {
            "temperature_celsius": 105.0,
            "time_minutes": 60,
            "expected_error": "TEMPERATURE_TOO_HIGH",
            "expected_status": 400,
        },
        "unsafe_poultry": {
            "temperature_celsius": 56.0,
            "time_minutes": 90,
            "food_type": "chicken",
            "expected_error": "POULTRY_TEMP_UNSAFE",
            "expected_status": 400,
        },
        "unsafe_ground_meat": {
            "temperature_celsius": 59.0,
            "time_minutes": 60,
            "food_type": "ground beef",
            "expected_error": "GROUND_MEAT_TEMP_UNSAFE",
            "expected_status": 400,
        },
        "time_zero": {
            "temperature_celsius": 65.0,
            "time_minutes": 0,
            "expected_error": "TIME_TOO_SHORT",
            "expected_status": 400,
        },
        "time_too_long": {
            "temperature_celsius": 65.0,
            "time_minutes": 6000,
            "expected_error": "TIME_TOO_LONG",
            "expected_status": 400,
        },
        "missing_temperature": {
            "time_minutes": 90,
            "expected_error": "MISSING_TEMPERATURE",
            "expected_status": 400,
        },
        "missing_time": {
            "temperature_celsius": 65.0,
            "expected_error": "MISSING_TIME",
            "expected_status": 400,
        },
    }
