"""
# Initializes and configures all external service clients (Redis, DB, AWS).

This module follows a singleton pattern, creating one instance of each client
when the application starts. These instances are then imported by other parts
of the application (like the worker loop).

This ensures that connections are pooled and reused efficiently and that
startup fails fast if a required backend service is unavailable. If any
client fails to initialize, this module will raise an ExtensionInitError,
which should be caught by the main application entry point.
"""

import logging
import boto3
import redis
from psycopg2 import pool, OperationalError
from .config import config
from errors import ExtensionInitError
from .helpers import get_error_log_extra
 
# A constant, shared context for all logs originating from this module
_LOG_CONTEXT = {
    "context": "AWS-WORKER-CLIENT-INIT"
}

# Define the public API of this module.
__all__ = [
    "redis_client",
    "db_pool",
    "aws_session"
]

# Setup a module-level logger
log = logging.getLogger(__name__)


def _init_redis_client():
    """
    Initializes and pings the Redis client, which manages its own pool.

    Raises:
        ExtensionInitError: If the connection or authentication fails.

    Returns:
        redis.Redis: A thread-safe Redis client instance.
    """

    log_extra = {**_LOG_CONTEXT, "service": "Redis"}
    try:
        log.debug(
            "Initializing Redis client...",
            extra={
                **log_extra,
                "redis_host": config.REDIS_HOST,
                "redis_port": config.REDIS_PORT,
                "redis_user": config.REDIS_USERNAME
            }
        )
        redis_conn_params = {
            "host": config.REDIS_HOST,
            "port": config.REDIS_PORT,
            "username": config.REDIS_USERNAME,
            "password": config.REDIS_PASSWORD,
            "db": 0,
            "decode_responses": True,
            # Add SSL/TLS options here if needed
        }
        client = redis.Redis(**redis_conn_params)
        client.ping()
        log.debug(
            "Redis client connected and ping successful.",
            extra=log_extra
        )
        return client
    except redis.exceptions.ConnectionError as e:
        log.error(
            "Redis client connection failed.",
            extra=get_error_log_extra(e,log_extra)
        )
        # Re-raise as our custom exception for the entry point to catch
        raise ExtensionInitError(f"Redis connection error") from e
    except Exception as e:
        log.error(
            "Unhandled Redis client error.",
            extra=get_error_log_extra(e,log_extra)
        )
        raise ExtensionInitError("Unhandled Redis init error") from e


def _init_db_pool():
    """
    Initializes the PostgreSQL threaded connection pool.

    Raises:
        ExtensionInitError: If the connection to the database fails.

    Returns:
        psycopg2.pool.ThreadedConnectionPool: A thread-safe pool manager.
    """

    log_extra = {**_LOG_CONTEXT, "service": "PostgreSQL"}
    try:
        log.debug(
            "Initializing PostgreSQL connection pool...",
            extra={
                **log_extra,
                "db_name": config.DB_NAME,
                "db_host": config.DB_HOST,
                "db_user": config.DB_USER,
                "db_port": config.DB_PORT
            }
        )
        db_pool_instance = pool.ThreadedConnectionPool(
            1,  # minconn
            config.DB_POOL_MAX_CONN,  # maxconn
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            dbname=config.DB_NAME
            # Placeholder for SSL/TLS options
        )

        # Test the pool by getting and returning a connection
        conn = db_pool_instance.getconn()
        db_pool_instance.putconn(conn)
        log.debug(
            "PostgreSQL connection pool created and tested.",
            extra=log_extra
        )
        return db_pool_instance
    except OperationalError as e:
        log.error(
            "Database connection pool creation failed.",
            extra=get_error_log_extra(e,log_extra)
        )
        raise ExtensionInitError(f"Database connection error") from e
    except Exception as e:
        log.error(
            "Unhandled PostgreSQL init error",
            extra=get_error_log_extra(e,log_extra)
        )
        raise ExtensionInitError("Unhandled PostgreSQL init error") from e


def _init_aws_session():
    """
    Initializes the thread-safe Boto3 Session and validates credentials.

    Raises:
        ExtensionInitError: If credentials are invalid or STS is unreachable.

    Returns:
        boto3.Session: A thread-safe session to create clients/resources from.
    """

    log_extra = {**_LOG_CONTEXT, "service": "AWS-STS"}
    try:
        log.debug(
            "Initializing AWS Boto3 session...",
            extra=log_extra
        )
        session = boto3.Session(
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY
        )

        # Test credentials by making a simple, read-only call
        test_client = session.client('sts')
        test_client.get_caller_identity()
        log.debug(
            "AWS Boto3 session created and credentials validated.",
            extra=log_extra
        )
        return session

    # All exceptions handled here
    except Exception as e:
        log.error(
            "AWS Boto3 session initialization failed",
            extra=get_error_log_extra(e,log_extra)
        )
        raise ExtensionInitError(f"AWS credential validation failed") from e

# Singleton instances for each section.
redis_client = _init_redis_client()
db_pool = _init_db_pool()
aws_session = _init_aws_session()
