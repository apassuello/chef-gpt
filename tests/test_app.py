"""
Tests for Flask application factory.

Tests the create_app() function, configuration loading, logging setup,
and application initialization.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from server.app import configure_logging, create_app
from server.config import Config


class TestCreateApp:
    """Tests for create_app() application factory."""

    @patch("server.app.AnovaWebSocketClient")
    def test_create_app_with_custom_config(self, mock_client_class):
        """Test creating app with custom config."""
        # Mock the WebSocket client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create custom config
        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-api-key",
            ANOVA_WEBSOCKET_URL="ws://test.example.com",
            DEBUG=True,
        )

        # Create app
        app = create_app(config=config)

        # Verify app created
        assert isinstance(app, Flask)
        assert app.config["API_KEY"] == "test-api-key"
        assert app.config["DEBUG"] is True
        assert app.config["ANOVA_CONFIG"] == config

        # Verify client initialized
        mock_client_class.assert_called_once_with(config)
        assert app.config["ANOVA_CLIENT"] == mock_client

    @patch("server.app.AnovaWebSocketClient")
    @patch("server.app.Config.load")
    def test_create_app_with_default_config(self, mock_load, mock_client_class):
        """Test creating app without providing config (loads from env)."""
        # Mock config loading
        mock_config = Config(
            PERSONAL_ACCESS_TOKEN="anova-loaded-token",
            API_KEY="loaded-api-key",
            DEBUG=False,
        )
        mock_load.return_value = mock_config

        # Mock WebSocket client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create app without config
        app = create_app()

        # Verify config loaded from environment
        mock_load.assert_called_once()
        assert app.config["ANOVA_CONFIG"] == mock_config
        assert app.config["API_KEY"] == "loaded-api-key"
        assert app.config["DEBUG"] is False

    @patch("server.app.AnovaWebSocketClient")
    def test_create_app_registers_routes(self, mock_client_class):
        """Test that routes are registered."""
        mock_client_class.return_value = MagicMock()

        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-key",
        )

        app = create_app(config=config)

        # Verify routes exist
        with app.test_client() as client:
            # Health endpoint should exist
            response = client.get("/health")
            assert response.status_code == 200

    @patch("server.app.AnovaWebSocketClient")
    def test_create_app_websocket_client_failure(self, mock_client_class):
        """Test app creation fails gracefully when WebSocket client fails."""
        # Mock WebSocket client to raise exception
        mock_client_class.side_effect = Exception("Connection failed")

        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-key",
        )

        # App creation should fail with RuntimeError
        with pytest.raises(RuntimeError, match="Failed to connect to Anova API"):
            create_app(config=config)

    @patch("server.app.AnovaWebSocketClient")
    @patch("server.app.atexit.register")
    def test_create_app_registers_shutdown_handler(
        self, mock_atexit, mock_client_class
    ):
        """Test that shutdown handler is registered for WebSocket client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-key",
        )

        create_app(config=config)

        # Verify atexit.register was called
        assert mock_atexit.called

        # Get the registered function and call it
        shutdown_func = mock_atexit.call_args[0][0]
        shutdown_func()

        # Verify it calls shutdown on the client
        mock_client.shutdown.assert_called_once()


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def test_configure_logging_debug_mode(self):
        """Test logging configuration in debug mode."""
        app = Flask(__name__)
        app.config["DEBUG"] = True

        configure_logging(app)

        # Verify debug level set
        assert app.logger.level == logging.DEBUG

    def test_configure_logging_production_mode(self):
        """Test logging configuration in production mode."""
        app = Flask(__name__)
        app.config["DEBUG"] = False

        configure_logging(app)

        # Verify info level set
        assert app.logger.level == logging.INFO

    def test_configure_logging_no_debug_config(self):
        """Test logging configuration with no DEBUG config."""
        app = Flask(__name__)
        # Don't set DEBUG config

        configure_logging(app)

        # Should default to INFO
        assert app.logger.level == logging.INFO


class TestAppIntegration:
    """Integration tests for the full app."""

    @patch("server.app.AnovaWebSocketClient")
    def test_app_request_logging_setup(self, mock_client_class):
        """Test that request logging middleware is set up."""
        mock_client_class.return_value = MagicMock()

        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-key",
        )

        app = create_app(config=config)

        # Make a request to trigger logging
        with app.test_client() as client:
            response = client.get("/health")
            assert response.status_code == 200

        # If we get here, logging middleware didn't crash
        # (More detailed logging tests are in test_middleware.py)

    @patch("server.app.AnovaWebSocketClient")
    def test_app_error_handlers_registered(self, mock_client_class):
        """Test that error handlers are registered."""
        mock_client_class.return_value = MagicMock()

        config = Config(
            PERSONAL_ACCESS_TOKEN="anova-test-token",
            API_KEY="test-key",
        )

        app = create_app(config=config)

        # Verify error handlers exist by checking Flask's error_handler_spec
        # Error handlers are registered for ValidationError, DeviceOfflineError, etc.
        # (Detailed error handler tests are in test_middleware.py)
        assert app.error_handler_spec is not None
