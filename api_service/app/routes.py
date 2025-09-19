'''
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
'''

from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, request, jsonify, g, current_app
from jsonschema import validate, ValidationError
import psycopg2
import redis
import uuid
import json

# Import the backend module to access data logic functions
from .backend import create_new_request, get_request_by_id
from .extensions import limiter, redis_client, db_pool

# Define the public API of this module. Only the blueprint should be exposed.
__all__ = ['api_blueprint']

# Internal error class for the module
class APIServerError(Exception):
    pass

# Load schema file for payload validation
try:
    with open('schema.json', 'r') as f:
        _ACCESS_REQUEST_SCHEMA = f.read()
except FileNotFoundError as e:
    raise APIServerError(f'Could not load schema.json: {e}') from e

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

def _get_backend_data(data):
    """Internal function to generate the data for backend processing."""
    
    return {
        "request_id": data['request_id'],
        "correlation_id": str(uuid.uuid4()),
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
        "client_request_id": data["request_id"],
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

@api_blueprint.route('/api/v1/requests', methods=['POST'])
@_token_required
@limiter.limit("100 per minute")
def create_request():
    """API POST Method - Accepts, validates, and queues a new access request. """

    # Load and parse the payload
    try:
        data = request.get_json(silent=True)
        if not data:
            return _build_error_response(400, 'Data error')
        validate(instance=data, schema=json.loads(_ACCESS_REQUEST_SCHEMA))
    except (ValidationError, json.JSONDecodeError) as e:
        return _build_error_response(400, 'Data error', 'JSON schema validation failed')
    
    # Create the payload for backend processing
    backend_data = _get_backend_data(data)

    try:
        db_conn = _get_db_connection()
        redis_conn = _get_redis_connection()

        # Call the backend function to log the request.
        create_new_request(db_conn, redis_conn, backend_data)
        db_conn.commit()
    except (psycopg2.Error, redis.exceptions.RedisError) as e:
        if 'redis_conn' in locals() and db_conn:
            db_conn.rollback()
        current_app.logger.error(f'Service communication failed: {e}',
                                 exc_info=True)
        raise APIServerError(f'Backend service communication failed. Error details: {str(e)}')
    
    return _build_api_response(202, _get_response_data(backend_data))

@api_blueprint.route('/api/v1/requests/<string:correlation_id>', methods=['GET'])
@_token_required
@limiter.limit("200 per minute")
def get_request_status(correlation_id):
    """API Get Method - Retrieves the status of a specific access request."""

    try:
        conn = _get_db_connection()
        redis_conn = _get_redis_connection()

        # Call the backend function to get the data
        request_status = get_request_by_id(conn,
                                           redis_conn,
                                           correlation_id)
    except (psycopg2.Error, redis.exceptions.RedisError) as e:
        current_app.logger.error(f'Service communication failed for '
                                 f'{correlation_id}: {e}', exc_info=True)
        raise APIServerError(f'Backend service communication failed for '
                             f'{correlation_id}. Error details: {str(e)}')
    
    if not request_status:
        return _build_error_response(404, 'Data error', f'Request not found for correlation id {correlation_id}')

    # Send the status of the request
    return _build_api_response(200, request_status)