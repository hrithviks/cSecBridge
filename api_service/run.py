'''
# Application entry point for the CSecBridge API Service.

This script is the main executable to start the Flask application. It handles
the crucial initial setup and error handling before the application server
begins.

Its primary responsibilities are:
1.  Importing the application factory (`create_app`).
2.  Wrapping the application creation in a multi-stage exception block to
    gracefully catch fatal errors during startup. It provides specific, clear
    error messages for different failure modes (config vs. service connection)
    and logs a full traceback for unexpected code errors.
3.  Creating the application instance using the factory.
4.  Providing a simple unit testing block to run on local dev server
'''

import sys
import traceback

# Catch import errors as part of startup
try:
    from config import ConfigLoadError
    from psycopg2 import OperationalError
    from redis.exceptions import ConnectionError
except ImportError as e:
    print(f'FATAL: A required library is not installed: {e}', file=sys.stderr)
    sys.exit(1)

try:
    # Load and create application
    from app import create_app
    app = create_app()
except ConfigLoadError as e:
    # Handle specific, known configuration errors.
    print(f'FATAL: Configuration Error. {e}', file=sys.stderr)
    sys.exit(1)
except (OperationalError, ConnectionError) as e:
    # Handle known service connection errors.
    print(
        f'FATAL: Could not connect to a required service (DB/Redis).'
        f'Please check service health and connection settings. Details: {e}',
        file=sys.stderr
    )
    sys.exit(1)
except Exception as e:
    # Handle any other unexpected exception during startup.
    # This is likely a bug, so we print the full traceback for debugging.
    print(
        'FATAL: An unexpected error occurred during application startup.',
        file=sys.stderr
    )
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':

    # Unit Testing
    app.run(debug=True, port=5001)