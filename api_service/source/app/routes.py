"""
# Defines the API routes for the CSecBridge API Service.

This module uses a Flask Blueprint (`api_blueprint`) to organize all API endpoints.
It acts as the primary interface for the application, responsible for:
- Handling HTTP request/response logic.
- Validating incoming data payloads.
- Enforcing authentication and rate limiting.
- Calling the data access layer (`backend.py`) to perform business logic.
- Formatting data returned from the backend into JSON responses.

API will provide data related response only.
Custom error class will return internal errors during the excecution back to
application factory.
"""

import uuid
import json
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, jsonify, g, current_app
from jsonschema import validate, ValidationError
from app.errors import APIServerError, DBError, RedisError

# Import the backend module to access data logic functions
from .backend import create_new_request, get_request_by_id
from .extensions import limiter, redis_client, db_pool

# Set context for logging
_SYSTEM_CONTEXT = {"context": "SYSTEM-API"}
_CLIENT_CONTEXT = {"context": "CLIENT-API"}

# Define the public API of this module. Only the blueprint should be exposed.
__all__ = ['api_blueprint']
api_blueprint = Blueprint('api', __name__)

def _build_error_response(status_code, error_message, trace_back=None):
    """Internal function to generate an error response to client."""

    error_response = jsonify({"error": error_message, "trace_back": trace_back})
    return error_response, status_code

def _build_api_response(status_code, data):
    """Internal message to generate api response to client."""
    
    return jsonify(data), status_code

def _get_db_connection():
    """Gets a connection from the PostgreSQL pool for the current request."""
    if 'db' not in g:
        g.db = db_pool.getconn()
    return g.db

def _get_redis_connection():
    """Returns the singleton Redis client instance."""

    return redis_client

def _get_backend_data(data, correlation_id):
    """Internal function to generate the data for backend processing."""
    
    return {
        "client_request_id": data['client_request_id'],
        "correlation_id": correlation_id,
        "account_id": data['account_id'],
        "target_cloud": data['target_cloud'],
        "status": "PENDING",
        "received_at": datetime.now(timezone.utc).isoformat(),
        **data['context']
    }

def _get_response_data(data):
    """Internal function to generate the response data."""
    
    return {
        "status": "Request accepted",
        "client_request_id": data["client_request_id"],
        "correlation_id": data["correlation_id"],
        "received_at": data["received_at"]
    }

def _token_required(func):
    """Decorator function to wrap API functions to enforce token validation."""

    @wraps(func)
    def decorated(*args, **kwargs):
        """Wrapper function that performs the token check."""

        token = request.headers.get('X-Auth-Token')
        if not token or token != current_app.config['API_AUTH_TOKEN']:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return decorated

######################
# Health Check Probe #
######################
@api_blueprint.route('/health', methods=['GET'])
def health_check_probe():
    """Health Check Probe - Used by Kubernetes for liveness probe."""

    current_app.logger.debug('Health check probe received.', 
                             extra=_SYSTEM_CONTEXT)
    return _build_api_response(200, {"status": "ok"})

#######################
# App Readiness Probe #
#######################
@api_blueprint.route('/ready', methods=['GET'])
def app_readiness_probe():
    """Readiness probe - Used by Kubernetes to check if app is ready to accept traffic."""

    current_app.logger.info('App readiness probe received.', 
                             extra=_SYSTEM_CONTEXT)
    try:
        # Check database connectivity by getting a connection from the pool
        db_conn = _get_db_connection()
        if not db_conn:
            current_app.logger.error('Failed to obtain database connection from pool. \
                                     App is not ready to serve requests.', 
                                     extra=_SYSTEM_CONTEXT, 
                                     exc_info=False)
            raise Exception("Failed to get DB connection from pool.")

        # Check Redis connectivity by sending a PING command
        redis_conn = _get_redis_connection()
        redis_conn.ping()
        current_app.logger.info('App readiness confirmed.', 
                                 extra=_SYSTEM_CONTEXT)
        return _build_api_response(200, {"status": "ready"})

    # Catch all exceptions
    except Exception as e:
        # Log the specific error details for debugging
        current_app.logger.error(f"Readiness probe failed: {e.__qualname__}", exc_info=False)
        current_app.logger.error(f"Exception details: {str(e)}", exc_info=False)
        
        # Return a 503 error to signal Kubernetes that the pod is not ready
        return _build_error_response(400, 'Service Error', f'A backend service is currently unavailable. Error details: {str(e)}')

########################
# Requests POST Method #
########################
@api_blueprint.route('/api/v1/requests', methods=['POST'])
@_token_required
@limiter.limit("100 per minute")
def create_request():
    """API POST Method - Accepts, validates, and queues a new access request. """

    # Create a unique corelation id and set it to the logger context
    correlation_id = str(uuid.uuid4())
    client_context = {**_CLIENT_CONTEXT, **{'correlation_id': correlation_id}}
    server_context = {**_SYSTEM_CONTEXT, **{'correlation_id': correlation_id}}
    current_app.logger.info(f'API Request received. Path: {request.path}. Method: {request.method}.', 
                            extra=client_context)

    # Load and parse the payload
    data = request.get_json(silent=True)
    if not data:
        current_app.logger.info(f'Invalid JSON data in the request.', 
                                extra=client_context)
        raise ValidationError('Invalid JSON data')
    try:
        validate(instance=data, schema=current_app.config['JSON_REQ_SCHEMA'])
    except ValidationError as e:
        current_app.logger.info(f'Json schema validation failed. Error: {e}', 
                                extra=client_context)
        raise
    
    # Create the payload for backend processing
    backend_data = _get_backend_data(data, correlation_id)

    try:
        current_app.logger.info(f'Getting database connection from the pool.', 
                                extra=client_context)
        db_conn = _get_db_connection()
        redis_conn = _get_redis_connection()

        # Call the backend function to log the request.
        current_app.logger.info(f'Initiating backend data processing.', 
                                extra=client_context)
        create_new_request(db_conn, redis_conn, backend_data)
        db_conn.commit()
        current_app.logger.info(f'Backend data processing successful.', 
                                extra=client_context)
    except (DBError, RedisError) as e:
        current_app.logger.error(f'Service communication error: {e}',
                                 extra = server_context,
                                 exc_info=True)
        if 'redis_conn' in locals() and db_conn:
            db_conn.rollback()
            current_app.logger.warning(f'Rollback executed for the request.',
                                        extra = server_context,
                                        exc_info=True)
        raise APIServerError(f'Backend service communication failed. Error details: {str(e)}')
    
    return _build_api_response(202, _get_response_data(backend_data))

#######################
# Requests GET Method #
#######################
@api_blueprint.route('/api/v1/requests/<string:correlation_id>', methods=['GET'])
@_token_required
@limiter.limit("200 per minute")
def get_request_status(correlation_id):
    """API Get Method - Retrieves the status of a specific access request."""
    client_context = {**_CLIENT_CONTEXT, **{'correlation_id': correlation_id}}
    server_context = {**_SYSTEM_CONTEXT, **{'correlation_id': correlation_id}}
    current_app.logger.info(f'API Request received. Path: {request.path}. Method: {request.method}.', 
                            extra=client_context)

    try:
        current_app.logger.info(f'Getting database connection from the pool.', 
                                extra=client_context)
        conn = _get_db_connection()
        redis_conn = _get_redis_connection()
        current_app.logger.info(f'Initiating backend data querying.', 
                                extra=client_context)

        # Call the backend function to get the data
        request_status = get_request_by_id(conn,
                                           redis_conn,
                                           correlation_id)
        current_app.logger.info(f'Backend data querying successful.', 
                                extra=client_context)
    except (DBError, RedisError) as e:
        current_app.logger.warning(f'Service communication error: {e}',
                                 extra = server_context,
                                 exc_info=True)
        raise APIServerError(f'Backend service communication failed for '
                             f'{correlation_id}. Error details: {str(e)}')
    
    if not request_status:
        return _build_error_response(404, 'Data error', f'Request not found for correlation id {correlation_id}')

    # Send the status of the request
    return _build_api_response(200, request_status)