"""
Backend Data Access Layer (DAL) for the CSecBridge AWS Worker.

This module encapsulates all direct interactions with the backend data stores
(PostgreSQL and Redis). It provides a clean, abstracted API for the main
worker logic to use, separating business logic from data access logic.
All database operations within a single function are transactional.
"""

import logging
import json
from datetime import datetime, timezone
from psycopg2 import OperationalError, ProgrammingError, DataError
from redis.exceptions import ConnectionError

# Import dependent modules using relative and absolute imports
from .clients import redis_client, db_pool
from errors import DBError, RedisError, ExtensionInitError, BackendDataError
from .config import config
from .helpers import get_error_log_extra

# Define what this module exposes
__all__ = [
    "get_job_from_redis_queue",
    "push_job_to_redis_queue",
    "validate_job_status_on_db",
    "update_job_status_on_db"
]

# Setup logger for the module
log = logging.getLogger(__name__)

# SQL Query Constants
_SQL_SELECT_STATUS = """
    select status from csb_requests where correlation_id = %s;
"""

_SQL_UPDATE_REQUESTS = """
    update csb_requests set status = %s, last_upd_time_stamp = %s
    where correlation_id = %s;
"""

_SQL_INSERT_AUDIT = """
    insert into csb_requests_audit (correlation_id, status, audit_log)
    values (%s, %s, %s);
"""

_SQL_INSERT_REF = """
    insert into csb_requests_ref (cloud_provider, correlation_id, ref_id)
    values (%s, %s, %s);
"""

# A constant, shared context for all logs originating from this module
_LOG_CONTEXT = {
    "context": "AWS-WORKER-BACKEND"
}

######################
# Database Functions #
######################

def _get_db_connection():
    """
    Gets a connection from the PostgreSQL pool.

    Raises:
        ExtensionInitError: If the pool is unable to provide a connection.

    Returns:
        psycopg2.connection: A connection object from the pool.
    """
    
    return db_pool.getconn()


def update_job_status_on_db(correlation_id,
                            status,
                            audit_log,
                            cloud_provider='aws',
                            aws_ref=None):
    """
    Updates the final status of the job in the database.
    This function performs all database writes in a single transaction.

    Args:
        correlation_id (str): The unique ID of the job.
        status (str): The final status to set (e.g., 'SUCCESS', 'FAILED').
        audit_log (str): A descriptive message for the audit log.
        cloud_provider (str, optional): The cloud provider (e.g., 'aws').
        aws_ref (str, optional): The external reference ID from the API call.

    Raises:
        DBError: If the database update or commit fails.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "service": "PostgreSQL",
        "operation": "update_status",
        "correlation_id": correlation_id
    }
    conn = None
    try:
        conn = _get_db_connection()

        # All database transactions for the request
        with conn.cursor() as cur:

            # Update the main 'csb_requests' table
            log.debug(
                "Executing database update.",
                extra={
                    **log_extra,
                    "table_name": "csb_requests"
                }
            )
            cur.execute(
                _SQL_UPDATE_REQUESTS,
                (status, datetime.now(timezone.utc), correlation_id)
            )

            # Insert into the 'csb_requests_audit' table
            log.debug(
                "Executing database insert.",
                extra={
                    **log_extra,
                    "table_name": "csb_requests_audit"
                }
            )
            cur.execute(
                _SQL_INSERT_AUDIT,
                (correlation_id, status, audit_log)
            )

            # If the status is success, insert into 'csb_requests_ref'
            if status == "success" and aws_ref and cloud_provider:
                log.debug(
                    "Executing database insert",
                    extra={
                        **log_extra,
                        "table_name": "csb_requests_ref"
                    }
                )
                cur.execute(
                    _SQL_INSERT_REF,
                    (cloud_provider, correlation_id, aws_ref)
                )

        # Commit all 3 operations at once.
        conn.commit()
        log.info(
            f"Database operations completed.",
            extra={
                **log_extra,
                "status": status
            }
        )
    # Database connection errors
    except OperationalError as e:
        log.error(
            'Postgresql DB operation failed. Transaction will be rolled back.',
            extra=get_error_log_extra(e,log_extra)
        )
        if conn:
            conn.rollback()
        raise DBError('Postgresql DB operation error.') from e
    # Database query errors (eg. Insufficient privileges, Data mismatches etc.)
    except (ProgrammingError, DataError) as e:
        log.warning(
            'PostgreSQL query execution error.',
            extra=get_error_log_extra(e,log_extra)
        )
        raise BackendDataError('Postgresql database query error.') from e
    finally:
        if conn:
            db_pool.putconn(conn)


def validate_job_status_on_db(correlation_id):
    """
    Checks if a job is legitimate by verifying its correlation_id
    exists in the database and is in a 'PENDING' state.

    Args:
        correlation_id (str): The ID of the job to check.

    Raises:
        DBError: If the database connection or query fails.

    Returns:
        bool: True if the job is valid and PENDING, False otherwise.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "service": "PostgreSQL",
        "operation": "validate_status",
        "correlation_id": correlation_id
    }
    log.debug("Validating job legitimacy", extra=log_extra)

    try:
        # Assign and check the status of connection obtained from pool
        conn = None
        if not (conn := _get_db_connection()):
            raise ExtensionInitError("Failed to get a database connection.")

        with conn.cursor() as cur:
            log.debug(
                    "Executing database select.",
                    extra={
                        **log_extra,
                        "table_name": "csb_requests"
                    }
                )
            cur.execute(_SQL_SELECT_STATUS, (correlation_id,))
            result = cur.fetchone()

            # If there are no valid rows in the database
            if not result:
                log.warning(
                    'No data found in database. Validation failed.',
                    extra={
                        **log_extra,
                        "table_name": "csb_requests"
                    }
                )
                return False

            # Check the result - should be "queued"
            status = result[0]
            if status != 'queued':
                log.warning(
                    'Unexpected status on database. Validation failed.',
                    extra={
                        **log_extra,
                        "table_name": "csb_requests",
                        "status": status
                    }
                )
                return False

        log.debug('Job validation successful',
                 extra=log_extra)
        return True

    # Database connection errors
    except OperationalError as e:
        log.warning(
            'PostgreSQL database service operation error.',
            extra=get_error_log_extra(e, log_extra)
        )
        raise DBError('Postgresql database service operation error.') from e

    # Database query errors (eg. Insufficient privileges, Data mismatches etc.)
    except (ProgrammingError, DataError) as e:
        log.warning(
            'PostgreSQL query execution error.',
            extra=get_error_log_extra(e, log_extra)
        )
        raise BackendDataError('Postgresql database query error.') from e
    finally:
        if conn:
            db_pool.putconn(conn)

###################
# Redis Functions #
###################

def get_job_from_redis_queue(queue_name, time_out=0):
    """
    Gets a single job from the AWS Redis queue using a blocking pop.

    Args:
        queue_name (str): The name of the redis queue object.
        time_out (int, optional): The block timeout. 0 blocks indefinitely.

    Raises:
        RedisError: If the connection to Redis fails.

    Returns:
        tuple: A (queue_name, job_payload_bytes) tuple or None if timeout.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "service": "Redis",
        "operation": "read_queue",
        "queue_name": queue_name
    }

    try:
        log.debug("Executing Redis BRPOP.", extra=log_extra)

        # Blocking Right Pop: Waits for a job from the tail of the list
        return redis_client.brpop([queue_name], timeout=time_out)
    except ConnectionError as e:
        log.error("BRPOP failed.", extra=get_error_log_extra(e, log_extra))
        raise RedisError("Redis connection error during BRPOP.") from e


def push_job_to_redis_queue(queue_name, job_payload):
    """
    Pushes a failed job back to the *head* of the queue for immediate retry.

    Args:
        queue_name (str): The name of the redis queue object.
        job_payload (dict): The job payload to re-queue.

    Raises:
        RedisError: If the connection to Redis fails.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "service": "Redis",
        "operation": "write_queue",
        "queue_name": queue_name,
        "correlation_id": job_payload.get('correlation_id')
    }

    try:
        log.debug("Executing Redis LPUSH.", extra=log_extra)
        redis_client.lpush(queue_name, json.dumps(job_payload))
        log.debug("Job successfully re-queued for retry.", extra=log_extra)
    except ConnectionError as e:
        log.critical("LPUSH failed.", extra=get_error_log_extra(e, log_extra))
        raise RedisError("Redis connection error during LPUSH.") from e