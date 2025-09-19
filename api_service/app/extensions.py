'''
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
'''

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS
import redis
from psycopg2 import pool
from config import config

# Define the public APIs of this module
__all__ = ['limiter', 'talisman', 'cors', 'db_pool', 'redis_client']

# Internal configuration for rate setter
_redis_auth = f":{config.REDIS_PASSWORD}@" if config.REDIS_PASSWORD else ""
_redis_scheme = "rediss://" if config.REDIS_SSL_ENABLED else "redis://"
_redis_uri_for_limiter = (
    f"{_redis_scheme}{_redis_auth}"
    f"{config.REDIS_HOST}:{config.REDIS_PORT}/0"
)

limiter = Limiter(
    get_remote_address,
    storage_uri=_redis_uri_for_limiter,
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
)

# Flask security extensions
talisman = Talisman()
cors = CORS()

# Internal configuration for database connection pool.
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

db_pool = pool.ThreadedConnectionPool(1, 
                                      config.POSTGRES_MAX_CONN,
                                      **_db_conn_params)

# Internal connection setup for redis client
_redis_conn_params = {
    "host": config.REDIS_HOST,
    "port": config.REDIS_PORT,
    "password": config.REDIS_PASSWORD,
    "db": 0,
    "decode_responses": True
}
if config.REDIS_SSL_ENABLED:
    _redis_conn_params['ssl'] = True
    _redis_conn_params['ssl_ca_certs'] = config.REDIS_SSL_CA_CERT
    
redis_client = redis.Redis(**_redis_conn_params)

# Issue ping on the redis client for fail-fast approach
redis_client.ping()