"""
Firebase Authentication Mock Server.

Provides mock endpoints for Firebase authentication:
- /v1/token - Token refresh (Firebase Token Exchange API)
- /v1/accounts:signInWithPassword - Email/password login

Reference: docs/SIMULATOR-SPECIFICATION.md Section 2
"""

import asyncio
import json
import logging
from typing import Optional

from aiohttp import web

from .auth import TokenManager
from .config import Config

logger = logging.getLogger(__name__)


class FirebaseMock:
    """
    Mock Firebase Authentication Server.

    Implements the Firebase REST API endpoints for token operations.
    """

    def __init__(self, config: Config, token_manager: Optional[TokenManager] = None):
        """
        Initialize Firebase mock.

        Args:
            config: Simulator configuration
            token_manager: Token manager (creates new one if None)
        """
        self.config = config
        self.token_manager = token_manager or TokenManager(
            valid_credentials=config.firebase_credentials,
            token_expiry=config.token_expiry,
        )

        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._running = False

    async def start(self, host: str = "localhost"):
        """
        Start the Firebase mock server.

        Args:
            host: Host to bind to
        """
        self._app = web.Application()
        self._setup_routes()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, host, self.config.firebase_port)
        await self._site.start()

        self._running = True
        logger.info(f"Firebase mock started on http://{host}:{self.config.firebase_port}")

    async def stop(self):
        """Stop the Firebase mock server."""
        self._running = False

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

        logger.info("Firebase mock stopped")

    def _setup_routes(self):
        """Setup HTTP routes."""
        self._app.router.add_post("/v1/token", self._handle_token_refresh)
        self._app.router.add_post(
            "/v1/accounts:signInWithPassword", self._handle_sign_in
        )
        self._app.router.add_get("/health", self._handle_health)

    async def _handle_token_refresh(self, request: web.Request) -> web.Response:
        """
        Handle token refresh request.

        POST /v1/token
        Body: grant_type=refresh_token&refresh_token=<token>

        Returns:
            {
                "access_token": "...",
                "expires_in": "3600",
                "token_type": "Bearer",
                "refresh_token": "...",
                "id_token": "...",
                "user_id": "...",
                "project_id": "mock-project"
            }
        """
        try:
            # Parse form data or JSON
            content_type = request.content_type
            if "application/x-www-form-urlencoded" in content_type:
                data = await request.post()
                grant_type = data.get("grant_type")
                refresh_token = data.get("refresh_token")
            else:
                data = await request.json()
                grant_type = data.get("grant_type")
                refresh_token = data.get("refresh_token")

            if grant_type != "refresh_token":
                return self._error_response(
                    "INVALID_GRANT_TYPE",
                    "grant_type must be refresh_token",
                    400,
                )

            if not refresh_token:
                return self._error_response(
                    "MISSING_REFRESH_TOKEN",
                    "refresh_token is required",
                    400,
                )

            new_token, error = self.token_manager.refresh_token(refresh_token)
            if error:
                return self._error_response(error, "Token refresh failed", 401)

            # Get the token info for the new token
            token_info = self.token_manager.validate_token(new_token)

            return web.json_response({
                "access_token": new_token,
                "expires_in": str(self.config.token_expiry),
                "token_type": "Bearer",
                "refresh_token": token_info.refresh_token,
                "id_token": new_token,
                "user_id": token_info.user_id,
                "project_id": "mock-project",
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return self._error_response("INTERNAL_ERROR", str(e), 500)

    async def _handle_sign_in(self, request: web.Request) -> web.Response:
        """
        Handle email/password sign in.

        POST /v1/accounts:signInWithPassword
        Body: {"email": "...", "password": "...", "returnSecureToken": true}

        Returns:
            {
                "kind": "identitytoolkit#VerifyPasswordResponse",
                "localId": "...",
                "email": "...",
                "displayName": "",
                "idToken": "...",
                "registered": true,
                "refreshToken": "...",
                "expiresIn": "3600"
            }
        """
        try:
            data = await request.json()
            email = data.get("email")
            password = data.get("password")

            if not email:
                return self._error_response("MISSING_EMAIL", "email is required", 400)
            if not password:
                return self._error_response(
                    "MISSING_PASSWORD", "password is required", 400
                )

            id_token, refresh_token, error = self.token_manager.authenticate(
                email, password
            )
            if error:
                status = 401 if error in ("INVALID_PASSWORD", "EMAIL_NOT_FOUND") else 400
                return self._error_response(error, "Authentication failed", status)

            token_info = self.token_manager.validate_token(id_token)

            return web.json_response({
                "kind": "identitytoolkit#VerifyPasswordResponse",
                "localId": token_info.user_id,
                "email": email,
                "displayName": "",
                "idToken": id_token,
                "registered": True,
                "refreshToken": refresh_token,
                "expiresIn": str(self.config.token_expiry),
            })

        except json.JSONDecodeError:
            return self._error_response("INVALID_JSON", "Invalid JSON body", 400)
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            return self._error_response("INTERNAL_ERROR", str(e), 500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok", "service": "firebase-mock"})

    def _error_response(
        self, error_code: str, message: str, status: int
    ) -> web.Response:
        """Build error response matching Firebase format."""
        return web.json_response(
            {
                "error": {
                    "code": status,
                    "message": error_code,
                    "errors": [
                        {
                            "message": error_code,
                            "domain": "global",
                            "reason": message,
                        }
                    ],
                }
            },
            status=status,
        )
