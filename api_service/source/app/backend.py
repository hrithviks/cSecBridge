'''
# Data access layer for the CSecBridge API Service.

This module contains all the functions responsible for interacting with the
database (PostgreSQL) and the cache/queue (Redis). It abstracts the data
storage logic away from the API routes, allowing for cleaner, more testable,
and reusable code.

Functions in this module are designed to be called by the route handlers and
are passed the necessary connection objects for the current request context.

Error log streaming to container is only for operations that do not propagate
exceptions to the calling module.
'''

import json
import psycopg2
import redis
from datetime import datetime
from flask import current_app
from psycopg2.extras import RealDictCursor
from app.errors import DBError, RedisError

# Expose only the required functions
__all__ = ['create_new_request', 'get_request_by_id', 'DBError', 'RedisError']

# Insert statment for requests table
_INSERT_TO_REQUESTS = 'INSERT INTO REQUESTS \
    (CLIENT_REQ_ID, \
    CORRELATION_ID, \
    ACCOUNT_ID, \
    PRINCIPAL, \
    ROLE, \
    ACTION, \
    STATUS, \
    CLOUD_PROVIDER, \
    REQUESTED_TIME_STAMP, \
    LAST_UPDATED_TIME_STAMP) \
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'

# Insert statement for requests audit table
_INSERT_TO_REQUESTS_AUDIT = 'INSERT INTO REQUESTS_AUDIT \
    (CORRELATION_ID, \
    ACTION, \
    STATUS, \
    ERROR_TEXT, \
    PROCESSED_TIME_STAMP) \
    VALUES (%s, %s, %s, %s, %s)'

# Select statement to retrieve data from requests table
_SELECT_FROM_REQUESTS = 'SELECT * FROM REQUESTS WHERE CORRELATION_ID = %s'

# Keys to filter data from table, for response
_RESPONSE_KEYS = ['CLIENT_REQ_ID',
                  'CORRELATION_ID',
                  'STATUS'
                  'REQUSTED_TIME_STAMP',
                  'LAST_UPDATED_TIME_STAMP']

# Redis cache active duration
_REDIS_CACHE_TTL = 300

# Initial status for all new requests.
_INIT_STATUS = 'PENDING'

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

    Args:
        db_conn: A PostgreSQL connection object from the connection pool.
        redis_conn: The Redis client instance.
        backend_data: A dictionary containing the full job details.
    """

    log_context = {"correlation_id": backend_data["correlation_id"],
                   "context": "SYSTEM-API"}

    with db_conn.cursor() as cur:
        try:
            # Insert into the requests table
            cur.execute(_INSERT_TO_REQUESTS, (
                        backend_data['client_request_id'],
                        backend_data['correlation_id'],
                        backend_data['account_id'],
                        backend_data['principal'],
                        backend_data['role'],
                        backend_data['action'],
                        _INIT_STATUS,
                        backend_data['target_cloud'],
                        backend_data['received_at'],
                        backend_data['received_at']
                    )
                )
        
            # Insert into the audit table
            cur.execute(_INSERT_TO_REQUESTS_AUDIT, (
                        backend_data['correlation_id'],
                        backend_data['action'],
                        _INIT_STATUS,
                        None,
                        backend_data['received_at']
                )
            )
        except psycopg2.Error as e:
            error_message = f'DB insert failed for {backend_data["correlation_id"]}'
            raise DBError(f'{error_message}') from e
        
        # Push the data to redis queue
        try:
            queue_name = f'queue:{backend_data["target_cloud"]}'
            redis_conn.lpush(queue_name, json.dumps(backend_data))
        except redis.exceptions.RedisError as e:
            error_message = f'Redis LPUSH failed for {backend_data["correlation_id"]}'
            raise RedisError(f'{error_message}') from e

        # Populate the redis cache with the initial status
        try:
            _set_cache(redis_conn, backend_data['correlation_id'], _INIT_STATUS)
        except redis.exceptions.RedisError as e:
            current_app.logger.warning(f'Redis set cache failed for {backend_data["correlation_id"]}: {e}',
                                       extra=log_context)

def get_request_by_id(db_conn, redis_conn, correlation_id):
    """
    Retrieves the status of a request, implementing the cache-aside pattern.
    It returns the raw data as a dictionary or None.

    Args:
        db_conn: A PostgreSQL connection object from the connection pool.
        redis_conn: The Redis client instance.
        correlation_id: The UUID of the request to retrieve.

    Returns:
        A dictionary containing the request status, or None if not found.
    """
    log_context = {"correlation_id": correlation_id,
                   "context": "SYSTEM-API"}

    cache_key = f'cache:status:{correlation_id}'

    # 1. Check cache first
    try:
        cached_status = redis_conn.get(cache_key)
        if cached_status:
            current_app.logger.debug('Redis GET successful.', extra=log_context)
            return json.loads(cached_status)
    except redis.exceptions.RedisError as e:
        current_app.logger.warning(f'Redis GET failed for {cache_key}: {e}',
                                   extra=log_context)
    current_app.logger.debug('Redis cache miss.', extra=log_context)

    # 2. On cache miss or Redis error, query the database
    try:
        with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_SELECT_FROM_REQUESTS, (correlation_id,))
            request_status = cur.fetchone()
    except psycopg2.Error as e:
        raise DBError(f'DB select failed for {correlation_id}') from e

    if not request_status:
        raise DBError(f'Request not found for correlation id {correlation_id}')

    # Ensure all datetime objects are ISO 8601 strings
    for key, value in request_status.items():
        if isinstance(value, datetime):
            request_status[key] = value.isoformat()

    # 3. Populate cache for next run
    try:
        current_app.logger.debug('Caching the status.', extra=log_context)
        status = request_status['STATUS']
        _set_cache(redis_conn, correlation_id, status)
    except redis.exceptions.RedisError as e:
        current_app.logger.warning(f'Redis set cache failed for {correlation_id}: {e}',
                                   extra=log_context)
        
    current_app.logger.debug('Status cached to redis.', extra=log_context)
    return {key: request_status[key] for key in _RESPONSE_KEYS}