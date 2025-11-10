"""
# CSecBridge AWS Worker - Helper Utilities

This module provides common, reusable utility functions that are shared across
the application, such as logging formatters or data parsers.
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
        **context,
        "error_type": type(err).__name__,
        "error_message": str(err)
    }


def get_aws_request_id(boto3_response):
    """
    Extracts the AWS Request ID from a Boto3 response dictionary for auditing.

    Args:
        boto3_response (dict): The dictionary response from a Boto3 client call.

    Returns:
        str: The AWS Request ID, or "not-defined" if not found.
    """
    if not isinstance(boto3_response, dict):
        return "not-defined"

    response_metadata = boto3_response.get(
        "ResponseMetadata",
        {"RequestId": "not-defined"}
    )
    return response_metadata.get("RequestId", "not-defined")