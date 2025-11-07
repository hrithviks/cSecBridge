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
from psycopg2 import OperationalError
from redis.exceptions import ConnectionError

# Import dependent modules using relative and absolute imports
from .clients import redis_client, db_pool
from errors import DBError, RedisError, ExtensionInitError
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


def get_error_log_extra(err, context):
    """
    Creates a standard 'extra' dict for logging exceptions.

    Args:
        err (Exception): The exception that occurred.
        context (str): The context string (e.g., 'SYSTEM-DB-UPDATE').

    Returns:
        dict: A dictionary formatted for the JSON logger.
    """
    return {
        "context": context,
        "error_type": type(err).__name__,
        "error_message": str(err)
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

    try:
        return db_pool.getconn()
    except OperationalError as e:
        log.error(
            "PostgreSQL pool connection failed.",
            extra=_get_error_log_extra(e, "SYSTEM-DB-INIT")
        )
        raise ExtensionInitError("Failed to get a database connection.") from e


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
        'context': 'SYSTEM-DB-UPDATE',
        'correlation_id': correlation_id
    }
    conn = None
    try:
        conn = _get_db_connection()

        # All database transactions for the request
        with conn.cursor() as cur:

            # Update the main 'csb_requests' table
            log.debug(
                "Executing UPDATE on csb_requests.",
                extra=log_extra
            )
            cur.execute(
                _SQL_UPDATE_REQUESTS,
                (status, datetime.now(timezone.utc), correlation_id)
            )

            # Insert into the 'csb_requests_audit' table
            log.debug(
                "Executing INSERT on csb_requests_audit.",
                extra=log_extra
            )
            cur.execute(
                _SQL_INSERT_AUDIT,
                (correlation_id, status, audit_log)
            )

            # If the status is success, insert into 'csb_requests_ref'
            if status == "SUCCESS" and aws_ref and cloud_provider:
                log.debug(
                    "Executing INSERT on csb_requests_ref.",
                    extra=log_extra
                )
                cur.execute(
                    _SQL_INSERT_REF,
                    (cloud_provider, correlation_id, aws_ref)
                )

        # Commit all 3 operations at once.
        conn.commit()
        log.info(
            f"Database finalized for status '{status}'.",
            extra=log_extra
        )

    except OperationalError as e:
        log.error(
            'Postgresql DB operation failed. Transaction will be rolled back.',
            extra=_get_error_log_extra(e, 'SYSTEM-DB-UPDATE')
        )
        if conn:
            conn.rollback()
        raise DBError('Postgresql DB Operation Error.') from e

    finally:
        if conn:
            db_pool.putconn(conn)


def validate_job_status_on_db(correlation_id, log_extra):
    """
    Checks if a job is legitimate by verifying its correlation_id
    exists in the database and is in a 'PENDING' state.

    Args:
        correlation_id (str): The ID of the job to check.
        log_extra (dict): The logging context.

    Raises:
        DBError: If the database connection or query fails.

    Returns:
        bool: True if the job is valid and PENDING, False otherwise.
    """

    log.info("Validating job legitimacy against database.", extra=log_extra)
    conn = None
    if not (conn := _get_db_connection()):
        raise ExtensionInitError("Failed to get a database connection.")

    try:
        with conn.cursor() as cur:
            cur.execute(_SQL_SELECT_STATUS, (correlation_id,))
            result = cur.fetchone()

            if not result:
                log.warning(
                    f'Job validation FAILED: Correlation ID {correlation_id} '
                    'not found in database. Discarding unauthorized job.',
                    extra=log_extra
                )
                return False

            status = result[0]
            if status != 'PENDING':
                log.warning(
                    f'Job validation SKIPPED: Job is a duplicate '
                    f'(status is "{status}"). Discarding.',
                    extra=log_extra
                )
                return False

        log.info('Job validation successful. Proceeding to lock.',
                 extra=log_extra)
        return True

    except OperationalError as e:
        log.warning(
            'PostgreSQL DB validation query failed.',
            extra=_get_error_log_extra(e, log_extra.get("context"))
        )
        raise DBError('Postgresql DB Operation Error.') from e
    finally:
        if conn:
            db_pool.putconn(conn)

###################
# Redis Functions #
###################

def get_job_from_redis_queue(time_out=0):
    """
    Gets a single job from the AWS Redis queue using a blocking pop.

    Args:
        time_out (int, optional): The block timeout. 0 blocks indefinitely.

    Raises:
        RedisError: If the connection to Redis fails.

    Returns:
        tuple: A (queue_name, job_payload_bytes) tuple or None if timeout.
    """

    try:
        # Blocking Right Pop: Waits for a job from the tail of the list
        return redis_client.brpop([config.REDIS_QUEUE_AWS], timeout=time_out)
    except ConnectionError as e:
        log.error(
            "Redis BRPOP failed. Connection may be down.",
            extra=_get_error_log_extra(e, "SYSTEM-QUEUE-READ")
        )
        raise RedisError("Redis connection error during BRPOP.") from e


def push_job_to_redis_queue(job_payload):
    """
    Pushes a failed job back to the *head* of the queue for immediate retry.

    Args:
        job_payload (dict): The job payload to re-queue.

    Raises:
        RedisError: If the connection to Redis fails.
    """

    correlation_id = job_payload.get('correlation_id', 'unknown')
    log_extra = {'context': 'SYSTEM-JOB-RETRY', 'correlation_id': correlation_id}
    try:
        redis_client.lpush(config.REDIS_QUEUE_AWS, json.dumps(job_payload))
        log.info("Job successfully re-queued for retry.", extra=log_extra)
    except ConnectionError as e:
        log.critical(
            "FATAL: Failed to re-queue job. Job may be lost.",
            exc_info=True, extra=log_extra
        )
        raise RedisError("Redis connection error during LPUSH.") from e