"""
# Application entry point for the CSecBridge API Service.

This script is the main executable to start the Flask application. It handles
the crucial initial setup and error handling before the application server
begins.

Application flow:
- Import and initialize configuration data.
- Import and create application factory to run the Flask server.
- Multi-stage exception handling for startup errors.
"""

import sys
import logging

_STARTUP_CONTEXT = {
    "context": "SYSTEM-STARTUP"
}

# Default logging configuration.
try:
    from logging_config import setup_logging
    setup_logging()
except ImportError:
    # Fallback to plain text if logging config fails.
    logging.basicConfig(level=logging.DEBUG)
    logging.warning(
        "Logging configuration not found. Falling back to basic logging."
    )

# Main application process starts here
try:
    from config import ConfigLoadError, initialize_config

    # Initialize logger
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    # Initialize config to load and validate environment variables
    log.debug(
        "Server configuration validation started.",
        extra=_STARTUP_CONTEXT
    )
    initialize_config()
    log.debug(
        "Server configuration validation successful.",
        extra=_STARTUP_CONTEXT
    )

    # Import and call the application factory
    from app import create_app

    log.debug(
        "Application factory initialization started.",
        extra=_STARTUP_CONTEXT
    )
    app = create_app()
    log.debug(
        "Application factory created successfully.",
        extra=_STARTUP_CONTEXT
    )

# Exceptions from config module
except ConfigLoadError:
    log.critical("Environment configuration validation failed.",
                 exc_info=True,
                 extra=_STARTUP_CONTEXT)
    sys.exit(1)

# All other exceptions
except Exception:
    log.critical(
        "Exception during application startup. Traceback available.",
        exc_info=True,
        extra=_STARTUP_CONTEXT
    )
    sys.exit(1)

if __name__ == '__main__':

    # Unit Testing
    app.run(debug=True, port=5001)
