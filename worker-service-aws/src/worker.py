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

# A constant, shared context for all logs originating from this module
_LOG_CONTEXT = {
    "context": "AWS-WORKER-MAIN"
}

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
        BackendDataError,
        process_iam_action,
        get_job_from_redis_queue,
        push_job_to_redis_queue,
        validate_job_status_on_db,
        update_job_status_on_db
    )
    # Import the logging helper from the new helpers module
    from app.helpers import get_error_log_extra
except Exception as e:
    log.critical(
        "FATAL: Failed to initialize worker application package",
        exc_info=True,
        extra={
            **_LOG_CONTEXT,
            "operation": "worker_init",
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
    )
    sys.exit(1)  # Exit immediately if startup fails


# Set main and error queues
JOB_QUEUE = config.REDIS_QUEUE_AWS
JOB_ERROR_QUEUE = f"queue:aws_error"


def process_job(job_payload):
    """
    Manages the full lifecycle and state change for a single job.

    This function implements the core acceptance, retry, and failure logic
    for a job payload consumed from the queue.
    """

    try:
        correlation_id = job_payload["correlation_id"]
        log_extra = {
            **_LOG_CONTEXT,
            "operation": "payload_proc",
            "correlation_id": correlation_id
        }
    except KeyError as e:
        log.error(
            f"Correlation ID missing in job payload.",
            extra=log_extra
        )
        return  # Malformed job, discard permanently.

    try:
        # Step 1: Verify the job is in the DB and "queued".
        if not validate_job_status_on_db(correlation_id):
            log.warning('Duplicate or invalid job. Discarding.')
            return  # Job is unauthorized or a duplicate, discard.

        # Step 2: Lock the job by setting backend status to "in_progress"
        log.debug('Locking the job.', extra=log_extra)
        update_job_status_on_db(
            correlation_id,
            "in_progress",
            "AWS worker processing started."
        )
        log.debug("Job locked and state set to in_progress.", extra=log_extra)

        # Execute main IAM business logic for the job.
        result = process_iam_action(job_payload)
        aws_request_id = result.get("aws_request_id", "not-defined")

        # Handle post-processing.
        update_job_status_on_db(
            correlation_id,
            "success",
            "AWS IAM operation successful.",
            aws_ref=aws_request_id
        )
        log.debug("Job processed and committed successfully.", extra=log_extra)

    # Handle IAM execution failures
    except AWSWorkerError as e:
        err = str(e)
        if e.is_transient:

            # Re-queue for a transient error (e.g., AWS throttling)
            log.warning(
                f"Transient AWS error, re-queuing job",
                extra=get_error_log_extra(e, log_extra)
            )
            update_job_status_on_db(
                correlation_id,
                'queued',  # Revert status to PENDING
                f"Transient error, re-queuing job. Error: {err}"
            )
            push_job_to_redis_queue(JOB_QUEUE, job_payload)
        else:
            # Mark as FAILED for a permanent error (e.g., AccessDenied).
            log.error(
                f"Permanent business logic failure, job will not be retried",
                extra=get_error_log_extra(e, log_extra)
            )
            update_job_status_on_db(
                correlation_id,
                "failed",
                f"Non-transient error, discarding job."
            )
    
    # Handle backend data errors during querying - always non-transient.
    except BackendDataError as e:
        log.error(
            f"Backend database query error. Moving job to error queue.",
            extra=get_error_log_extra(e, log_extra)
        )
        push_job_to_redis_queue(JOB_ERROR_QUEUE, job_payload)

    # Handle backend connection failures - always transient.
    except (DBError, RedisErrorBase) as e:
        log.error(
            f"Backend connection error, re-queuing job.",
            extra=get_error_log_extra(e, log_extra)
        )
        # Job is still 'in_progress' state in DB, so just re-queue.
        # Additional option for re-queue to insert a retry count on payload,
        # and stop processing after fixed attempts to process.
        push_job_to_redis_queue(JOB_QUEUE, job_payload)

    # Handled unexpected errors - move to error queue.
    except Exception as e:
        log.error(
            f"Critical unhandled error, moving to error queue.",
            extra=get_error_log_extra(e, log_extra),
            exc_info=True
        )
        update_job_status_on_db(
            correlation_id,
            "failed",  # Set to failed
            f"Unhandled exception, Job moved to error queue"
        )
        push_job_to_redis_queue(JOB_ERROR_QUEUE, job_payload)


def run_worker():
    """
    Main infinite loop for the worker process. Blocks waiting for jobs.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "operation": "worker_startup"
    }

    log.debug("AWS Worker starting up...", extra=log_extra)

    # Startup health check
    try:
        redis_client.ping()
        with db_pool.getconn() as conn:
            pass  # Test DB pool
        aws_session.client('sts').get_caller_identity()
        log.debug(
            "All clients initialized and healthy. Entering queue loop.",
            extra=log_extra
        )
    except (DBErrorBase, RedisErrorBase, Exception) as e:
        log.critical(
            "FATAL: Client health check failed. Exiting.",
            extra=get_error_log_extra(e, log_extra),
            exc_info=True
        )
        sys.exit(1)
    log.debug("Startup health check completed.", extra=log_extra)

    # Start worker process loop
    while True:
        log.debug("Worker ready to accept jobs", extra=log_extra)
        log_extra = {
            **_LOG_CONTEXT,
            "operation": "worker_loop"
        }
        redis_data = None

        try:
            # Get job payload from queue
            item = get_job_from_redis_queue(JOB_QUEUE, time_out=0)
            if item:
                _, redis_data = item
                job_payload = json.loads(redis_data)

                log.debug(
                    "Job received from queue.",
                    extra={
                        **log_extra,
                        "correlation_id": job_payload.get("correlation_id")
                    }
                )

                process_job(job_payload) # Process the job obtained from queue
        except RedisErrorBase as e:
            log.error(
                "Redis connection lost. Retrying in 10 seconds...",
                extra=get_error_log_extra(e, log_extra),
            )
            time.sleep(10)
        except json.JSONDecodeError as e:
            log.error(
                "Failed to extract job payload. Moving to error queue.",
                extra=get_error_log_extra(e, log_extra),
            )
            push_job_to_redis_queue(JOB_ERROR_QUEUE, redis_data)
        except Exception as e:
            log.critical(
                "FATAL: Unhandled exception in main worker loop. Exiting.",
                extra=get_error_log_extra(e, log_extra),
                exc_info=True
            )

            # If processing of an item was already in progress
            if redis_data:
                push_job_to_redis_queue(JOB_ERROR_QUEUE, redis_data)
            
            # Terminate the worker
            time.sleep(10)  # Avoid rapid crash-looping
            sys.exit(1)  # Terminate; Kubernetes will restart the pod.

def app(environ, start_response):
    """
    WSGI callable for Gunicorn to start the worker.
    
    Gunicorn runs this function, which in turn calls the
    infinite `run_worker()` loop.
    """

    log_extra = {
        **_LOG_CONTEXT,
        "operation": "gunicorn_init"
    }
    try:
        log.debug(
            "Starting worker process.",
            extra=log_extra
        )
        run_worker()
    except Exception as e:
        # Final, ultimate catch-all
        log.critical(
            "FATAL: Worker process error",
            extra=log_extra,
            exc_info=True
        )
        sys.exit(1)

    # This part should ideally not be reached, as run_worker() is an
    # infinite loop. It's here to satisfy the WSGI interface.
    start_response("200 OK", [('Content-Type', 'text/plain')])
    return [b"Worker process has completed."]


if __name__ == '__main__':
    """
    Local testing of AWS worker service
    """

    log.warning(
        'Initializing in test mode. This is for local testing only.',
        extra={**_LOG_CONTEXT, "operation": "local_testing"}
    )
    try:
        run_worker()
    except KeyboardInterrupt:
        log.warning('Exiting Test...')
    exit(0)