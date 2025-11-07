"""
# Centralized logging configuration for the CSecBridge API Service.

This module provides a setup function to configure the application's logger to
output records in a structured JSON format. This is crucial for production
environments where logs are ingested and parsed by an observability stack.

Using a unified formatter ensures that logs from application startup, request
handling, and error reporting all share a consistent, machine-readable schema.

Methods:
    setup_logging: Configures the root logger to output structured JSON logs.

"""

import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging():
    """
    Configures the root logger to output structured JSON logs to stderr.
    """
    logger = logging.getLogger()
    # Prevent duplicate logs if already configured
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)

    # Define the format of the JSON logs
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Redirect standard library warnings to the logger
    logging.captureWarnings(True)
