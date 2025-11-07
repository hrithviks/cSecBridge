# **AWS Worker Service (worker-service-aws)**

This service is a dedicated, asynchronous background worker responsible for processing all CSecBridge requests for the **AWS** target platform.

## **Core Responsibilities**

1. **Consume Jobs:** Continuously polls the queue:aws list in Redis using a blocking pop (BRPOP).  
2. **Validate Job:** Upon receiving a job, it first checks the PostgreSQL database to ensure the correlation\_id exists and its status is PENDING. This prevents processing duplicate or unauthorized jobs.  
3. **Lock Job:** Atomically updates the job's status in the database from PENDING to IN\_PROGRESS.  
4. Execute Business Logic: Performs the core IAM operation by:  
   a. Using its master credentials to assume a role (cSecBridgeIAMHandlerRole) in the target AWS account via STS.  
   b. Using the temporary session to create an IAM client.  
   c. Attaching or detaching the specified IAM policy from the target principal (User or Role).  
5. **Update Status:**  
   * **On Success:** Updates the job status to SUCCESS in the database and records the AWS Request ID in the csb\_requests\_ref table for auditing.  
   * **On Failure:** Distinguishes between:  
     * **Transient Failures** (e.g., AWS throttling, network timeout): Reverts the status to PENDING and pushes the job back to the *head* of the queue (LPUSH) for immediate retry.  
     * **Permanent Failures** (e.g., AccessDenied, NoSuchEntity): Updates the job status to FAILED and records the error. The job is *not* retried.

## **Project Structure (src/)**

* **worker.py**: The main WSGI entry point for Gunicorn.  
  * Initializes the app package (which triggers config.py and clients.py).  
  * run\_worker(): The main infinite loop that calls get\_job\_from\_redis\_queue.  
  * process\_job(): The core job lifecycle logic (validate, lock, execute, update/retry).  
* **logging\_config.py**: Configures structured (JSON) logging.  
* **errors.py**: Defines custom exception classes (ConfigLoadError, ExtensionInitError, DBError, RedisError, AWSWorkerError, IAMError).  
* **app/\_\_init\_\_.py**: The application package initializer. It imports and exposes all core components (config, clients, errors, and logic functions) as a single package.  
* **app/config.py**: Loads and validates all worker-specific environment variables (AWS credentials, DB/Redis connection strings, queue name) with a fail-fast approach.  
* **app/clients.py**: Initializes and exports the singleton clients used by the worker:  
  * redis\_client: A thread-safe Redis client.  
  * db\_pool: A psycopg2 threaded connection pool for PostgreSQL.  
  * aws\_session: A boto3.Session created using the worker's master credentials.  
* **app/backend.py**: The Data Access Layer (DAL) for the worker.  
  * get\_job\_from\_redis\_queue(): Wraps the BRPOP command.  
  * push\_job\_to\_redis\_queue(): Wraps the LPUSH command for retries.  
  * validate\_job\_status\_on\_db(): Checks if a job is PENDING.  
  * update\_job\_status\_on\_db(): A transactional function that updates the csb\_requests table and inserts into csb\_requests\_audit (and csb\_requests\_ref on success).  
* **app/iam\_handler.py**: The core business logic module.  
  * process\_iam\_action(): The main function called by worker.py. It orchestrates the entire AWS operation.  
  * \_get\_target\_account\_session(): Handles the sts:AssumeRole call to get temporary credentials for the target account.  
* **app/helpers.py**: Utility functions, such as get\_error\_log\_extra for standardizing log metadata.

## **Containerization (Dockerfile)**

The Dockerfile uses a multi-stage build:

1. **builder stage**: Installs Python dependencies (requirements.txt) into a wheels directory.  
2. **Final stage**: Copies the pre-built wheels and the src/ directory into a clean Python image. It creates a non-root user (csbuser) and runs the application via Gunicorn.