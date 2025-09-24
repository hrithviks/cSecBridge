"""
Defines custom exceptions and registers application error handlers.

This module centralizes error handling for the application. It contains:
1.  Definitions for custom, application-specific exceptions.
2.  A registration function for unified HTTP error handling.
"""
from flask import jsonify, current_app, request
from werkzeug.exceptions import HTTPException
from jsonschema import ValidationError

# Custom exception classes for the package

# Custom exception class for the extention
class ExtentionError(Exception):
    """Custom error class for extensions."""
    pass

# Custom error classes for backend
class BackendServerError(Exception):
    """Custom error class for backend errors."""
    pass

class DBError(BackendServerError):
    """Custom error class for database operations."""
    pass

class RedisError(BackendServerError):
    """Custom error class for Redis operations."""
    pass

# Internal system error class for the routes module
class APIServerError(Exception):
    """Custom error class for API server."""
    pass

# HTTP error handler for Flask App
def _handle_http_exception(e):
    """A generic handler for all Werkzeug HTTPException instances."""

    response = {
        "error": e.name,
        "details": e.description,
    }
    current_app.logger.info(f"HTTP Exception caught: {e.code} {e.name} - {request.path}")
    return jsonify(response), e.code

# API server error handler for Flask App
def _handle_api_server_exception(e):
    """Handler for all internal API server errors."""

    # Client will receive a generic internal server error
    response = {
        "error": "Internal Server Error. Please try again."
    }
    current_app.logger.error(f"APIServer Exception caught.")
    return jsonify(response), 503

# JSON Schema validation error handler
def _handle_json_schema_error(e):
    """Handler for JSON Schema validation errors."""

    response = {
        "error": "JSON Data Error",
        "details": str(e),
    }
    current_app.logger.error(f"JSON Schema Validation Exception caught.")
    return jsonify(response), 400

# All unhandled exceptions within the app
def _handle_all_exceptions(e):
    """Handler for all unhandled exceptions."""

    response = {
        "error": "Internal Server Error",
        "details": "An unexpected error occurred. Please try again."
    }
    current_app.logger.error(f"Unhandled Exception caught: {e}", exc_info=True)
    return jsonify(response), 500

# Register all error handlers
def register_error_handlers(app):
    """Registers all necessary error handlers for the Flask app instance."""

    app.register_error_handler(ValidationError, _handle_json_schema_error)
    app.register_error_handler(HTTPException, _handle_http_exception)
    app.register_error_handler(APIServerError, _handle_api_server_exception)
    app.register_error_handler(Exception, _handle_all_exceptions)

