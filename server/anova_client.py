"""
Client for Anova Cloud API.

Handles:
- Firebase authentication (email/password → JWT tokens)
- Token refresh when expired
- Device control (start cook, stop cook, get status)
- Error handling and retries

API Flow:
1. Authenticate with Firebase using Anova credentials
2. Get JWT access token and refresh token
3. Use access token for Anova API calls
4. Refresh token when it expires (Firebase tokens expire after 1 hour)

Reference: CLAUDE.md Section "Component Responsibilities"
Reference: docs/02-security-architecture.md Section 4 (authentication flows)
Reference: docs/03-component-architecture.md Section 4.3
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests

from .config import Config
from .exceptions import (
    AnovaAPIError,
    AuthenticationError,
    DeviceBusyError,
    DeviceOfflineError,
    NoActiveCookError,
)

logger = logging.getLogger(__name__)


class AnovaClient:
    """
    Client for communicating with Anova Cloud API.

    Handles Firebase authentication and Anova device control.
    Maintains JWT tokens and refreshes them automatically when expired.

    Attributes:
        config: Configuration with credentials and device ID
        session: Persistent HTTP session for connection reuse
        _access_token: Firebase JWT access token (expires after 1 hour)
        _refresh_token: Firebase refresh token (long-lived)
        _token_expiry: When the access token expires

    Example usage:
        config = Config.load()
        client = AnovaClient(config)
        client.start_cook(temperature_c=65.0, time_minutes=90)
        status = client.get_status()
        client.stop_cook()

    Reference: docs/02-security-architecture.md Section 4
    """

    # Firebase API endpoints
    FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

    # Anova API endpoints
    ANOVA_BASE_URL = "https://anovaculinary.io/api/v1"

    # Token refresh buffer (refresh if expiring within this time)
    TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def __init__(self, config: Config):
        """
        Initialize Anova client.

        Args:
            config: Configuration with ANOVA_EMAIL, ANOVA_PASSWORD, DEVICE_ID

        Raises:
            AuthenticationError: If authentication fails

        Reference: COMP-ANOVA-01 (docs/03-component-architecture.md Section 4.3.1)
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # Initialize empty token state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: datetime | None = None

        # Authenticate immediately
        self._authenticate()

        logger.info("AnovaClient initialized successfully")

    def _authenticate(self) -> None:
        """
        Authenticate with Firebase to get JWT tokens.

        Makes POST request to Firebase authentication API with email/password.
        Stores access_token, refresh_token, and token_expiry.

        Raises:
            AuthenticationError: If authentication fails

        API Request:
            POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}
            Body: {"email": "...", "password": "...", "returnSecureToken": true}

        API Response:
            {"idToken": "...", "refreshToken": "...", "expiresIn": "3600"}

        Reference: docs/02-security-architecture.md Section 4.1
        """
        firebase_api_key = os.getenv('FIREBASE_API_KEY')
        if not firebase_api_key:
            raise AuthenticationError("FIREBASE_API_KEY environment variable not set")

        url = f"{self.FIREBASE_AUTH_URL}?key={firebase_api_key}"
        payload = {
            "email": self.config.ANOVA_EMAIL,
            "password": self.config.ANOVA_PASSWORD,
            "returnSecureToken": True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code != 200:
                error_msg = response.json().get("error", {}).get("message", "Unknown error")
                raise AuthenticationError(f"Firebase authentication failed: {error_msg}")

            data = response.json()
            self._access_token = data["idToken"]
            self._refresh_token = data["refreshToken"]

            # Calculate token expiry (expiresIn is in seconds)
            expires_in = int(data["expiresIn"])
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info("Firebase authentication successful")

        except requests.exceptions.RequestException as e:
            raise AuthenticationError(f"Network error during authentication: {e!s}") from e
        except KeyError as e:
            raise AuthenticationError(f"Unexpected response format from Firebase: missing {e}") from e

    def _refresh_access_token(self) -> None:
        """
        Refresh the access token using the refresh token.

        Makes POST request to Firebase token refresh endpoint.
        Updates access_token and token_expiry.

        Raises:
            AuthenticationError: If refresh fails

        API Request:
            POST https://securetoken.googleapis.com/v1/token?key={API_KEY}
            Body: {"grant_type": "refresh_token", "refresh_token": "..."}

        API Response:
            {"id_token": "...", "refresh_token": "...", "expires_in": "3600"}

        Reference: docs/02-security-architecture.md Section 4.1
        """
        firebase_api_key = os.getenv('FIREBASE_API_KEY')
        if not firebase_api_key:
            raise AuthenticationError("FIREBASE_API_KEY environment variable not set")

        url = f"{self.FIREBASE_REFRESH_URL}?key={firebase_api_key}"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code != 200:
                # Refresh failed, need to re-authenticate
                logger.warning("Token refresh failed, re-authenticating")
                self._authenticate()
                return

            data = response.json()
            self._access_token = data["id_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)

            # Calculate token expiry
            expires_in = int(data["expires_in"])
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info("Access token refreshed successfully")

        except requests.exceptions.RequestException as e:
            # Network error, try full re-authentication
            logger.warning(f"Network error during token refresh: {e}, re-authenticating")
            self._authenticate()
        except KeyError as e:
            logger.warning(f"Unexpected response format during token refresh: {e}, re-authenticating")
            self._authenticate()

    def _ensure_authenticated(self) -> None:
        """
        Ensure we have a valid access token.

        Checks if token is expired or will expire within TOKEN_REFRESH_BUFFER (5 minutes).
        If so, refreshes the token using the refresh token.

        Raises:
            AuthenticationError: If token refresh or re-authentication fails
        """
        if self._token_expiry is None:
            # No token, need to authenticate
            self._authenticate()
            return

        # Check if token is expired or will expire soon
        now = datetime.now()
        if now >= (self._token_expiry - self.TOKEN_REFRESH_BUFFER):
            logger.info("Access token expired or expiring soon, refreshing")
            self._refresh_access_token()

    def _api_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """
        Make an authenticated request to the Anova API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/devices/{device_id}")
            **kwargs: Additional arguments passed to requests (json, params, etc.)

        Returns:
            Response JSON as dictionary

        Raises:
            DeviceOfflineError: If device returns 404
            AnovaAPIError: For other API errors
        """
        # Ensure we have a valid token
        self._ensure_authenticated()

        # Build full URL
        url = f"{self.ANOVA_BASE_URL}{endpoint}"

        # Add authorization header
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f"Bearer {self._access_token}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=10,
                **kwargs
            )

            # Handle specific status codes
            if response.status_code == 404:
                raise DeviceOfflineError("Device not found or offline")

            if response.status_code >= 400:
                error_msg = response.json().get("error", "Unknown error")
                raise AnovaAPIError(f"Anova API error ({response.status_code}): {error_msg}", response.status_code)

            return response.json()

        except requests.exceptions.Timeout as e:
            raise AnovaAPIError("Request timeout", 503) from e
        except requests.exceptions.RequestException as e:
            raise AnovaAPIError(f"Network error: {e!s}", 503) from e

    def _map_state(self, anova_state: str) -> str:
        """
        Map Anova device state to standard state names.

        Args:
            anova_state: State from Anova API

        Returns:
            Normalized state: "idle", "preheating", "cooking", or "done"
        """
        state_map = {
            'idle': 'idle',
            'preheating': 'preheating',
            'cooking': 'cooking',
            'maintaining': 'cooking',  # Maintaining temp = cooking
            'done': 'done',
            'stopped': 'idle'
        }

        normalized = anova_state.lower()
        return state_map.get(normalized, 'idle')

    def get_status(self) -> dict[str, Any]:
        """
        Get current device status.

        Returns:
            Dict with current status:
                {
                    "device_online": bool,
                    "state": str,  # idle, preheating, cooking, done
                    "current_temp_celsius": float,
                    "target_temp_celsius": float|None,
                    "time_remaining_minutes": int|None,
                    "time_elapsed_minutes": int|None,
                    "is_running": bool
                }

        Raises:
            DeviceOfflineError: If device is offline (404)
            AnovaAPIError: For other API errors

        Reference: COMP-ANOVA-01 (docs/03-component-architecture.md Section 4.3.1)
        """
        endpoint = f"/devices/{self.config.DEVICE_ID}"

        try:
            data = self._api_request('GET', endpoint)

            # Parse Anova response
            state = self._map_state(data.get('cookerState', 'idle'))
            is_running = state in ['preheating', 'cooking']

            # Convert times from seconds to minutes
            time_remaining = data.get('cookTimeRemaining')
            time_elapsed = data.get('cookTimeElapsed')

            return {
                'device_online': True,
                'state': state,
                'current_temp_celsius': float(data.get('currentTemperature', 0)),
                'target_temp_celsius': float(data['targetTemperature']) if data.get('targetTemperature') else None,
                'time_remaining_minutes': int(time_remaining // 60) if time_remaining else None,
                'time_elapsed_minutes': int(time_elapsed // 60) if time_elapsed else None,
                'is_running': is_running
            }

        except DeviceOfflineError:
            raise
        except AnovaAPIError:
            raise

    def start_cook(self, temperature_c: float, time_minutes: int) -> dict[str, Any]:
        """
        Start a cooking session.

        Args:
            temperature_c: Target temperature in Celsius (validated by caller)
            time_minutes: Cook time in minutes (validated by caller)

        Returns:
            Dict with cook start confirmation:
                {
                    "success": bool,
                    "message": str,
                    "cook_id": str,
                    "device_state": str,
                    "target_temp_celsius": float,
                    "time_minutes": int,
                    "estimated_completion": str  # ISO8601 timestamp
                }

        Raises:
            DeviceOfflineError: If device is offline
            DeviceBusyError: If device is already cooking
            AnovaAPIError: For other API errors

        Reference: COMP-ANOVA-01 (docs/03-component-architecture.md Section 4.3.1)
        """
        # Check if device is already cooking
        try:
            status = self.get_status()
            if status['is_running']:
                raise DeviceBusyError("Device is already cooking. Stop current cook first.")
        except DeviceOfflineError:
            raise

        # Start cook command
        endpoint = f"/devices/{self.config.DEVICE_ID}/cook"
        payload = {
            "temperature": temperature_c,
            "timer": time_minutes * 60  # Convert to seconds
        }

        data = self._api_request('POST', endpoint, json=payload)

        # Generate cook_id if not provided
        cook_id = data.get('cookId', f"cook_{int(datetime.now().timestamp())}")

        # Calculate estimated completion
        estimated_completion = datetime.now() + timedelta(minutes=time_minutes)

        return {
            'success': True,
            'message': 'Cook started successfully',
            'cook_id': cook_id,
            'device_state': 'preheating',
            'target_temp_celsius': temperature_c,
            'time_minutes': time_minutes,
            'estimated_completion': estimated_completion.isoformat() + 'Z'
        }

    def stop_cook(self) -> dict[str, Any]:
        """
        Stop the current cooking session.

        Returns:
            Dict with stop confirmation:
                {
                    "success": bool,
                    "message": str,
                    "device_state": str,
                    "final_temp_celsius": float | None
                }

        Raises:
            DeviceOfflineError: If device is offline
            NoActiveCookError: If no cook is active
            AnovaAPIError: For other API errors

        Reference: COMP-ANOVA-01 (docs/03-component-architecture.md Section 4.3.1)
        Reference: docs/05-api-specification.md lines 254-263
        """
        # Check if there's an active cook and capture final temperature
        try:
            status = self.get_status()
            if not status['is_running']:
                raise NoActiveCookError("No active cook to stop")

            # Capture current temperature before stopping
            final_temp = status['current_temp_celsius']
        except DeviceOfflineError:
            raise

        # Stop cook command
        endpoint = f"/devices/{self.config.DEVICE_ID}/stop"
        self._api_request('POST', endpoint)

        return {
            'success': True,
            'message': 'Cook stopped successfully',
            'device_state': 'idle',
            'final_temp_celsius': final_temp
        }


# ==============================================================================
# SECURITY NOTES
# ==============================================================================
# CRITICAL - Token handling security:
# ✅ Store tokens in memory only (never log or persist to disk)
# ✅ Refresh tokens before they expire (proactive refresh with 5-min buffer)
# ✅ Use HTTPS for all API calls
#
# ❌ NEVER log access tokens or refresh tokens
# ❌ NEVER store tokens in files or databases
# ❌ NEVER expose tokens in error messages
#
# Reference: CLAUDE.md Section "Anti-Patterns > 1. Never Log Credentials or Tokens"
