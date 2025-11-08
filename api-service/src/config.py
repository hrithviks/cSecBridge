"""
# Configuration loader for the CSecBridge API Service.

This module is responsible for loading, validating, and providing access to all
configuration parameters required by the application. It follows a strict,
fail-fast approach:

1.  It reads all settings from environment variables defined in the container.
2.  It performs validation to ensure all required variables are present and
    that numeric values are correctly formatted.
3.  If validation fails, it raises a custom `ConfigLoadError` with a clear
    error message, causing the application to exit on startup. This prevents
    the service from running in a misconfigured state.
4.  It exposes the configuration via a singleton instance named `config`, which
    provides read-only properties for security, preventing accidental
    modification at runtime.

This module should be imported before any other application component that
requires configuration.

Classes:
    ConfigLoadError: Custom exception for fatal configuration loading errors.
    _Config: The internal class that performs loading and provides properties.

Instances:
    config: The singleton, read-only instance of the _Config class that the
            rest of the application should import and use.
"""

import os

__all__ = ['ConfigLoadError', 'initialize_config']


class ConfigLoadError(Exception):
    """
    Custom exception for all fatal errors during configuration load.
    """
    pass


class _Config:
    """
    Loads, validates, and provides read-only access to app configuration.
    The loading and validation logic is encapsulated within this class.
    """

    def __init__(self):
        pass

    #############################################
    # Read-only properties of the configuration #
    #############################################
    @property
    def API_AUTH_TOKEN(self):
        return self._API_AUTH_TOKEN

    @property
    def CACHE_TTL_SECONDS(self):
        return self._CACHE_TTL_SECONDS

    @property
    def POSTGRES_HOST(self):
        return self._POSTGRES_HOST

    @property
    def POSTGRES_PORT(self):
        return self._POSTGRES_PORT

    @property
    def POSTGRES_USER(self):
        return self._POSTGRES_USER

    @property
    def POSTGRES_PASSWORD(self):
        return self._POSTGRES_PASSWORD

    @property
    def POSTGRES_DB(self):
        return self._POSTGRES_DB

    @property
    def POSTGRES_MAX_CONN(self):
        return self._POSTGRES_MAX_CONN

    @property
    def POSTGRES_SSL_ENABLED(self):
        return self._POSTGRES_SSL_ENABLED

    @property
    def POSTGRES_SSL_CA_CERT(self):
        return self._POSTGRES_SSL_CA_CERT

    @property
    def REDIS_HOST(self):
        return self._REDIS_HOST

    @property
    def REDIS_PORT(self):
        return self._REDIS_PORT

    @property
    def REDIS_USER(self):
        return self._REDIS_USER

    @property
    def REDIS_PASSWORD(self):
        return self._REDIS_PASSWORD

    @property
    def REDIS_SSL_ENABLED(self):
        return self._REDIS_SSL_ENABLED

    @property
    def REDIS_SSL_CA_CERT(self):
        return self._REDIS_SSL_CA_CERT

    @property
    def ALLOWED_ORIGIN(self):
        return self._ALLOWED_ORIGIN

    ############################
    # Configuration validation #
    ############################
    def _load_and_validate_env(self):
        """
        Performs the strict loading and validation of all env variables.
        Stores the final values in private instance attributes.
        """

        # Define a set of required base variables
        required_env_vars = [
            "API_AUTH_TOKEN",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_USER",
            "REDIS_PASSWORD",
            "POSTGRES_MAX_CONN",
            "ALLOWED_ORIGIN"
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        # Check if SSL option is enabled for postgres
        self._POSTGRES_SSL_ENABLED = os.getenv('POSTGRES_SSL_ENABLED',
                                               'false').lower() == 'true'
        if (self._POSTGRES_SSL_ENABLED
                and not os.getenv('POSTGRES_SSL_CA_CERT')):
            missing_vars.append('POSTGRES_SSL_CA_CERT')

        # Check if SSL option is enabled for redis
        self._REDIS_SSL_ENABLED = os.getenv('REDIS_SSL_ENABLED',
                                            'false').lower() == 'true'
        if self._REDIS_SSL_ENABLED and not os.getenv('REDIS_SSL_CA_CERT'):
            missing_vars.append('REDIS_SSL_CA_CERT')

        # Exit if required variables are missing
        if missing_vars:
            error_message = f'Fatal error: Missing required environment \
                variables {', '.join(missing_vars)}'
            raise ConfigLoadError(error_message)

        # Load validated config into private attributes
        try:
            self._API_AUTH_TOKEN = os.getenv('API_AUTH_TOKEN')
            self._CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 300))
            self._POSTGRES_HOST = os.getenv('POSTGRES_HOST')
            self._POSTGRES_PORT = int(os.getenv('POSTGRES_PORT'))
            self._POSTGRES_USER = os.getenv('POSTGRES_USER')
            self._POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
            self._POSTGRES_DB = os.getenv('POSTGRES_DB')
            self._POSTGRES_MAX_CONN = int(os.getenv('POSTGRES_MAX_CONN'))
            self._POSTGRES_SSL_CA_CERT = os.getenv('POSTGRES_SSL_CA_CERT')
            self._REDIS_HOST = os.getenv('REDIS_HOST')
            self._REDIS_PORT = int(os.getenv('REDIS_PORT'))
            self._REDIS_USER = os.getenv('REDIS_USER')
            self._REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
            self._REDIS_SSL_CA_CERT = os.getenv('REDIS_SSL_CA_CERT')
            self._ALLOWED_ORIGIN = os.getenv('ALLOWED_ORIGIN')
        except (ValueError, TypeError) as e:
            # Catch errors from int() if a variable is not a valid number
            error_message = 'Fatal error: Malformed numeric \
                environment variable.'
            raise ConfigLoadError(error_message) from e


# The global config object starts as None.
config = None


def initialize_config():
    """
    Creates and validates the global config instance. This function should be
    called once at application startup.
    """
    global config
    if config is None:
        config_instance = _Config()
        config_instance._load_and_validate_env()
        config = config_instance
    return config
