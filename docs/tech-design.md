# **CSecBridge \- Technical Design & Architecture**

## **1\. Overview**

This design outlines a decoupled, microservice-based architecture. Each component is a distinct, containerized service that communicates over a network, primarily via a message queue (Redis) and a shared state database (PostgreSQL). The entire system is designed to be deployed and orchestrated via Kubernetes.

## **2\. Core Components**

### **2.1. API Service (api-service)**

The API service is the primary, public-facing entry point, designed as a stateless bridge for all incoming requests.

* **Technology:** Flask, Gunicorn  
* **Core Responsibilities:**  
  * **Authentication & Authorization:** Validates a mandatory X-Auth-Token on all API endpoints.  
  * **Rate Limiting:** Utilizes Flask-Limiter with a Redis backend to protect against abuse.  
  * **Schema Validation:** Enforces a strict JSON schema (schema.json) on all POST request payloads.  
  * **Health Probes:**  
    * /health: Liveness probe.  
    * /ready: Readiness probe that actively checks connectivity to both PostgreSQL and Redis.  
* **Endpoints:**  
  * **POST /api/v1/requests**  
    1. Auth, validate, and rate-limit the request.  
    2. Generate a unique correlation\_id (UUID) for the transaction.  
    3. Persist the request to the csb\_requests table in PostgreSQL with an initial status of PENDING.  
    4. Create an initial entry in the csb\_requests\_audit table.  
    5. Publish a job message (containing the full payload and correlation\_id) to the appropriate Redis queue (e.g., queue:aws).  
    6. Immediately returns the correlation\_id and a 202 Accepted HTTP status.  
  * **GET /api/v1/requests/{correlation\_id}**  
    1. Auth and rate-limit the request.  
    2. Implements a **Cache-Aside Read Pattern**:  
       * Attempts to GET the request status from a Redis cache key (e.g., cache:status:\<correlation\_id\>).  
       * **On Cache Hit:** Immediately returns the cached JSON data.  
       * **On Cache Miss:** Queries the PostgreSQL csb\_requests table for the record.  
       * Populates the Redis cache with the result (with a defined TTL) and then returns the data.

### **2.2. Redis (redis)**

A single, persistent Redis instance serves two distinct and critical roles:

* **Caching:** Uses simple **Key-Value pairs** for the cache-aside pattern.  
  * **Key:** cache:status:\<correlation\_id\>  
  * **Value:** JSON object with the request's current status.  
* **Message Queuing:** Uses the **LIST** data type to provide reliable, FIFO queues for each worker.  
  * **Queue Name:** queue:\<cloud\_provider\> (e.g., queue:aws).  
  * **API Service** uses LPUSH to add jobs to the queue.  
  * **Worker Service** uses BRPOP (blocking pop) to consume jobs.

### **2.3. Worker Services (e.g., worker-service-aws)**

Dedicated, asynchronous worker services are responsible for all background processing and direct interaction with target platform APIs.

* **Technology:** Python, Gunicorn  
* **Core Workflow:**  
  1. **Consume Job:** Blocks on and consumes a job from its dedicated Redis list (e.g., BRPOP queue:aws).  
  2. **Validate & Lock:**  
     * Queries the PostgreSQL csb\_requests table to verify the job's correlation\_id exists and its status is PENDING. This prevents duplicate or unauthorized processing.  
     * Atomically updates the job's status to IN\_PROGRESS in the database to act as a processing lock.  
  3. **Execute Logic:** Performs the platform-specific operations. For AWS:  
     * Uses its master credentials to call sts:AssumeRole in the target account.  
     * Uses the temporary credentials to perform the IAM action (e.g., attach\_policy, detach\_policy).  
  4. **Handle Retry/Failure:**  
     * **Transient Failure** (e.g., API throttling, network error): Reverts the status in PostgreSQL back to PENDING and uses LPUSH to re-queue the job for immediate retry.  
     * **Permanent Failure** (e.g., AccessDenied, NoSuchEntity): Updates the status to FAILED and logs the error in the audit table. The job is discarded.  
  5. **Handle Success:**  
     * Updates the status to SUCCESS in the csb\_requests table.  
     * Logs the success and any external IDs (like an AWS Request ID) to the csb\_requests\_audit and csb\_requests\_ref tables.  
  6. **Cache Management:**  
     * After any final update (Success or Failed), the worker is responsible for **deleting the cache key** from Redis (e.g., DEL cache:status:\<correlation\_id\>).  
     * This invalidates the stale cache entry, ensuring that the next GET request from the API will fetch the fresh, completed status directly from the database and re-populate the cache.

### **2.4. PostgreSQL Database (postgres-db)**

The PostgreSQL database is the central **System of Record**, providing durable, transactional storage for the state of all requests.

* **Schema Design:** The application schema (CSB\_APP) uses a unified set of tables:  
  * **csb\_requests**: The primary table storing the current state of every request (correlation\_id, status, principal, action, etc.).  
  * **csb\_requests\_audit**: An append-only audit log of all status changes (IN\_PROGRESS, FAILED, SUCCESS) for each correlation\_id, providing a complete history.  
  * **csb\_requests\_ref**: Stores external reference IDs (e.g., AWS Request IDs) associated with a successful request for auditing and cross-referencing.  
* **Security:**  
  * **Roles:** Defines specific roles for each service (CSB\_API\_USER, CSB\_AWS\_USER) with least-privilege permissions.  
  * **Row-Level Security (RLS):** RLS is enabled on the csb\_requests table. Policies ensure that a worker (e.g., CSB\_AWS\_USER) can *only* SELECT and UPDATE rows where cloud\_provider \= 'aws'.

### **2.5. Observability Service**

A centralized platform for monitoring, logging, and troubleshooting the entire system.

* **Technology:** **EFK Stack (Elasticsearch, Fluentd, Kibana)**.  
* **Logging:** All services (Flask, Gunicorn, Workers) are configured with python-json-logger to log to stdout as structured JSON.  
* **Aggregation:** Fluentd, running as a DaemonSet in Kubernetes, will automatically collect these container logs, parse the JSON, and forward them to Elasticsearch for storage and analysis in Kibana.

## **3\. Orchestration & Deployment (.github/, helm/)**

The entire platform is managed using modern CI/CD and GitOps principles.

* **Containerization:** All services are containerized with **Docker**. Dockerfiles are multi-stage to produce minimal, secure final images running as non-root users.  
* **CI/CD Pipelines:** **GitHub Actions** workflows (.github/workflows/) automate:  
  * Building and pushing versioned Docker images to a container registry (GHCR).  
  * Creating Kubernetes secrets.  
  * Deploying or updating services using Helm.  
* **Platform Setup:** **Kustomize** (platform-config/) is used to bootstrap the Kubernetes environment (Namespaces, RBAC Roles, ServiceAccounts) before any applications are deployed.  
* **Deployment:** **Helm** charts are used to manage the deployment of each microservice (api-service, postgres-db, redis) as a repeatable, configurable package. This includes managing Deployments/StatefulSets, Services, ConfigMaps, and NetworkPolicies.