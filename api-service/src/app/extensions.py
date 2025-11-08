"""
# Initializes all third-party extensions for the CSecBridge API Service.

This module is responsible for creating and configuring all global, shared
"extension" objects that the application uses. These objects are instantiated
only once when the application starts, following the singleton pattern,
to ensure efficiency and consistent state.

The extensions initialized here include:
-   limiter: An instance of Flask-Limiter for rate limiting API endpoints.
-   talisman: An instance of Flask-Talisman to set security HTTP headers.
-   cors: An instance of Flask-CORS to handle Cross-Origin Resource Sharing.
-   db_pool: A thread-safe connection pool for PostgreSQL, which manages a
    set of connections for the application to use.
-   redis_client: A client instance for connecting to Redis, used for caching
    and as a message queue broker.

This module adheres to a "fail-fast" principle. If a connection to a critical
service like PostgreSQL or Redis cannot be established during initialization,
it will raise an exception that will be caught by the main application entry
point, preventing the service from starting in a faulty state.
"""

import redis
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS
from psycopg2 import pool
from config import config
from app.errors import ExtentionError

_MODULE_LOG_CONTEXT = {"app_module": "EXTENSIONS"}

# Setup logger for the extentions module
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

# Define the public APIs of this module
__all__ = [
    'limiter',
    'talisman',
    'cors',
    'db_pool',
    'redis_client',
    'ExtentionError'
]


# Log context setter function
def _set_log_err_context(excp):

    return {
        "error_type": type(excp).__name__,
        "error_message": str(excp),
        "app_module": "EXTENSIONS"
    }


#######################################
# Rate setter extention for Flask app #
#######################################
_redis_scheme = "rediss://" if config.REDIS_SSL_ENABLED else "redis://"
_redis_uri_for_limiter = (
    f"{_redis_scheme}{config.REDIS_HOST}:{config.REDIS_PORT}/0"
)

_redis_limiter_storage_options = {
    "socket_connect_timeout": 30
}

if config.REDIS_USER:
    _redis_limiter_storage_options["username"] = config.REDIS_USER
if config.REDIS_PASSWORD:
    _redis_limiter_storage_options["password"] = config.REDIS_PASSWORD
if config.REDIS_SSL_ENABLED:
    _redis_limiter_storage_options["ssl"] = True
    _redis_limiter_storage_options["ssl_ca_certs"] = config.REDIS_SSL_CA_CERT

try:
    limiter = Limiter(
        get_remote_address,
        storage_uri=_redis_uri_for_limiter,
        storage_options=_redis_limiter_storage_options,
        strategy="fixed-window",
    )
except redis.exceptions.AuthenticationError as e:
    log.error(
        "Authentication error for rate limiter Redis.",
        exc_info=True,
        extra=_set_log_err_context(e)
    )
    raise ExtentionError
except redis.exceptions.ConnectionError as e:
    log.error(
        "Connection error for rate limiter Redis.",
        exc_info=True,
        extra=_set_log_err_context(e)
    )
    raise ExtentionError

######################################
# Security extenstions for Flask app #
######################################
talisman = Talisman()
cors = CORS()

#############################################
# Postgres database extention for Flask app #
#############################################
_db_conn_params = {
    "host": config.POSTGRES_HOST,
    "port": config.POSTGRES_PORT,
    "user": config.POSTGRES_USER,
    "password": config.POSTGRES_PASSWORD,
    "dbname": config.POSTGRES_DB
}
if config.POSTGRES_SSL_ENABLED:
    _db_conn_params['sslmode'] = 'verify-full'
    _db_conn_params['sslrootcert'] = config.POSTGRES_SSL_CA_CERT

try:
    db_pool = pool.ThreadedConnectionPool(
                1,
                config.POSTGRES_MAX_CONN,
                **_db_conn_params
            )
except ConnectionError as e:
    log.error(
        "Connection error for PostgreSQL pool.",
        exc_info=True,
        extra=_set_log_err_context(e)
    )
    raise ExtentionError

##############################
# Redis client for Flask app #
##############################
_redis_conn_params = {
    "host": config.REDIS_HOST,
    "port": config.REDIS_PORT,
    "username": config.REDIS_USER,
    "password": config.REDIS_PASSWORD,
    "db": 0,
    "decode_responses": True
}
if config.REDIS_SSL_ENABLED:
    _redis_conn_params['ssl'] = True
    _redis_conn_params['ssl_ca_certs'] = config.REDIS_SSL_CA_CERT

try:
    redis_client = redis.Redis(**_redis_conn_params)
    # Issue ping on the redis client for fail-fast approach
    redis_client.ping()
except redis.exceptions.ConnectionError as e:
    log.error(
        "Connection error for Redis client.",
        exc_info=True,
        extra=_set_log_err_context(e)
    )
    raise ExtentionError
