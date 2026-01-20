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
import logging
import os
import threading
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from server.anova_client import AnovaWebSocketClient
from server.config import Config
from server.middleware import register_error_handlers, setup_request_logging
from server.routes import api
from simulator.config import Config as SimConfig
from simulator.server import AnovaSimulator

logger = logging.getLogger(__name__)

# =============================================================================
# PORT MANAGEMENT
# =============================================================================


class E2EPortManager:
    """
    Manages port allocation for E2E test isolation.

    Uses higher port range (29000+) to avoid conflicts with unit tests.
    Adds process-based offset for parallel test runs across different processes.
    """

    # Process-based offset prevents port collision when running tests in parallel
    # across different pytest-xdist workers or parallel CI jobs
    _base_port = 29000 + (os.getpid() % 1000) * 10
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
        heating_rate=60.0,  # Fast heating for tests (60°C/min = instant preheat)
        ambient_temp=19.0,  # Room temperature
        valid_tokens=["e2e-test-token"],
    )


class SimulatorThread:
    """
    Runs the simulator in a background thread with its own event loop.

    This is necessary because:
    1. The WebSocket client (AnovaWebSocketClient) runs in its own background thread
    2. If the simulator runs in pytest-asyncio's event loop, there's a deadlock
    3. Running simulator in a separate thread allows both to operate independently

    Reference: https://websockets.readthedocs.io/en/stable/faq/asyncio.html
    "Choosing asyncio to handle concurrency is mutually exclusive with threading"
    """

    def __init__(self, config: SimConfig):
        self.config = config
        self.simulator: AnovaSimulator | None = None
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.ready = threading.Event()
        self.error: Exception | None = None

    def start(self):
        """Start the simulator in a background thread."""
        self.thread = threading.Thread(target=self._run, daemon=True, name="SimulatorThread")
        self.thread.start()

        # Wait for simulator to be ready
        if not self.ready.wait(timeout=10.0):
            raise RuntimeError("Simulator failed to start within timeout")

        if self.error:
            raise self.error

    def _run(self):
        """Run the simulator's event loop in this thread."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.simulator = AnovaSimulator(config=self.config)

            # Start simulator and signal ready
            self.loop.run_until_complete(self.simulator.start(start_control=True))
            self.ready.set()

            # Keep running until stopped
            self.loop.run_forever()

        except Exception as e:
            logger.error(f"Simulator thread error: {e}")
            self.error = e
            self.ready.set()  # Unblock waiter even on error
        finally:
            if self.loop:
                self.loop.close()

    def stop(self):
        """Stop the simulator and its event loop."""
        if self.loop and self.simulator:
            # Schedule stop on the simulator's event loop
            future = asyncio.run_coroutine_threadsafe(self.simulator.stop(), self.loop)
            try:
                future.result(timeout=5.0)
            except Exception as e:
                logger.warning(f"Error stopping simulator: {e}")

            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)


@pytest.fixture
def e2e_simulator(e2e_sim_config):
    """
    Running simulator with Control API for E2E tests.

    Runs in a background thread to avoid event loop deadlocks with the
    WebSocket client which also runs in its own background thread.

    Yields:
        Tuple of (simulator, control_api)
    """
    sim_thread = SimulatorThread(e2e_sim_config)
    sim_thread.start()

    yield sim_thread.simulator, sim_thread.simulator.control_api

    sim_thread.stop()


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


@pytest.fixture
def e2e_app(e2e_simulator, e2e_server_config):
    """
    Flask app with real WebSocket client connected to simulator.

    Connection Flow:
        1. Simulator is already running in background thread (from e2e_simulator fixture)
        2. Create Flask app → spawns WebSocket client in its own background thread
        3. Wait for client to connect AND receive device list (up to 10s)
        4. Yield app for testing

    Both simulator and client run in separate background threads with their own
    event loops, avoiding the pytest-asyncio deadlock issue.

    Raises:
        RuntimeError: If WebSocket client fails to become ready
    """
    simulator, control = e2e_simulator

    logger.info(f"Simulator ready on {e2e_server_config.ANOVA_WEBSOCKET_URL}")

    # Create Flask app (spawns WebSocket client background thread)
    app = _create_e2e_app_sync(e2e_server_config)

    # Get client from app config
    client = app.config.get("ANOVA_CLIENT")
    if not client:
        raise RuntimeError("ANOVA_CLIENT not configured in Flask app config")

    # Wait for device discovery (connection timeout handled in client __init__)
    if not client.wait_for_device(timeout=10.0):
        # Device discovery failed - provide diagnostic info
        client.shutdown()
        raise RuntimeError(
            f"E2E test setup failed: Device discovery timeout.\n"
            f"  WebSocket connected: {client.connected.is_set()}\n"
            f"  Connection error: {client.connection_error}\n"
            f"  Devices discovered: {len(client.devices)}\n"
            f"  Selected device: {client.selected_device}\n"
            f"  Simulator URL: {e2e_server_config.ANOVA_WEBSOCKET_URL}\n"
            f"  Hint: Check simulator logs for connection errors"
        )

    logger.info(f"E2E app ready: device={client.selected_device}, devices={len(client.devices)}")

    yield app

    # Cleanup: shutdown WebSocket client
    if client:
        client.shutdown()
        logger.debug("WebSocket client shut down")


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


@pytest.fixture
def reset_simulator(e2e_simulator):
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
