'''
# Application factory for the CSecBridge API Service.

This module contains the application factory function, `create_app`, which is
the central entry point for assembling the Flask application. Using a factory
pattern allows for easier testing and management of application instances.

The `create_app` function is responsible for:
1.  Creating the core Flask application instance.
2.  Loading configuration from the `config` object.
3.  Initializing Flask extensions, such as the rate limiter and security
    features (CORS, Talisman), by binding them to the application instance.
4.  Registering all API route blueprints to make the endpoints available.
5.  Setting up a global error handler to catch any unhandled exceptions during
    request processing, ensuring the service remains stable.
6.  Registering a teardown function to safely return database connections to
    the pool after each request, preventing connection leaks.

Functions:
    create_app: Creates and returns a configured Flask application instance.
'''

from flask import Flask, g, jsonify
from config import config
from .extensions import limiter, db_pool, talisman, cors
from .backend import BackendServerError
from .routes import APIServerError


def create_app():
    """Create and configure instance of the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config)

    # Initialize extensions with the app instance
    limiter.init_app(app)

    # Initialize security extensions
    talisman.init_app(app, force_https=False)
    cors.init_app(app,
                  resources={r'/api/*': {"origins": config.ALLOWED_ORIGIN}})

    # Register blueprints
    from . import routes
    app.register_blueprint(routes.api_bp)

    # Global error handler for the routes
    @app.errorhandler(APIServerError, BackendServerError, Exception)
    def handle_unexpected_error(e):
        '''
        Catches all internal errors during the request processing, and logs to
        the application's logger.

        This abstracts the underlying operation from the client, and propagates
        a uniform internal server error.
        '''

        # Log the exception to stderr
        app.logger.error(f"Internal Exception: {e}", exc_info=True)

        # Return a generic, safe error response to the client
        return jsonify({
            "error": "Internal Server Error",
            "details": "An unexpected error occurred. Please try again."
        }), 500

    # Register teardown function to return DB connection to the pool
    @app.teardown_appcontext
    def close_db_connection(exception=None):
        '''
        Returns the database connection to the pool after each request.
        This is a teardown function that Flask calls automatically.
        '''

        db = g.pop('db', None)
        if db is not None:
            db_pool.putconn(db)

    return app
