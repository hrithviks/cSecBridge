# **API Service (api-service)**

The API Service is the primary, public-facing entry point for the CSecBridge application. It is a stateless Flask/Gunicorn application responsible for validating, authenticating, and queueing all incoming access requests.

## **Core Responsibilities**

1. **Authentication:** Validates incoming requests via a shared secret token (X-Auth-Token).  
2. **Validation:** Enforces a strict JSON schema (schema.json) on all request payloads.  
3. **Rate Limiting:** Applies endpoint-level rate limiting using Flask-Limiter with a Redis backend.  
4. **Persistence:** Creates an initial record for the request in the PostgreSQL database with a PENDING status.  
5. **Queueing:** Pushes the validated job payload into the appropriate Redis list (e.g., queue:aws) for asynchronous processing by a worker service.  
6. **Status Check:** Provides an endpoint to check the status of a request, utilizing a cache-aside pattern with Redis for fast responses.

## **Project Structure (src/)**

* **run.py**: The main WSGI entry point for Gunicorn. It initializes the configuration (config.py) and then calls the application factory (create\_app) to create the Flask app.  
* **logging\_config.py**: Configures structured (JSON) logging for the entire application.  
* **config.py**: Loads and validates all configuration from environment variables (e.g., database passwords, Redis host). It follows a fail-fast approach, raising a ConfigLoadError if any required variable is missing or malformed.  
* **app/\_\_init\_\_.py**: Contains the create\_app() application factory. This function assembles the Flask app, initializes extensions (CORS, Talisman, Limiter), registers blueprints, and sets up error handlers.  
* **app/extensions.py**: Initializes and configures all third-party Flask extensions (Limiter, Talisman, CORS) and creates the singleton clients for db\_pool (PostgreSQL) and redis\_client.  
* **app/routes.py**: Defines all API endpoints using a Flask Blueprint.  
  * POST /api/v1/requests: The main endpoint for submitting a new access request.  
  * GET /api/v1/requests/\<correlation\_id\>: The endpoint for checking the status of a request.  
  * /health: A simple liveness probe.  
  * /ready: A readiness probe that actively checks connections to the database and Redis.  
* **app/backend.py**: The Data Access Layer (DAL). This module contains all business logic for interacting with the database and Redis. It is called by routes.py.  
  * create\_new\_request(): Atomically inserts the request into the csb\_requests table, adds an audit log, and pushes the job to the Redis queue.  
  * get\_request\_by\_id(): Implements the cache-aside logic to fetch request status.  
* **app/errors.py**: Defines custom exception classes (DBError, RedisError, APIServerError) and registers all global error handlers to ensure standardized JSON error responses.

## **Database Schema (sql/)**

* **backend.sql**: This script (intended to be run by an administrator after init.sql) creates the application-specific tables:  
  * csb\_requests: The primary table for storing the state of all requests.  
  * csb\_requests\_audit: An append-only log of all status changes for every request.  
  * csb\_requests\_ref: Stores external reference IDs from cloud providers (e.g., AWS Request ID) for auditing.  
  * It also defines permissions and Row-Level Security (RLS) policies to restrict worker access (e.g., AWS worker can only see cloud\_provider \= 'aws' rows).

## **Containerization (Dockerfile)**

The Dockerfile uses a multi-stage build:

1. **builder stage**: Installs Python dependencies into a wheels directory.  
2. **Final stage**: Copies the pre-built wheels and the application source code into a clean Python image. It creates a non-root user (csbuser) and runs the application via Gunicorn.

## **Deployment (helm/)**

This service is deployed to Kubernetes using its own [Helm chart](https://www.google.com/search?q=./helm/README.md). The chart manages the Deployment, Service, ConfigMap, NetworkPolicy, and HPA resources.