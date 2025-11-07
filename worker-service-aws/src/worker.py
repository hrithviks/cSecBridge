"""
# CSecBridge AWS Worker Service - Main Entry Point

This script is the main entry point for the worker, designed to be run by
a WSGI server like Gunicorn.

Lifecycle:
1.  Sets up structured JSON logging (must be the first action).
2.  Imports and initializes the `app` package, which triggers the
    "fail-fast" initialization of all configs and backend clients.
3.  Defines the core `process_job` logic.
4.  Defines the `run_worker` infinite loop to consume jobs from Redis.
5.  Defines the `app` (WSGI) callable that Gunicorn executes.
"""

import logging
import time
import json
import sys

# Setup Logging Config
try:
    from logging_config import setup_logging
    setup_logging()
except ImportError:
    # Fallback to basic logging if config file is missing
    logging.basicConfig(level=logging.INFO)
    logging.warning("logging_config not found. Falling back to basic logging.")

# Setup logger for this entrypoint module
log = logging.getLogger(__name__)

# Import Dependencies
from redis.exceptions import ConnectionError as RedisErrorBase
from psycopg2 import OperationalError as DBErrorBase
from errors import ConfigLoadError

# Import Application Package
# This single import block initializes the entire 'app' package,
# including config, clients, and error classes.
try:
    from app import (
        config,
        redis_client,
        db_pool,
        aws_session,
        DBError,
        RedisError,
        AWSWorkerError,
        ExtensionInitError,
        process_iam_action,
        get_job_from_redis_queue,
        push_job_to_redis_queue,
        validate_job_status_on_db,
        update_job_status_on_db
    )
    # Import the logging helper from the new helpers module
    from app.helpers import get_error_log_extra
except (ExtensionInitError, ConfigLoadError, ImportError) as e:
    log.critical(
        "FATAL: Failed to initialize worker application package.",
        exc_info=True,
        extra={"context": "SYSTEM-STARTUP"}
    )
    sys.exit(1)  # Exit immediately if startup fails


def process_job(job_payload):
    """
    Manages the full lifecycle and state change for a single job.

    This function implements the core acceptance, retry, and failure logic
    for a job payload consumed from the queue.
    """

    try:
        correlation_id = job_payload["correlation_id"]
        log_extra = {
            "context": "SYSTEM-EXEC",
            "correlation_id": correlation_id
        }
    except KeyError as e:
        log.error(
            f"Malformed payload. Missing required field: {e}. Discarding.",
            extra=log_extra
        )
        return  # Malformed job, discard permanently.

    try:
        # Verify the job is in the DB and PENDING.
        if not validate_job_status_on_db(correlation_id, log_extra):
            return  # Job is unauthorized or a duplicate, discard.

        # Lock the job and set status to IN_PROGRESS.
        update_job_status_on_db(
            correlation_id,
            "IN_PROGRESS",
            "AWS Worker processing started."
        )
        log.info("Job locked and state set to IN_PROGRESS.", extra=log_extra)

        # Execute main IAM business logic for the job.
        result = process_iam_action(job_payload)
        aws_request_id = result.get("aws_request_id", "not-defined")

        # Handle post-processing.
        update_job_status_on_db(
            correlation_id,
            "SUCCESS",
            "AWS operation successful",
            aws_ref=aws_request_id
        )
        log.info("Job processed and committed successfully.", extra=log_extra)

    # Handle IAM execution failures
    except AWSWorkerError as e:
        err = str(e)
        if e.is_transient:

            # Re-queue for a transient error (e.g., AWS throttling)
            log.warning(
                f"Transient AWS error, re-queuing job",
                extra=get_error_log_extra(e, "SYSTEM-EXEC")
            )
            update_job_status_on_db(
                correlation_id,
                'PENDING',  # Revert status to PENDING
                f"Transient error, re-queuing job. Error: {err}"
            )
            push_job_to_redis_queue(job_payload)
        else:
            # Mark as FAILED for a permanent error (e.g., AccessDenied).
            log.error(
                f"Permanent business logic failure, job will not be retried",
                extra=log_extra
            )
            update_job_status_on_db(
                correlation_id,
                "FAILED",
                f"Non-transient error, discarding job. Error: {err}"
            )

    # Handle backend connection failures - always transient.
    except (DBError, RedisErrorBase) as e:
        log.error(
            f"Backend connection error, re-queuing job.",
            extra=get_error_log_extra(e, "SYSTEM-EXEC")
        )
        # Job is still 'IN_PROGRESS' in DB, so just re-queue.
        push_job_to_redis_queue(job_payload)

    # Handled unexpected errors - assuming transient.
    except Exception as e:
        log.error(
            f"Critical unhandled error, re-queuing job.",
            extra=get_error_log_extra(e, "SYSTEM-EXEC")
        )
        update_job_status_on_db(
            correlation_id,
            'PENDING',  # Revert status
            f"Unhandled exception, re-queuing."
        )
        push_job_to_redis_queue(job_payload)


def run_worker():
    """
    Main infinite loop for the worker process. Blocks waiting for jobs.
    """

    _startup_log_context = {"context": 'SYSTEM-STARTUP'}
    log.info("AWS Worker starting up...", extra=_startup_log_context)

    # Startup health check
    try:
        redis_client.ping()
        with db_pool.getconn() as conn:
            pass  # Test DB pool
        aws_session.client('sts').get_caller_identity()
        log.info(
            "All clients initialized and healthy. Entering queue loop.",
            extra=_startup_log_context
        )
    except (DBErrorBase, RedisErrorBase, Exception) as e:
        log.critical(
            "FATAL: Client health check failed. Exiting.",
            extra=get_error_log_extra(e, "SYSTEM-STARTUP"),
            exc_info=True
        )
        sys.exit(1)
    log.info("Startup health check completed.", extra=_startup_log_context)

    # Start worker process loop
    while True:
        try:
            # Get job payload from queue
            item = get_job_from_redis_queue(time_out=0)
            if item:
                _, payload_bytes = item
                job_payload = json.loads(payload_bytes.decode('utf-8'))

                log.info(
                    "Job received from queue.",
                    extra={
                        "context": "SYSTEM-EXEC",
                        "correlation_id": job_payload.get("correlation_id")
                    }
                )

                process_job(job_payload) # Process the job obtained from queue
        except RedisErrorBase as e:
            log.error(
                "Redis connection lost. Retrying in 10 seconds...",
                extra=get_error_log_extra(e, "SYSTEM-EXEC"),
            )
            time.sleep(10)
        except json.JSONDecodeError as e:
            log.error(
                "Failed to extract job payload. Job will be discarded",
                extra=get_error_log_extra(e, "SYSTEM-EXEC"),
            )
        except Exception as e:
            log.critical(
                "FATAL: Unhandled exception in main worker loop. Exiting.",
                extra=get_error_log_extra(e, "SYSTEM-EXEC"),
                exc_info=True
            )
            time.sleep(10)  # Avoid rapid crash-looping
            sys.exit(1)  # Terminate; Kubernetes will restart the pod.

def app(environ, start_response):
    """
    WSGI callable for Gunicorn to start the worker.
    
    Gunicorn runs this function, which in turn calls the
    infinite `run_worker()` loop.
    """

    try:
        run_worker()
    except Exception as e:
        # Final, ultimate catch-all
        log.critical(
            "FATAL: run_worker() loop exited unexpectedly.",
            extra=get_error_log_extra(e, "SYSTEM-EXEC"),
            exc_info=True
        )
        sys.exit(1)

    # This part should ideally not be reached, as run_worker() is an
    # infinite loop. It's here to satisfy the WSGI interface.
    start_response("200 OK", [('Content-Type', 'text/plain')])
    return [b"Worker process has completed."]
