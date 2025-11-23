"""
# Data access layer for the CSecBridge API Service.

This module contains all the functions responsible for interacting with the
database (PostgreSQL) and the cache/queue (Redis). It abstracts the data
storage logic away from the API routes, allowing for cleaner, more testable,
and reusable code.

Functions in this module are designed to be called by the route handlers and
are passed the necessary connection objects for the current request context.

Error log streaming to container is only for operations that do not propagate
exceptions to the calling module.
"""

import json
import psycopg2
import redis
from datetime import datetime
from flask import current_app
from psycopg2.extras import RealDictCursor
from app.errors import DBError, RedisError

_SYSTEM_CONTEXT = {"context": "BACKEND-API"}

# Expose only the required functions
__all__ = [
    'create_new_request',
    'get_request_by_id',
    'DBError',
    'RedisError'
]

# Insert statment for requests table
_INSERT_TO_REQUESTS = '''INSERT INTO CSB_REQUESTS
    (CLIENT_REQ_ID,
    CORRELATION_ID,
    ACCOUNT_ID,
    PRINCIPAL,
    ENTITLEMENT,
    ACTION,
    STATUS,
    CLOUD_PROVIDER,
    REQ_TIME_STAMP,
    LAST_UPD_TIME_STAMP)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

# Insert statement for requests audit table
_INSERT_TO_REQUESTS_AUDIT = '''INSERT INTO CSB_REQUESTS_AUDIT
    (CORRELATION_ID,
    STATUS,
    AUDIT_LOG,
    AUDIT_TIMESTAMP)
    VALUES (%s, %s, %s, %s)'''

# Select statement to retrieve data from requests table
_SELECT_FROM_REQUESTS = 'SELECT CLIENT_REQ_ID, \
    CORRELATION_ID, \
    STATUS, \
    REQ_TIME_STAMP, \
    LAST_UPD_TIME_STAMP FROM CSB_REQUESTS WHERE CORRELATION_ID = %s'

# Keys to filter data from table, for response
_RESPONSE_KEYS = ['correlation_id',
                  'status']

# Redis cache active duration
_REDIS_CACHE_TTL = 300

# Initial status for all new requests.
_INIT_STATUS = 'queued'


def _set_err_log_context(excp, correlation_id):
    """ Function to set extra context for error logging."""

    return {
        "correlation_id": correlation_id,
        "error_type": type(excp).__name__,
        "error_message": str(excp),
        "context": "BACKEND-API"
    }


def _set_log_context(correlation_id):
    """ Function to set extra context for normal logging."""

    return {
        "correlation_id": correlation_id,
        "context": "BACKEND-API"
    }


def _set_cache(redis_conn, correlation_id, status):
    """Internal function to update the redis cache."""

    cache_key = f'cache:status:{correlation_id}'
    cache_data = {
        "correlation_id": correlation_id,
        "status": status,
    }
    redis_conn.set(
        cache_key,
        json.dumps(cache_data),
        ex=_REDIS_CACHE_TTL
    )


def create_new_request(db_conn, redis_conn, backend_data):
    """
    Handles the transactional database insert and Redis operations for a new
    request. This function ensures that the DB is the source of truth.

    Request Flow:
    - Logs new request to "requests" table
    - Logs the initial status to "requests_audit" table
    - Push request data to redis queue for processing by the worker service
    - Populate the redis cache with the initial status

    Args:
        db_conn: A PostgreSQL connection object from the connection pool.
        redis_conn: The Redis client instance.
        backend_data: A dictionary containing the full job details.

    Returns:
        None
    """

    correlation_id = backend_data["correlation_id"]

    with db_conn.cursor() as cur:
        try:
            # Insert into the requests table
            cur.execute(
                _INSERT_TO_REQUESTS,
                (
                    backend_data['client_request_id'],
                    correlation_id,
                    backend_data['account_id'],
                    backend_data['principal'],
                    backend_data['entitlement'],
                    backend_data['action'],
                    _INIT_STATUS,
                    backend_data['target_cloud'],
                    backend_data['received_at'],
                    backend_data['received_at']
                )
            )
            current_app.logger.debug(
                'Postgres insert successful.',
                extra={
                    "table_name": "requests",
                    **_set_log_context(correlation_id)
                }
            )

            # Insert into the audit table
            cur.execute(
                _INSERT_TO_REQUESTS_AUDIT,
                (
                    correlation_id,
                    _INIT_STATUS,
                    "API request received.",
                    backend_data['received_at']
                )
            )
            current_app.logger.debug(
                'Postgres insert successful.',
                extra={
                    "table_name": "requests_audit",
                    **_set_log_context(correlation_id)
                }
            )
        except psycopg2.Error as e:
            current_app.logger.error(
                'Postgres operation failed.',
                exc_info=False,
                extra=_set_err_log_context(e, correlation_id)
            )
            raise DBError

        # Push the data to redis queue
        try:
            queue_name = f'queue:{backend_data["target_cloud"]}'
            redis_conn.lpush(queue_name, json.dumps(backend_data))
        except redis.exceptions.RedisError as e:
            current_app.logger.error(
                'Redis queue operation failed.',
                exc_info=False,
                extra=_set_err_log_context(e, correlation_id)
            )
            raise RedisError
        else:
            current_app.logger.debug(
                'Redis push successful.',
                extra={
                    "queue_name": queue_name,
                    **_SYSTEM_CONTEXT
                }
            )

        # Populate the redis cache with the initial status
        try:
            _set_cache(redis_conn, correlation_id, _INIT_STATUS)
        except redis.exceptions.RedisError as e:
            current_app.logger.warning(
                'Redis cache operation failed.',
                exc_info=False,
                extra=_set_err_log_context(e, correlation_id)
            )
        else:
            current_app.logger.debug(
                'Redis cache successful.',
                extra=_set_log_context(correlation_id)
            )


def get_request_by_id(db_conn, redis_conn, correlation_id):
    """
    Retrieves the status of a request, implementing the cache-aside pattern.
    It returns the raw data as a dictionary or None.

    Request Flow:
    - Check redis cache for the correlation id
    - If cache miss, query database for status
    - Populate cache for next run

    Args:
        db_conn: A PostgreSQL connection object from the connection pool.
        redis_conn: The Redis client instance.
        correlation_id: The UUID of the request to retrieve.

    Returns:
        A dictionary containing the request status, or None if not found.
    """

    cache_key = f'cache:status:{correlation_id}'

    # 1. Check cache first
    try:
        cached_status = redis_conn.get(cache_key)
        current_app.logger.debug(
            'Redis cache lookup initiated.',
            extra=_set_log_context(correlation_id)
        )
        if cached_status:
            current_app.logger.debug(
                'Redis GET successful.',
                extra=_set_log_context(correlation_id)
            )
            return json.loads(cached_status)
    except redis.exceptions.RedisError as e:
        current_app.logger.warning(
            'Redis GET failed.',
            extra=_set_err_log_context(e, correlation_id)
        )
    current_app.logger.warning(
        'Redis cache miss.',
        extra=_set_log_context(correlation_id)
    )

    # 2. On cache miss or Redis error, query the database
    current_app.logger.debug(
        'Postgres query initiated for request status.',
        extra=_set_log_context(correlation_id)
    )

    try:
        with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                _SELECT_FROM_REQUESTS,
                (correlation_id,)
            )
            request_status = cur.fetchone()
    except psycopg2.Error as e:
        current_app.logger.error(
            'Postgres select failed',
            extra={
                "table_name": "requests",
                **_set_err_log_context(e, correlation_id)
            }
        )
        raise DBError
    else:
        current_app.logger.debug(
            'Postgres select successful.',
            extra=_set_log_context(correlation_id)
        )

    # Return empty response if no data found
    if not request_status:
        current_app.logger.warning(
            'No data found for request ID.',
            extra=_set_log_context(correlation_id)
        )
        return {}

    # Ensure all datetime objects are ISO 8601 strings
    for key, value in request_status.items():
        if isinstance(value, datetime):
            request_status[key] = value.isoformat()

    # 3. Populate cache for next run
    try:
        current_app.logger.debug(
            'Writing status to Redis cache.',
            extra=_set_log_context(correlation_id)
        )
        status = request_status['status']

        # Invoke internal set cache method
        _set_cache(
            redis_conn,
            correlation_id,
            status
        )
    except redis.exceptions.RedisError as e:
        current_app.logger.warning(
            'Redis cache operation failed.',
            exc_info=False,
            extra=_set_err_log_context(e, correlation_id)
        )
        raise RedisError

    else:
        current_app.logger.debug(
            'Redis cache successful.',
            extra=_set_log_context(correlation_id)
        )

    return {key: request_status[key] for key in _RESPONSE_KEYS}
