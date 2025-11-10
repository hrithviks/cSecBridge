"""
# Custom Errors for the CSecBridge AWS Worker Service

This module defines all custom error class, to be used by AWS worker app.
"""

import logging

LOG = logging.getLogger(__name__)

class ConfigLoadError(Exception):
    """Custom exception for fatal configuration loading errors."""
    pass

class ExtensionInitError(Exception):
    """Raised when a required backend connection (DB/Redis/AWS) fails"""
    pass

class BackendServerError(Exception):
    """Base class for errors originating from downstream services."""
    pass

class BackendDataError(Exception):
    """Raised for errors specific to the backend data operations."""
    
    def __init__(self, message, is_transient=False):
        """
        Initializes the exception with a message and a transient flag.

        Args:
            message (str): The error message.
            is_transient (bool): Flag to indicate if the error is transient.
        """
        super().__init__(message)
        self.is_transient = is_transient

class DBError(BackendServerError):
    """Raised for specific errors related to database service operations"""
    pass

class RedisError(BackendServerError):
    """Raised for specific errors related to Redis operations."""
    pass

class AWSWorkerError(BackendServerError):
    """Raised for errors specific to the AWS API or business logic failures."""
    
    def __init__(self, message, is_transient=False):
        """
        Initializes the exception with a message and a transient flag.

        Args:
            message (str): The error message.
            is_transient (bool): Flag to indicate if the error is transient.
        """
        super().__init__(message)
        self.is_transient = is_transient

class IAMError(BackendServerError):
    """Raised for errors related to IAM action"""
    pass