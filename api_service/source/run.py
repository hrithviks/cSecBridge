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

_STARTUP_CONTEXT = {"context": "SYSTEM-STARTUP"}

# Default logging configuration.
try:
    from logging_config import setup_logging
    setup_logging()
except ImportError as e:
    # Fallback to plain text if logging config fails.
    logging.basicConfig(level=logging.DEBUG)
    logging.warning(f"Could not import logging_config. Falling back to basic logging. {str(e)}")

# Main application process starts here
try:
    from config import ConfigLoadError, initialize_config

    # Initialize logger
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    # Initialize config to load and validate environment variables
    log.debug("Initializing configuration.", extra=_STARTUP_CONTEXT)
    initialize_config()
    
    # Import and call the application factory
    from app import create_app
    from app.errors import ExtentionError, BackendServerError, APIServerError

    log.debug("Creating application factory.", extra=_STARTUP_CONTEXT)
    app = create_app()
    log.debug("Application factory created.", extra=_STARTUP_CONTEXT)

# Exceptions from config module
except ConfigLoadError as e:
    log.critical("Environment configuration validation failed.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)
# Exceptions from extensions module
except ExtentionError as e:
    log.critical("Extension initialization failed.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

# Runtime errors during initialization
except RuntimeError as e:
    log.critical("Runtime error during application initialization.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

# Exceptions from backend module
except BackendServerError as e:
    log.critical("Backend service communication failed.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

# System errors from routes module
except APIServerError as e:
    log.critical("Unrecoverable system error in application routing.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

# Handle library import errors
except ImportError as e:
    log.critical("Application library import failed.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

# All unhandled exceptions
except Exception as e:
    log.critical("Unhandled exception during application startup.", exc_info=True, extra=_STARTUP_CONTEXT)
    sys.exit(1)

if __name__ == '__main__':

    # Unit Testing
    app.run(debug=True, port=5001)