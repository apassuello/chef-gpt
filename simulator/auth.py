"""
Token generation and validation for the Anova Simulator.

Implements mock Firebase authentication tokens.

Reference: docs/SIMULATOR-SPECIFICATION.md Section 2
"""

import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Token expiration time in seconds (1 hour, same as real Firebase)
TOKEN_EXPIRY_SECONDS = 3600


@dataclass
class TokenInfo:
    """Information about a token."""

    user_id: str
    email: str
    issued_at: float
    expires_at: float
    refresh_token: str

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return time.time() > self.expires_at


class TokenManager:
    """
    Manages mock Firebase tokens.

    Handles:
    - Token generation for valid credentials
    - Token refresh
    - Token validation
    - Token expiry simulation
    """

    def __init__(
        self,
        valid_credentials: dict | None = None,
        token_expiry: int = TOKEN_EXPIRY_SECONDS,
    ):
        """
        Initialize token manager.

        Args:
            valid_credentials: Dict mapping email -> password for valid users
            token_expiry: Token expiration time in seconds
        """
        self.valid_credentials = valid_credentials or {
            "test@example.com": "testpassword123",
        }
        self.token_expiry = token_expiry

        # Active tokens: token_string -> TokenInfo
        self._tokens: dict[str, TokenInfo] = {}
        # Refresh tokens: refresh_token -> token_string
        self._refresh_tokens: dict[str, str] = {}

        # For test control: force token expiry
        self._force_expired: bool = False

    def authenticate(self, email: str, password: str) -> tuple[str | None, str | None, str | None]:
        """
        Authenticate with email/password.

        Args:
            email: User email
            password: User password

        Returns:
            Tuple of (id_token, refresh_token, error_message)
            On success: (token, refresh_token, None)
            On failure: (None, None, error_message)
        """
        # Check credentials
        expected_password = self.valid_credentials.get(email)
        if expected_password is None:
            logger.warning(f"Authentication failed: unknown email {email}")
            return None, None, "EMAIL_NOT_FOUND"

        if password != expected_password:
            logger.warning(f"Authentication failed: invalid password for {email}")
            return None, None, "INVALID_PASSWORD"

        # Generate tokens
        id_token = self._generate_id_token(email)
        refresh_token = self._generate_refresh_token()

        # Store token info
        now = time.time()
        token_info = TokenInfo(
            user_id=self._email_to_user_id(email),
            email=email,
            issued_at=now,
            expires_at=now + self.token_expiry,
            refresh_token=refresh_token,
        )
        self._tokens[id_token] = token_info
        self._refresh_tokens[refresh_token] = id_token

        logger.info(f"Authentication successful for {email}")
        return id_token, refresh_token, None

    def refresh_token(self, refresh_token: str) -> tuple[str | None, str | None]:
        """
        Exchange refresh token for new ID token.

        Args:
            refresh_token: The refresh token

        Returns:
            Tuple of (new_id_token, error_message)
        """
        id_token = self._refresh_tokens.get(refresh_token)
        if id_token is None:
            logger.warning("Token refresh failed: invalid refresh token")
            return None, "INVALID_REFRESH_TOKEN"

        token_info = self._tokens.get(id_token)
        if token_info is None:
            logger.warning("Token refresh failed: token not found")
            return None, "TOKEN_NOT_FOUND"

        # Generate new ID token
        new_id_token = self._generate_id_token(token_info.email)
        new_refresh_token = self._generate_refresh_token()

        # Update token info
        now = time.time()
        new_token_info = TokenInfo(
            user_id=token_info.user_id,
            email=token_info.email,
            issued_at=now,
            expires_at=now + self.token_expiry,
            refresh_token=new_refresh_token,
        )

        # Replace old tokens
        del self._tokens[id_token]
        del self._refresh_tokens[refresh_token]
        self._tokens[new_id_token] = new_token_info
        self._refresh_tokens[new_refresh_token] = new_id_token

        logger.info(f"Token refreshed for {token_info.email}")
        return new_id_token, None

    def validate_token(self, token: str) -> TokenInfo | None:
        """
        Validate an ID token.

        Args:
            token: The ID token to validate

        Returns:
            TokenInfo if valid, None otherwise
        """
        if self._force_expired:
            logger.info("Token validation failed: forced expiry enabled")
            return None

        token_info = self._tokens.get(token)
        if token_info is None:
            return None

        if token_info.is_expired():
            logger.info(f"Token expired for {token_info.email}")
            return None

        return token_info

    def is_token_valid(self, token: str) -> bool:
        """Check if a token is valid."""
        return self.validate_token(token) is not None

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.

        Args:
            token: The ID token to revoke

        Returns:
            True if token was revoked, False if not found
        """
        token_info = self._tokens.pop(token, None)
        if token_info is None:
            return False

        self._refresh_tokens.pop(token_info.refresh_token, None)
        logger.info(f"Token revoked for {token_info.email}")
        return True

    def force_expiry(self, enabled: bool = True):
        """
        Force all tokens to be considered expired.

        Useful for testing token expiry scenarios.
        """
        self._force_expired = enabled
        logger.info(f"Forced token expiry: {enabled}")

    def _generate_id_token(self, email: str) -> str:
        """Generate a mock Firebase ID token."""
        # Create a JWT-like structure (not cryptographically secure, just for testing)
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": "https://securetoken.google.com/mock-project",
            "aud": "mock-project",
            "auth_time": int(time.time()),
            "user_id": self._email_to_user_id(email),
            "sub": self._email_to_user_id(email),
            "iat": int(time.time()),
            "exp": int(time.time() + self.token_expiry),
            "email": email,
            "email_verified": True,
        }

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        # Add a random signature for uniqueness
        signature = secrets.token_urlsafe(32)

        return f"{header_b64}.{payload_b64}.{signature}"

    def _generate_refresh_token(self) -> str:
        """Generate a refresh token."""
        return secrets.token_urlsafe(64)

    def _email_to_user_id(self, email: str) -> str:
        """Convert email to a deterministic user ID."""
        return hashlib.sha256(email.encode()).hexdigest()[:28]
