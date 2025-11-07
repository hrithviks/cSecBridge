"""
# Configuration loader for the CSecBridge AWS Worker Service

This module is responsible for loading, validating, and providing access to all
configuration parameters required by the application. It follows a strict,
fail-fast approach:

1.  It reads all settings from environment variables defined in the container.
2.  It performs validation to ensure all required variables are present and
    that numeric values are correctly formatted.
3.  If validation fails, it raises a custom `ConfigLoadError` with a clear
    error message. This exception is intended to be caught by the main
    application entry point (`worker.py`), which will then exit.
4.  It exposes the configuration via a singleton instance named `config`, which
    provides read-only properties for security, preventing accidental
    modification at runtime.

This module should be imported before any other application component that
requires configuration.

Classes:
    _Config: The internal class that performs loading and provides properties.

Instances:
    config: The singleton, read-only instance of the _Config class that the
            rest of the application should import and use.
"""

import os
import logging
from errors import ConfigLoadError

# Define APIs of the module
__all__ = ["config"]

# Configure logging early to catch fatal errors
log = logging.getLogger(__name__)


class _Config:
    """
    Holds immutable configuration data loaded from environment variables.
    Exposes settings via read-only properties.
    """

    def __init__(self):
        self._load_and_validate_env()

    # Public Read-only Properties
    @property
    def AWS_REGION(self):
        """The AWS region for the Boto3 client."""
        return self._AWS_REGION

    @property
    def AWS_ACCESS_KEY(self):
        """The AWS access key for the master Boto3 session."""
        return self._AWS_ACCESS_KEY

    @property
    def AWS_SECRET_KEY(self):
        """The AWS secret key for the master Boto3 session."""
        return self._AWS_SECRET_KEY

    @property
    def REDIS_HOST(self):
        """The hostname for the Redis service."""
        return self._REDIS_HOST

    @property
    def REDIS_PORT(self):
        """The port for the Redis service."""
        return self._REDIS_PORT

    @property
    def REDIS_USERNAME(self):
        """The ACL username for the Redis service."""
        return self._REDIS_USERNAME

    @property
    def REDIS_PASSWORD(self):
        """The ACL password for the Redis service."""
        return self._REDIS_PASSWORD

    @property
    def REDIS_QUEUE_AWS(self):
        """The name of the Redis list to use as the job queue."""
        return self._REDIS_QUEUE_AWS

    @property
    def DB_HOST(self):
        """The hostname for the PostgreSQL database."""
        return self._DB_HOST

    @property
    def DB_PORT(self):
        """The port for the PostgreSQL database."""
        return self._DB_PORT

    @property
    def DB_USER(self):
        """The username for the PostgreSQL database."""
        return self._DB_USER

    @property
    def DB_PASSWORD(self):
        """The password for the PostgreSQL database."""
        return self._DB_PASSWORD

    @property
    def DB_NAME(self):
        """The name of the PostgreSQL database."""
        return self._DB_NAME

    @property
    def DB_POOL_MAX_CONN(self):
        """The maximum number of connections for the DB pool."""
        return self._DB_POOL_MAX_CONN

    def _load_and_validate_env(self):
        """
        Internal method to load and validate all required environment variables.
        Raises ConfigLoadError if any validation fails.
        """

        required_vars = [
            "AWS_REGION",
            "AWS_ACCESS_KEY",
            "AWS_SECRET_KEY",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_USERNAME",
            "REDIS_PASSWORD",
            "REDIS_QUEUE_AWS",
            "DB_HOST",
            "DB_PORT",
            "DB_USER",
            "DB_PASSWORD",
            "DB_NAME",
            "DB_POOL_MAX_CONN"
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            error_msg = (
                "FATAL ERROR: Missing required environment variables: "
                f"{', '.join(missing_vars)}"
            )
            raise ConfigLoadError(error_msg)

        try:
            # Load all values into private attributes
            self._AWS_REGION = os.getenv('AWS_REGION')
            self._AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
            self._AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
            self._REDIS_HOST = os.getenv('REDIS_HOST')
            self._REDIS_PORT = int(os.getenv('REDIS_PORT'))
            self._REDIS_USERNAME = os.getenv('REDIS_USERNAME')
            self._REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
            self._REDIS_QUEUE_AWS = os.getenv('REDIS_QUEUE_AWS')
            self._DB_HOST = os.getenv('DB_HOST')
            self._DB_PORT = int(os.getenv('DB_PORT'))
            self._DB_USER = os.getenv('DB_USER')
            self._DB_PASSWORD = os.getenv('DB_PASSWORD')
            self._DB_NAME = os.getenv('DB_NAME')
            self._DB_POOL_MAX_CONN = int(os.getenv('DB_POOL_MAX_CONN'))
        except (ValueError, TypeError) as e:
            error_msg = (
                "FATAL ERROR: Malformed environment variable. "
                "Ensure ports and connection counts are integers."
            )
            raise ConfigLoadError(error_msg) from e

# Singleton instance of the configuration
config = _Config()
