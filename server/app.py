"""
Flask application factory.

Creates and configures the Flask application with all routes, middleware,
and error handlers. Uses the application factory pattern for flexibility
and testability.

Reference: CLAUDE.md Section "Component Responsibilities > app.py"
"""

import logging
from typing import Any

from flask import Flask

from .config import Config
from .middleware import register_error_handlers, setup_request_logging
from .routes import api

logger = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> Flask:
    """
    Application factory for creating Flask app instances.

    The application factory pattern allows for:
    - Multiple app instances (testing, production, etc.)
    - Different configurations per environment
    - Easier testing with isolated app instances

    Args:
        config: Optional Config object. If not provided,
                loads from environment using Config.load()

    Returns:
        Configured Flask application instance

    Raises:
        RuntimeError: If required configuration is missing

    Example usage:
        # Production
        app = create_app()
        app.run()

        # Testing with custom config
        test_config = Config(ANOVA_EMAIL="test@example.com", ...)
        app = create_app(config=test_config)

    Reference: CLAUDE.md Section "Component Responsibilities > app.py" (lines 150-158)
    """
    # 1. Create Flask app instance
    app = Flask(__name__)

    # 2. Load configuration
    if config is None:
        config = Config.load()

    # 3. Store config in app.config for access by routes
    app.config['ANOVA_CONFIG'] = config
    app.config['API_KEY'] = config.API_KEY
    app.config['DEBUG'] = config.DEBUG

    # 4. Configure logging
    configure_logging(app)

    # 5. Register routes blueprint
    app.register_blueprint(api)

    # 6. Setup request logging middleware
    setup_request_logging(app)

    # 7. Register error handlers
    register_error_handlers(app)

    # 8. Log startup message
    logger.info("Anova Sous Vide Assistant API initialized")
    logger.info(f"Debug mode: {config.DEBUG}")

    return app


def configure_logging(app: Flask) -> None:
    """
    Configure application logging.

    Sets up logging format, level, and handlers based on configuration.

    Args:
        app: Flask application instance

    Log format example:
        2025-01-09 12:34:56,789 - INFO - Request: GET /health from 192.168.1.100

    Reference: CLAUDE.md Section "Code Patterns > 4. Logging Pattern" (lines 439-515)
    """
    # Set logging level based on DEBUG config
    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO

    # Configure log format
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Set Flask app logger to same level
    app.logger.setLevel(log_level)


def init_app_context(app: Flask, config: dict[str, Any]) -> None:
    """
    Initialize application context with configuration.

    NOTE: This function is not currently used. Configuration initialization
    is handled directly in create_app() for simplicity.

    Stores configuration values needed by routes and middleware.

    Args:
        app: Flask application instance
        config: Configuration dictionary
    """
    # Not implemented - config initialization happens in create_app()
    pass


# ==============================================================================
# ENTRY POINT FOR DEVELOPMENT SERVER
# ==============================================================================

if __name__ == '__main__':
    """
    Run development server.

    Usage:
        python -m server.app

    For production, use gunicorn:
        gunicorn "server.app:create_app()"

    Reference: CLAUDE.md Section "Quick Start Commands > Development Server" (lines 55-68)
    """
    print("=" * 70)
    print("ANOVA SOUS VIDE ASSISTANT - DEVELOPMENT SERVER")
    print("=" * 70)
    print("WARNING: This is a development server. Do not use in production.")
    print("For production, use: gunicorn 'server.app:create_app()'")
    print("=" * 70)
    print()

    # Create and run the app
    app = create_app()
    config = app.config['ANOVA_CONFIG']

    print(f"Starting server on {config.HOST}:{config.PORT}")
    print(f"Health check: http://{config.HOST}:{config.PORT}/health")
    print()

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )


# ==============================================================================
# IMPLEMENTATION NOTES
# ==============================================================================
# Component wiring order:
# 1. Create Flask app
# 2. Load configuration
# 3. Configure logging
# 4. Register routes (Blueprint)
# 5. Register middleware (request/response logging)
# 6. Register error handlers (exception → HTTP mapping)
#
# Error handler registration:
# - ValidationError → 400 Bad Request
# - DeviceOfflineError → 503 Service Unavailable
# - DeviceBusyError → 409 Conflict
# - NoActiveCookError → 404 Not Found
# - AnovaAPIError → 500 Internal Server Error
# - AuthenticationError → 500 Internal Server Error
#
# Reference: CLAUDE.md Section "Code Patterns > 1. Error Handling Pattern" (lines 229-233)
