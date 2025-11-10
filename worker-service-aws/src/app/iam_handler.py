"""
# Core business logic component for the CSecBridge AWS Worker Service.

This module is responsible for:
1.  Securely assuming an IAM role in a target AWS account.
2.  Constructing the correct IAM Policy ARN based on job data.
3.  Connecting to the IAM service (using the Boto3 resource model).
4.  Executing the requested 'add' or 'remove' policy actions for a
    given principal (User or Role).
5.  Returning a status and AWS Request ID for auditing.
"""

import logging
import boto3
from .clients import aws_session as base_aws_session
from botocore.exceptions import ClientError as AWSClientError
from errors import AWSWorkerError, IAMError
from .helpers import get_error_log_extra

# Define what this module exposes to other parts of the application
__all__ = ["process_iam_action"]

# A constant, shared context for all logs originating from this module
_MODULE_LOG_CONTEXT = {
    "context": "AWS-WORKER-IAM"
}

# IAM Role Definitions
_IAM_TARGET_ROLE="cSecBridgeIAMHandlerRole"
_IAM_TARGET_ROLE_SESSION="cSecBridgeWorkerSession"

# Setup a module-level logger
log = logging.getLogger(__name__)


def _get_target_account_session(account_id, correlation_id):
    """
    Assumes a role in the target AWS account via STS.

    This function uses the worker's master credentials to request temporary,
    short-lived credentials for the target account. This is the core of the
    cross-account access pattern.

    Args:
        account_id (str): The 12-digit AWS account ID to assume a role in.
        correlation_id (str): The unique ID for logging and tracing.

    Raises:
        AWSWorkerError: If the STS AssumeRole call fails (e.g., trust policy
                        is misconfigured, or the role doesn't exist).

    Returns:
        boto3.Session: A new, temporary Boto3 session authenticated as the
                       target account's role.
    """

    log_extra = {
        **_MODULE_LOG_CONTEXT,
        "correlation_id": correlation_id,
        "account_id": account_id,
        "operation": "sts_assume_role",
        "iam_role": _IAM_TARGET_ROLE,
        "iam_role_session": _IAM_TARGET_ROLE_SESSION
    }
    log.debug(f"Attempting to assume role in target account", extra=log_extra)

    # This is the central STS client from the base AWS session.
    sts_client = base_aws_session.client('sts')
    
    # Pre-created role on each account - to be assumed for the IAM operation.
    role_to_assume = f"arn:aws:iam::{account_id}:role/{_IAM_TARGET_ROLE}"
    
    try:
        response = sts_client.assume_role(
            RoleArn=role_to_assume,
            RoleSessionName=_IAM_TARGET_ROLE_SESSION
        )
        
        temp_credentials = response['Credentials']
        
        # Create a new boto3 session using the temporary credentials.
        target_session = boto3.Session(
            aws_access_key_id=temp_credentials['AccessKeyId'],
            aws_secret_access_key=temp_credentials['SecretAccessKey'],
            aws_session_token=temp_credentials['SessionToken']
        )
        log.debug(
            "Successfully assumed role in target account.",
            extra=log_extra
        )
        return target_session

    # Critical configuration error. (non-transient)
    except AWSClientError as e:
        log.error(
            "Failed to assume role.",
            extra=get_error_log_extra(e, log_extra)
        )
        raise AWSWorkerError(
            "STS AssumeRole failed due to boto3 client error.",
            is_transient=False
        ) from e
    
    # Malformed response from boto3 invocation. (non-transient)
    except KeyError as e:
        log.error(
            'Failed to get temporary credentials.',
            extra=get_error_log_extra(e, log_extra)
        )
        raise AWSWorkerError(
            "STS failed to get temporary credentials.",
            is_transient=False
        ) from e
    
    # Unhandled boto3 errors for STS. (non-transient)
    except Exception as e:
        log.error(
            'Unhandled exception during STS AssumeRole operation.',
            extra=get_error_log_extra(e, log_extra)
        )
        raise AWSWorkerError(
            "Unhandled exception during STS AssumeRole operation.",
            is_transient=False
        ) from e

def _get_iam_policy_arn(account_id, policy_name, policy_type):
    """
    Constructs the correct, full IAM Policy ARN based on the policy type.

    Args:
        account_id (str): The target AWS account ID.
        policy_name (str): The name of the policy (e.g., "ReadOnlyAccess").
        policy_type (str): The type of policy ("default" for AWS-managed,
                           "custom" for customer-managed).

    Returns:
        str: The fully-formatted IAM Policy ARN.
    """

    if policy_type == 'default': # AWS managed policy
        return f"arn:aws:iam::aws:policy/{policy_name}"
    else: # Customer managed policy
        return f"arn:aws:iam::{account_id}:policy/{policy_name}"
    

def _get_iam_request_id(resp):
    """
    Extracts the AWS Request ID from a Boto3 response for auditing.

    Args:
        resp (dict): The dictionary response from a Boto3 client/resource call.

    Returns:
        str: The AWS Request ID, or "not-defined" if not found.
    """

    aws_response = resp.get(
        "ResponseMetadata",
        {"RequestId": "not-defined"}
    )
    aws_request_id = aws_response.get("RequestId", "not-defined")
    return aws_request_id


def process_iam_action(job_payload):
    """
    Executes the required IAM action based on the job payload.
    This is the main entry point for the business logic.

    Args:
        job_payload (dict): The complete job data from the Redis queue.

    Raises:
        AWSWorkerError: If the job payload is invalid, an IAM operation fails,
                        or an unexpected error occurs.

    Returns:
        dict: A dictionary containing the status and AWS request ID.
    """

    # Stage 1: Extract and validate the job payload.
    try:
        iam_actn = job_payload['action']
        iam_name = job_payload['principal']
        iam_type = job_payload['principal_type']
        iam_policy = job_payload['entitlement']
        iam_policy_type = job_payload['entitlement_type']
        account_id = job_payload['account_id']
        correlation_id = job_payload['correlation_id']

        # Create a log context for all subsequent logs
        log_extra = {
            **_MODULE_LOG_CONTEXT,
            "correlation_id": correlation_id,
            "account_id": account_id,
            "principal": iam_name,
            "action": iam_actn,
            "operation": "iam_handler"
        }
    except KeyError as e:
        raise AWSWorkerError(
            f"Job payload missing required field {e}",
            is_transient=False
        ) from e
    
    # Stage 2: Process the request
    try:
        # Get a temporary, secure session for the target account
        aws_target_session = _get_target_account_session(account_id,
                                                         correlation_id)
        iam_resource = aws_target_session.resource('iam')

        # Determine if the action is on a user or a role
        if iam_type == "User":
            iam_entity = iam_resource.User(iam_name)
        elif iam_type == "Role":
            iam_entity = iam_resource.Role(iam_name)
        else: # Neither a user nor a role
            raise IAMError(f"Unsupported IAM entity type {iam_type}.")
        
        log.debug("Processing IAM action.", extra=log_extra)

        # Construct the full Policy ARN to be attached/detached
        iam_policy_arn = _get_iam_policy_arn(
            account_id,
            iam_policy,
            iam_policy_type
        )

        # Execute the IAM action
        if iam_actn == "add":
            resp = iam_entity.attach_policy(PolicyArn=iam_policy_arn)
        elif iam_actn == "remove":
            resp = iam_entity.detach_policy(PolicyArn=iam_policy_arn)
        else: # Invalid action
            raise IAMError(f"Unsupported action: {iam_actn}.")

        log.debug("IAM action processed.", extra=log_extra)
        
        # Return a success dictionary with the AWS audit ID
        return {
            "status": "success",
            "aws_request_id": _get_iam_request_id(resp)
        }
    
    # Runtime errors during the internal module operations.
    except (IAMError, ValueError) as e:
        log.error(
            "IAM processing error",
            extra=get_error_log_extra(e, log_extra)
        )
        raise AWSWorkerError(str(e), is_transient=False) from e
    
    # AWS API Error during the IAM operation.
    except AWSClientError as e:

        # Get the specific Boto3/AWS API error
        error_code = e.response.get('Error', {}).get('Code')
        log.error("AWS API error", extra=get_error_log_extra(e, log_extra))
        
        # Distinguish between non-transient (retry not possible)
        # and transient (retry possible) failures for the job.
        if error_code in ['NoSuchEntity', 'InvalidInput', 'AccessDenied']:
            raise AWSWorkerError(
                f"Non-transient failure: {error_code}",
                is_transient=False
            ) from e
        else:
            raise AWSWorkerError(
                f"Transient AWS API failure: {error_code}",
                is_transient=True
            ) from e
    
    # All unhandled exceptions.
    except Exception as e:
        log.error(
            "Unexpected error during IAM operation",
            extra=get_error_log_extra(e, log_extra))
        log.error(f"Unexpected error during IAM operation: {e}", extra=log_extra)

        # Unhandled errors are non-transient, and should be evaluated 
        # manually in a separate error queue.
        raise AWSWorkerError(
            f"Unexpected handler error: {e}", is_transient=False
        ) from e
    