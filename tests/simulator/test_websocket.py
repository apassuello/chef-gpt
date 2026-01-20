"""
Tests for WebSocket server (Phase 1: CP-01).

Test cases:
- WS-01: Connect with valid token
- WS-02: Connect with invalid token
- WS-03: Connect without token
- WS-04: Send malformed JSON
- WS-05: Graceful disconnect

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 1
"""

import asyncio
import json

import pytest
import pytest_asyncio
import websockets
from websockets.exceptions import InvalidStatus

from simulator.config import Config
from simulator.server import AnovaSimulator

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture
def config():
    """Test configuration with accelerated time."""
    return Config(
        ws_port=18765,  # Use non-standard port for tests
        time_scale=60.0,
        valid_tokens=["valid-test-token", "another-valid-token"],
        expired_tokens=["expired-test-token"],
    )


@pytest_asyncio.fixture
async def simulator(config):
    """Start simulator for tests."""
    sim = AnovaSimulator(config=config)
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def ws_url(config):
    """WebSocket URL builder."""

    def _build(token=None, accessories="APC"):
        base = f"ws://localhost:{config.ws_port}"
        params = []
        if token:
            params.append(f"token={token}")
        if accessories:
            params.append(f"supportedAccessories={accessories}")
        if params:
            return f"{base}?{'&'.join(params)}"
        return base

    return _build


class TestWebSocketConnection:
    """Test WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_device_list_sent_on_connection(self, simulator, ws_url):
        """Test simulator sends EVENT_APC_WIFI_LIST immediately on connection."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # First message should be device list
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(msg)

            # Verify it's a device list event
            assert data["command"] == "EVENT_APC_WIFI_LIST"
            assert "payload" in data
            assert isinstance(data["payload"], list)
            assert len(data["payload"]) > 0

            # Verify device info structure
            device = data["payload"][0]
            assert "cookerId" in device
            assert "type" in device
            assert "name" in device
            assert device["online"] is True
            assert device["cookerId"] == simulator.cooker_id

            # Second message should be initial state
            msg2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data2 = json.loads(msg2)
            assert data2["command"] == "EVENT_APC_STATE"

    @pytest.mark.asyncio
    async def test_ws01_connect_with_valid_token(self, simulator, ws_url):
        """WS-01: Connect with valid token should succeed."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # First message: device list
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            assert data["command"] == "EVENT_APC_WIFI_LIST"

            # Second message: initial state
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)

            assert data["command"] == "EVENT_APC_STATE"
            assert "payload" in data
            assert data["payload"]["cookerId"] == simulator.cooker_id

    @pytest.mark.asyncio
    async def test_ws02_connect_with_invalid_token(self, simulator, ws_url):
        """WS-02: Connect with invalid token should be rejected."""
        url = ws_url(token="invalid-token-xyz")

        with pytest.raises(InvalidStatus) as exc_info:
            async with websockets.connect(url):
                pass

        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_ws03_connect_without_token(self, simulator, ws_url):
        """WS-03: Connect without token should be rejected."""
        url = ws_url(token=None)

        with pytest.raises(InvalidStatus) as exc_info:
            async with websockets.connect(url):
                pass

        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_ws04_send_malformed_json(self, simulator, ws_url):
        """WS-04: Send malformed JSON should return error."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # Consume initial messages (device list + state)
            await ws.recv()  # Device list
            await ws.recv()  # State

            # Send malformed JSON
            await ws.send("not valid json {{{")

            # Should receive error response
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)

            assert data["command"] == "RESPONSE"
            assert data["payload"]["status"] == "error"
            assert data["payload"]["code"] == "INVALID_PAYLOAD"

    @pytest.mark.asyncio
    async def test_ws05_graceful_disconnect(self, simulator, ws_url):
        """WS-05: Graceful disconnect should not raise errors."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # Consume initial messages (device list + state)
            await ws.recv()  # Device list
            await ws.recv()  # State

            # Client count should be 1
            assert len(simulator.ws_server.clients) == 1

        # After disconnect, client count should be 0
        await asyncio.sleep(0.1)  # Allow cleanup
        assert len(simulator.ws_server.clients) == 0


class TestWebSocketInitialState:
    """Test initial state sent on connection."""

    @pytest.mark.asyncio
    async def test_initial_state_structure(self, simulator, ws_url):
        """Initial EVENT_APC_STATE should have correct structure."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # Skip device list (first message)
            await ws.recv()

            # Get state (second message)
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)

            # Check top-level structure
            assert data["command"] == "EVENT_APC_STATE"
            payload = data["payload"]
            assert "cookerId" in payload
            assert "type" in payload
            assert "state" in payload

            # Check state structure
            state = payload["state"]
            assert "job" in state
            assert "job-status" in state
            assert "temperature-info" in state
            assert "pin-info" in state
            assert "heater-control" in state

    @pytest.mark.asyncio
    async def test_initial_state_values(self, simulator, ws_url):
        """Initial state should have correct default values."""
        url = ws_url(token="valid-test-token")

        async with websockets.connect(url) as ws:
            # Skip device list (first message)
            await ws.recv()

            # Get state (second message)
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)

            state = data["payload"]["state"]

            # Should be IDLE
            assert state["job-status"]["state"] == "IDLE"

            # Temperature should be ambient
            assert state["temperature-info"]["water-temperature"] == 22.0

            # Safety should be OK
            assert state["pin-info"]["device-safe"] == 1
            assert state["pin-info"]["water-level-low"] == 0
