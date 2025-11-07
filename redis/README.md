# **Redis Service (redis)**

This service provides a persistent Redis instance for the CSecBridge application, deployed as a StatefulSet in Kubernetes.

## **Core Responsibilities**

This service serves two critical, distinct functions:

1. **Message Broker:** Acts as the job queue for the worker services. The api-service performs an LPUSH to a list (e.g., queue:aws), and the corresponding worker service uses a blocking BRPOP to consume jobs from that list.  
2. **Cache:** Provides a low-latency cache for request statuses. The api-service uses a cache-aside pattern (checking Redis GET before querying the DB) to speed up status checks.

## **Containerization (Dockerfile)**

* **Base Image:** Uses the official redis:7-alpine image.  
* **Configuration:** Copies the custom redis.conf file into the image.  
* **Healthcheck:** Includes a HEALTHCHECK instruction that uses redis-cli ping with the REDIS\_PASSWORD to ensure the instance is responsive and authenticated.  
* **Entrypoint:** Starts the redis-server explicitly using the path to the custom redis.conf.

## **Configuration (redis.conf)**

The custom redis.conf file provides a secure, persistent configuration:

* **protected-mode yes**: Enforces security best practices.  
* **requirepass password-placeholder**: Requires all clients to authenticate. The actual password is set via the REDIS\_PASSWORD environment variable in the StatefulSet template.  
* **appendonly yes**: Enables Append Only File (AOF) persistence.  
* **appendfsync everysec**: A good balance of performance and durability, ensuring data is written to disk every second.  
* **dir /data**: Sets the data directory, which is mounted to a PersistentVolume.  
* **logfile ""**: Logs to stdout so logs can be collected by Kubernetes.

## **Planned Security (csb.acl)**

The csb.acl file defines a plan for fine-grained Access Control Lists (ACLs) to enforce the principle of least privilege. This is a planned enhancement and is not yet implemented by the default redis.conf.

* **csb-api-client**: Would have permissions to LPUSH to queues (queue:\*) and GET/SET cache entries (cache:general:\*).  
* **csb-aws-worker**: Would *only* have permission to BRPOP from queue:aws and SET data to cache:aws:\*.

## **Deployment (helm/)**

This service is deployed to Kubernetes using its own Helm chart.

* **Chart.yaml**: Defines the chart csb-redis-service.  
* **values.yaml**: Contains all default configuration.  
  * Deploys as a StatefulSet with 1 replica.  
  * Requests 0.5Gi (512Mi) of storage.  
  * Enables a NetworkPolicy by default, allowing ingress traffic *only* from pods with the label app.kubernetes.io/name: csb-api-service.  
* **templates/statefulset.yaml**: Deploys the service as a StatefulSet.  
  * It mounts a PersistentVolumeClaim to /data (matching redis.conf).  
  * It mounts the redis.conf from a ConfigMap into the pod.  
  * It securely passes the REDIS\_PASSWORD from a Kubernetes secret into the container's environment, which the redis-server command then uses to set the password.  
* **templates/configmap.yaml**: Creates a ConfigMap named csb-redis-service-config that holds the contents of redis.conf.  
* **templates/networkpolicy.yaml**: Creates a NetworkPolicy to firewall Redis, restricting ingress to api-service pods on port 6379\.  
* **templates/service.yaml**: Creates a ClusterIP service named csb-redis-service to provide a stable internal DNS name.