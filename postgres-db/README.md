# **PostgreSQL Service (postgres-db)**

This service provides the central state database for the CSecBridge application. It is a persistent PostgreSQL instance deployed as a StatefulSet in Kubernetes.

## **Core Responsibilities**

* **State Storage:** Acts as the single system of record for all access requests, tracking their status from PENDING to SUCCESS or FAILED.  
* **Audit Trail:** Stores a detailed, append-only audit log for all status changes to every request.  
* **Data Durability:** Uses a Kubernetes PersistentVolumeClaim to ensure database files are stored on durable storage, surviving pod restarts and redeployments.

## **Containerization (Dockerfile)**

* **Base Image:** Uses the official postgres:15-alpine image.  
* **Initialization:** Copies the init.sql script into /docker-entrypoint-initdb.d/. This directory is automatically processed by the official Postgres entrypoint *only if the data directory is empty*. This ensures the database schema is bootstrapped on the very first run but is left untouched on subsequent restarts.  
* **Healthcheck:** Includes a HEALTHCHECK instruction that uses pg\_isready to verify the database is up and accepting connections.

## **Database Schema & Initialization**

The database schema is created in two phases:

1. **init.sql (Bootstrap)**:  
   * This script runs *once* when the persistent volume is empty.  
   * **Purpose:** Bootstraps the database with the necessary roles and schemas *before* any tables are created.  
   * **Actions:**  
     * Creates roles: CSB\_APP (schema owner), CSB\_API\_USER, CSB\_AWS\_USER, CSB\_AZURE\_USER.  
     * Creates schema: CSB\_APP (owned by CSB\_APP).  
     * Grants basic CONNECT and USAGE permissions to the service-level roles.  
   * **Note:** Passwords for these roles are *not* set here; they are set by an administrator or pipeline *after* deployment (see run\_db\_tests.sh for an example).  
2. **api-service/sql/backend.sql (Application Schema)**:  
   * This script is *not* part of the postgres-db service. It is run *manually* or by a CI/CD pipeline *after* the database is running.  
   * **Purpose:** Creates the actual application tables within the CSB\_APP schema.  
   * **Actions:**  
     * Creates tables: csb\_requests, csb\_requests\_audit, csb\_requests\_ref.  
     * Creates indices for fast lookups (e.g., on correlation\_id, status).  
     * Grants SELECT, INSERT, UPDATE permissions to CSB\_API\_USER and worker roles.  
     * Enables Row-Level Security (RLS) on csb\_requests and creates policies to ensure workers (like CSB\_AWS\_USER) can only see and update rows matching their cloud\_provider.

## **Deployment (helm/)**

This service is deployed to Kubernetes using its own Helm chart.

* **Chart.yaml**: Defines the chart csb-postgres-service.  
* **values.yaml**: Contains all default configuration.  
  * Deploys as a StatefulSet with 1 replica.  
  * Requests 1Gi of storage using the standard StorageClass.  
  * Configures the database instance with POSTGRES\_DB: csb\_app\_db and POSTGRES\_USER: csb\_admin.  
  * Enables a NetworkPolicy by default, allowing ingress traffic *only* from pods with the label app.kubernetes.io/name: csb-api-service.  
  * Enables a custom pg\_hba.conf via a ConfigMap.  
* **templates/statefulset.yaml**: Deploys the service as a StatefulSet to ensure stable network identity and persistent storage. It mounts the PersistentVolumeClaim to /var/lib/postgresql/data.  
* **templates/configmap-hba.yaml**: Creates a ConfigMap named postgres-hba-config that contains a custom pg\_hba.conf. This is mounted into the pod to enforce scram-sha-256 password authentication for clients within the cluster.  
* **templates/networkpolicy.yaml**: Creates a NetworkPolicy resource to firewall the database, restricting ingress to the api-service pods on port 5432\.  
* **templates/service.yaml**: Creates a ClusterIP service named csb-postgres-service to provide a stable internal DNS name for the database.