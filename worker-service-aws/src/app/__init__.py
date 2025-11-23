"""
# CSecBridge AWS Worker Package

It initializes and exposes the core components of the package
1. Custom error classes
2. The 'config' singleton
3. The backend client singletons ('redis_client', 'db_pool', 'aws_session')
4. The core business logic functions
"""

import logging

# A constant, shared context for all logs originating from this module
_LOG_CONTEXT = {
    "context": "AWS-WORKER-APP-INIT"
}

# Setup a package-level logger
log = logging.getLogger(__name__)
log.debug('Initializing AWS worker application.',
          extra=_LOG_CONTEXT)

# Expose all public error classes
from errors import (
    ConfigLoadError,
    ExtensionInitError,
    BackendServerError,
    DBError,
    RedisError,
    AWSWorkerError,
    IAMError,
    BackendDataError
)

# Initialize and expose the config singleton
try:
    from .helpers import get_error_log_extra
    from .config import config
except ConfigLoadError as e:
    log.error(
        'Error loading application configuration.',
        extra=get_error_log_extra(e, _LOG_CONTEXT)
    )
    raise

# Initialize and expose the client singletons
try:
    from .clients import (
        redis_client,
        db_pool,
        aws_session
    )
except ExtensionInitError as e:
    log.critical(
        'Error initializing backend clients.',
        extra=get_error_log_extra(e, _LOG_CONTEXT)
    )
    raise

# Expose the main business logic functions and helpers
from .iam_handler import process_iam_action
from .backend import (
    get_job_from_redis_queue,
    push_job_to_redis_queue,
    validate_job_status_on_db,
    update_job_status_on_db
)

# Define the public APIs for the package
__all__ = [
    # Singletons
    "config",
    "redis_client",
    "db_pool",
    "aws_session",

    # Business Logic
    "process_iam_action",
    "get_job_from_redis_queue",
    "push_job_to_redis_queue",
    "validate_job_status_on_db",
    "update_job_status_on_db",

    # Errors
    "ConfigLoadError",
    "ExtensionInitError",
    "BackendServerError",
    "DBError",
    "RedisError",
    "AWSWorkerError",
    "IAMError",
    "BackendDataError",

    # Helpers
    "get_error_log_extra"
]

log.debug('Application package initialized.',
          extra=_LOG_CONTEXT)