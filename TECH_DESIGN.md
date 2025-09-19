# **CSecBridge \- Microservice Architecture**

## **Overview**

This design outlines a decoupled, microservice-based architecture. Each component is a distinct, containerised service that communicates over a network, primarily via a message queue. A central PostgreSQL database acts as the system of record for state management, while a comprehensive observability stack provides system-wide visibility.

![Architecture Diagram](./images/csecbridge_arch.png)

## **1\. API Service (csecbridge-api)**

The API service is the primary, customer-facing entry point, designed to be a lightweight and stateless bridge for all incoming requests.

* **Technology:** Flask (or a high-performance alternative like FastAPI).  
* **Endpoints:**  
  * **POST /api/v1/requests**  
    * Authenticates the incoming request via a shared secret token.  
    * Generates a unique correlation\_id (UUID) for the transaction.  
    * Performs strict, fail-fast validation of the request payload against a predefined JSON schema.  
    * Persists the request to the PostgreSQL database with an initial status of PENDING.  
    * Publishes a job message containing the request details to the appropriate Redis queue (e.g., queue:aws).  
    * Immediately returns the correlation\_id to the client with a 202 Accepted HTTP status.  
  * **GET /api/v1/requests/{correlation\_id}**  
    * Authenticates the incoming request.  
    * **Cache-Aside Read Pattern:**  
      1. Attempts to fetch the request status from the Redis cache using the correlation\_id.  
      2. **On Cache Hit:** Immediately returns the cached data.  
      3. **On Cache Miss:** Queries the PostgreSQL database for the record, populates the Redis cache with the result (with a defined TTL), and then returns the data.

**Note:** The status endpoint uses the RESTful convention GET /api/v1/requests/{correlation\_id} for retrieving a specific resource.

## **2\. Redis Service (csecbridge-cache-broker)**

A single Redis instance serves two distinct roles: a low-latency cache and a reliable message broker.

* **Caching:** Uses simple **Key-Value pairs** for the cache-aside pattern. The key is the correlation\_id and the value is the request status object.  
* **Message Queuing:** Uses the **LIST** data type to provide separate, reliable queues for each worker service (e.g., queue:aws, queue:azure).

## **3\. & 4\. Worker Services (csecbridge-aws-worker, csecbridge-azure-worker, etc.)**

Dedicated worker services are responsible for all asynchronous processing and direct interaction with cloud provider APIs.

* **Technology:** Python with a robust task-processing library like Celery.  
* **Workflow:**  
  1. Consumes a job from its dedicated Redis list (e.g., csecbridge-aws-worker listens to queue:aws).  
  2. Transforms the legacy request payload into the format required by the target cloud provider's API.  
  3. Executes the necessary IAM operations by invoking the cloud provider's API.  
  4. **Scheduled Revocation:** For requests with a defined expiry, the worker will create a separate, scheduled task to revoke the permissions at the specified time.
  5. Updates the request's status (SUCCESS or FAILED with error details) in the PostgreSQL database.  
  6. **Cache Invalidation:** Issues a DEL command to Redis to remove the (now stale) cache entry for the correlation\_id.

## **5\. PostgreSQL Database Service (csecbridge-db)**

The PostgreSQL database is the central **System of Record**, providing durable, long-term storage for the state of all transactions.

* **Schema Design:** A **single, unified requests table** will store all transactions. A cloud\_provider column will differentiate between AWS, Azure, etc. This approach simplifies application logic and reporting.  
* **Key Columns:** correlation\_id (Primary Key), status, cloud\_provider, request\_payload, received\_at, completed\_at, error\_details.  
* **Indexing:** The correlation\_id and status columns will be indexed to ensure fast lookups.

**Note:** Using a single requests table is a critical design choice for scalability. It prevents schema drift, makes cross-cloud reporting trivial, and simplifies application code.

## **6\. Frontend UI Service (csecbridge-ui)**

A modern web application providing an operational dashboard for visibility and reporting.

* **Functionality:** Allows users to query request status by correlation\_id.  
* **Advanced Search:** The "AI-based search" can be implemented as a **Natural Language Querying (NLQ)** feature, translating text like "show me all failed requests for AWS yesterday" into API calls. This is a forward-looking goal.

## **7\. Observability Service**

A centralised platform for monitoring, logging, and troubleshooting the entire system.

* **Technology:** **EFK Stack (Elasticsearch, Fluentd, Kibana)**. Fluentd is a Kubernetes-native log aggregator that works exceptionally well for collecting container logs.

## **CSecBridge \- Orchestration & Deployment**

The entire platform will be managed using modern CI/CD and GitOps principles.

* **CI/CD Pipelines:** Automated pipelines (using GitHub Actions) will build, test, and containerise each microservice into a **Docker** image upon code changes.  
* **Deployment:** A **Kubernetes** cluster will orchestrate all services. Deployments will be managed via declarative YAML manifests stored in a Git repository, following **GitOps** principles for reliable and repeatable deployments.