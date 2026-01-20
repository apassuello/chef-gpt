"""
Tests for Firebase authentication mock (Phase 5: CP-05).

Reference: docs/SIMULATOR-IMPLEMENTATION-PLAN.md Phase 5
"""

import asyncio
import json

import aiohttp
import pytest
import pytest_asyncio
import websockets

from simulator.auth import TokenManager
from simulator.config import Config
from simulator.firebase_mock import FirebaseMock
from simulator.server import AnovaSimulator

# Note: Only async tests should be marked with @pytest.mark.asyncio

# Unique ports for auth tests
PORT_FB = 18850
PORT_WS = 18851


# =============================================================================
# TOKEN MANAGER UNIT TESTS
# =============================================================================


class TestTokenManager:
    """Tests for TokenManager class."""

    def test_authenticate_valid_credentials(self):
        """Should return tokens for valid credentials."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, refresh_token, error = tm.authenticate("test@example.com", "password123")

        assert id_token is not None
        assert refresh_token is not None
        assert error is None

    def test_authenticate_invalid_password(self):
        """Should reject invalid password."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, refresh_token, error = tm.authenticate("test@example.com", "wrongpassword")

        assert id_token is None
        assert refresh_token is None
        assert error == "INVALID_PASSWORD"

    def test_authenticate_unknown_email(self):
        """Should reject unknown email."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, refresh_token, error = tm.authenticate("unknown@example.com", "password123")

        assert id_token is None
        assert refresh_token is None
        assert error == "EMAIL_NOT_FOUND"

    def test_token_validation(self):
        """Should validate issued tokens."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, _, _ = tm.authenticate("test@example.com", "password123")
        token_info = tm.validate_token(id_token)

        assert token_info is not None
        assert token_info.email == "test@example.com"
        assert not token_info.is_expired()

    def test_token_refresh(self):
        """Should exchange refresh token for new ID token."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, refresh_token, _ = tm.authenticate("test@example.com", "password123")
        new_id_token, error = tm.refresh_token(refresh_token)

        assert new_id_token is not None
        assert new_id_token != id_token  # New token should be different
        assert error is None

    def test_invalid_refresh_token(self):
        """Should reject invalid refresh token."""
        tm = TokenManager({"test@example.com": "password123"})

        new_id_token, error = tm.refresh_token("invalid-refresh-token")

        assert new_id_token is None
        assert error == "INVALID_REFRESH_TOKEN"

    def test_force_expiry(self):
        """Should force all tokens to be expired."""
        tm = TokenManager({"test@example.com": "password123"})

        id_token, _, _ = tm.authenticate("test@example.com", "password123")
        assert tm.is_token_valid(id_token)

        tm.force_expiry(True)
        assert not tm.is_token_valid(id_token)

        tm.force_expiry(False)
        assert tm.is_token_valid(id_token)


# =============================================================================
# FIREBASE MOCK HTTP TESTS
# =============================================================================


@pytest.fixture
def auth_config():
    """Configuration for auth tests."""
    return Config(
        firebase_port=PORT_FB,
        ws_port=PORT_WS,
        firebase_credentials={"test@example.com": "testpassword123"},
        valid_tokens=["test-token"],
    )


@pytest_asyncio.fixture
async def firebase_mock(auth_config):
    """Start Firebase mock for tests."""
    mock = FirebaseMock(auth_config)
    await mock.start()
    yield mock
    await mock.stop()


@pytest.mark.asyncio
async def test_auth01_token_refresh_valid(firebase_mock, auth_config):
    """AUTH-01: Token refresh with valid refresh token returns id_token."""
    async with aiohttp.ClientSession() as session:
        # First, sign in to get tokens
        sign_in_url = f"http://localhost:{auth_config.firebase_port}/v1/accounts:signInWithPassword"
        async with session.post(
            sign_in_url,
            json={"email": "test@example.com", "password": "testpassword123"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            refresh_token = data["refreshToken"]

        # Now refresh the token
        refresh_url = f"http://localhost:{auth_config.firebase_port}/v1/token"
        async with session.post(
            refresh_url,
            json={"grant_type": "refresh_token", "refresh_token": refresh_token},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "id_token" in data
            assert "access_token" in data
            assert "refresh_token" in data


@pytest.mark.asyncio
async def test_auth02_token_refresh_invalid(firebase_mock, auth_config):
    """AUTH-02: Token refresh with invalid refresh token returns 401."""
    async with aiohttp.ClientSession() as session:
        refresh_url = f"http://localhost:{auth_config.firebase_port}/v1/token"
        async with session.post(
            refresh_url,
            json={"grant_type": "refresh_token", "refresh_token": "invalid-token"},
        ) as resp:
            assert resp.status == 401


@pytest.fixture
def auth03_config():
    """Configuration for AUTH-03 test with Firebase-issued tokens."""
    return Config(
        firebase_port=PORT_FB + 2,
        ws_port=PORT_WS + 2,
        firebase_credentials={"test@example.com": "testpassword123"},
        valid_tokens=[],  # Empty - we'll use Firebase tokens
    )


@pytest_asyncio.fixture
async def auth03_firebase(auth03_config):
    """Start Firebase mock for AUTH-03."""
    mock = FirebaseMock(auth03_config)
    await mock.start()
    yield mock
    await mock.stop()


@pytest_asyncio.fixture
async def auth03_simulator(auth03_config, auth03_firebase):
    """Start simulator for AUTH-03 that validates against Firebase."""
    sim = AnovaSimulator(config=auth03_config)
    # Share the token manager between Firebase mock and WebSocket server
    sim.ws_server._validate_token = lambda t: auth03_firebase.token_manager.is_token_valid(t)
    await sim.start()
    yield sim, auth03_firebase
    await sim.stop()


@pytest.mark.asyncio
async def test_auth03_websocket_with_firebase_token(auth03_simulator, auth03_config):
    """AUTH-03: WebSocket connection with Firebase-issued token should be accepted."""
    sim, firebase = auth03_simulator

    async with aiohttp.ClientSession() as session:
        # Get token from Firebase
        sign_in_url = (
            f"http://localhost:{auth03_config.firebase_port}/v1/accounts:signInWithPassword"
        )
        async with session.post(
            sign_in_url,
            json={"email": "test@example.com", "password": "testpassword123"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            token = data["idToken"]

    # Connect to WebSocket with Firebase token
    url = f"ws://localhost:{auth03_config.ws_port}?token={token}&supportedAccessories=APC"
    async with websockets.connect(url) as ws:
        # First message: device list
        msg1 = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data1 = json.loads(msg1)
        assert data1["command"] == "EVENT_APC_WIFI_LIST"

        # Second message: state
        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data = json.loads(msg)
        assert data["command"] == "EVENT_APC_STATE"


@pytest.fixture
def auth04_config():
    """Configuration for AUTH-04 test with short token expiry."""
    return Config(
        firebase_port=PORT_FB + 4,
        ws_port=PORT_WS + 4,
        firebase_credentials={"test@example.com": "testpassword123"},
        token_expiry=1,  # 1 second expiry for testing
        valid_tokens=[],
    )


@pytest_asyncio.fixture
async def auth04_firebase(auth04_config):
    """Start Firebase mock for AUTH-04."""
    mock = FirebaseMock(auth04_config)
    await mock.start()
    yield mock
    await mock.stop()


@pytest.mark.asyncio
async def test_auth04_token_expiry_simulation(auth04_firebase, auth04_config):
    """AUTH-04: Token expiry simulation works correctly."""
    # Get token from Firebase
    async with aiohttp.ClientSession() as session:
        sign_in_url = (
            f"http://localhost:{auth04_config.firebase_port}/v1/accounts:signInWithPassword"
        )
        async with session.post(
            sign_in_url,
            json={"email": "test@example.com", "password": "testpassword123"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            token = data["idToken"]

    # Token should be valid immediately
    assert auth04_firebase.token_manager.is_token_valid(token)

    # Wait for token to expire (1 second + buffer)
    await asyncio.sleep(1.5)

    # Token should now be expired
    assert not auth04_firebase.token_manager.is_token_valid(token)


# =============================================================================
# SIGN IN TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_sign_in_valid_credentials(firebase_mock, auth_config):
    """Sign in with valid credentials returns tokens."""
    async with aiohttp.ClientSession() as session:
        url = f"http://localhost:{auth_config.firebase_port}/v1/accounts:signInWithPassword"
        async with session.post(
            url,
            json={"email": "test@example.com", "password": "testpassword123"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "idToken" in data
            assert "refreshToken" in data
            assert data["email"] == "test@example.com"
            assert data["registered"] is True


@pytest.mark.asyncio
async def test_sign_in_invalid_password(firebase_mock, auth_config):
    """Sign in with invalid password returns 401."""
    async with aiohttp.ClientSession() as session:
        url = f"http://localhost:{auth_config.firebase_port}/v1/accounts:signInWithPassword"
        async with session.post(
            url,
            json={"email": "test@example.com", "password": "wrongpassword"},
        ) as resp:
            assert resp.status == 401


@pytest.mark.asyncio
async def test_sign_in_unknown_email(firebase_mock, auth_config):
    """Sign in with unknown email returns 401."""
    async with aiohttp.ClientSession() as session:
        url = f"http://localhost:{auth_config.firebase_port}/v1/accounts:signInWithPassword"
        async with session.post(
            url,
            json={"email": "unknown@example.com", "password": "password123"},
        ) as resp:
            assert resp.status == 401
