# **CSecBridge API Service Helm Chart**

This Helm chart deploys the CSecBridge API Service, a Flask-based application, to a Kubernetes cluster.

It is designed to be configurable for various environments and follows best practices for security and scalability, including support for health probes, resource management, autoscaling, and network policies.

## **Prerequisites**

* Kubernetes cluster v1.21+ with a Network Policy provider (e.g., Calico, Cilium).  
* Helm v3.2.0+  
* A pre-existing namespace where the service will be deployed.  
* Backend services (PostgreSQL, Redis) must be available and accessible from within the cluster.

## **Installing the Chart**

To install the chart with the release name api-release into the csecbridge-dev namespace:

\# To install with default values (which creates secrets), run:  
helm install api-release ./api\_service/helm \--namespace csecbridge-dev

\# To override a value, for example to disable secret creation for a  
\# CI/CD pipeline, you can use the \--set flag:  
helm install api-release ./api\_service/helm \--namespace csecbridge-dev \--set secrets.create=false

## **Uninstalling the Chart**

To uninstall the api-release deployment:

helm uninstall api-release \--namespace csecbridge-dev

## **Configuration**

The following table lists the configurable parameters of the API Service chart and their default values. The parameters are structured to match the values.yaml file.

### **Deployment Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| deployment.replicaCount | Number of pods to run for the deployment. | 1 |
| deployment.image.repository | The container image to use. | csecbridge-api-service |
| deployment.image.tag | The tag of the container image. | "" (uses Chart.AppVersion) |
| deployment.image.pullPolicy | The image pull policy. | IfNotPresent |
| deployment.resources | CPU/Memory resource requests and limits for the container. | {} (No limits) |

### **Service and Ingress Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| service.type | The type of Kubernetes Service to create. | ClusterIP |
| service.port | The port the Service and container expose. | 8000 |
| ingress.enabled | If true, an Ingress resource will be created. | false |
| ingress.hosts | A list of hostnames and paths for the Ingress. | \[{host: "...", paths: \[...\]}\] |
| ingress.annotations | A dictionary of annotations to add to the Ingress. | {} |

### **Autoscaling Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| autoscaling.enabled | If true, a HorizontalPodAutoscaler will be created. | false |
| autoscaling.minReplicas | Minimum number of replicas for the HPA. | 1 |
| autoscaling.maxReplicas | Maximum number of replicas for the HPA. | 5 |
| autoscaling.targetCPUUtilizationPercentage | Target CPU utilization to trigger scaling. | 80 |

### **Application Configuration (ConfigMap)**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| config.cacheTtlSeconds | TTL for Redis cache entries in seconds. | 300 |
| config.postgresMaxConn | Max connections for the app's database pool. | 5 |
| config.allowedOrigin | The CORS allowed origin for the frontend UI. | "http://localhost:3000" |
| config.postgresHost | Hostname for the PostgreSQL service. | postgres-service |
| config.postgresPort | Port for the PostgreSQL service. | 5432 |
| config.postgresUser | Username for the PostgreSQL database. | csecbridge\_user |
| config.postgresDb | Name of the PostgreSQL database. | csecbridge\_db |
| config.redisHost | Hostname for the Redis service. | redis-service |
| config.redisPort | Port for the Redis service. | 6379 |
| config.postgresSslEnabled | If true, the app will connect to PostgreSQL using SSL. | false |
| config.redisSslEnabled | If true, the app will connect to Redis using SSL. | false |

### **Secrets Management**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| secrets.create | If true, the chart will create Secret objects. Set to false for production. | true |
| secrets.apiAuthToken | The static API token for authentication. | super-secret-test-token |
| secrets.postgresPassword | The password for the PostgreSQL database. | a-very-strong-and-random-password |
| secrets.redisPassword | The password for the Redis service. | another-strong-random-password |

### **NetworkPolicy Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| networkPolicy.enabled | If true, a NetworkPolicy resource will be created to firewall the pods. | true |
| networkPolicy.egress.postgres.podSelector | The labels to select the PostgreSQL pods for allowed outbound traffic. | app.kubernetes.io/name: postgresql |
| networkPolicy.egress.redis.podSelector | The labels to select the Redis pods for allowed outbound traffic. | app.kubernetes.io/name: redis |
| networkPolicy.egress.dns.podSelector | The labels to select the Kubernetes DNS pods for allowed outbound traffic. | k8s-app: kube-dns |