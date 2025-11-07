# **CSecBridge API Service Helm Chart**

This Helm chart deploys the CSecBridge API Service, a Flask-based application, to a Kubernetes cluster.

It is designed to be configurable for various environments and follows best practices for security and scalability, including support for health probes, resource management, autoscaling, and network policies.

## **Prerequisites**

* Kubernetes cluster v1.21+ with a Network Policy provider (e.g., Calico, Cilium).  
* Helm v3.2.0+  
* A pre-existing namespace where the service will be deployed (managed by platform-config).  
* A ServiceAccount with correct RBAC permissions (managed by platform-config).  
* Backend services (PostgreSQL, Redis) must be available and accessible from within the cluster.  
* Kubernetes secrets for the API token, DB password, and Redis password must be created in the target namespace *before* deploying this chart.

## **Installing the Chart**

This chart is designed to be deployed by a CI/CD pipeline (like the one in .github/workflows/api-service.yaml) which handles secret creation and provides dynamic values.

Example deployment command:

helm upgrade \--install api-service-release ./api-service/helm \\  
  \--namespace csecbridge-dev \\  
  \--set deployment.image.uri="ghcr.io/hrithviks/csecbridge-api-service:dev-sha12345" \\  
  \--set secrets.apiToken.name="csb-api-token-secret" \\  
  \--set secrets.postgres.name="csb-postgres-api-user-secret" \\  
  \--set secrets.redis.name="csb-redis-user-secret"

## **Uninstalling the Chart**

To uninstall the api-service-release deployment:

helm uninstall api-service-release \--namespace csecbridge-dev

## **Configuration**

The following table lists the configurable parameters of the API Service chart and their default values from values.yaml.

### **Deployment Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| deployment.replicaCount | Number of pods to run for the deployment. | 1 |
| deployment.image.uri | The container image URI to use. | ghcr.io/hrithviks/csb-api-qa |
| deployment.image.pullPolicy | The image pull policy. | Always |
| deployment.image.tag | The tag of the container image. | latest |
| deployment.resources | CPU/Memory resource requests and limits. | (requests: 100m, 128Mi) |

### **Service Account**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| serviceAccount.name | Name of the *existing* ServiceAccount to use. | csb-app-sa |

### **Image Pull Secrets**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| imagePullSecrets\[0\].name | Name of the *existing* secret to pull container images. | csb-gh-secret |

### **Service and Ingress Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| service.type | The type of Kubernetes Service. | ClusterIP |
| service.port | The port the Service and container expose. | 8000 |
| ingress.enabled | If true, an Ingress resource will be created. | false |
| ingress.hosts | Host and path rules for the Ingress. | csecbridge-api.local |

### **Autoscaling Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| autoscaling.enabled | If true, a HorizontalPodAutoscaler is created. | false |
| autoscaling.minReplicas | Minimum number of replicas for the HPA. | 1 |
| autoscaling.maxReplicas | Maximum number of replicas for the HPA. | 5 |
| autoscaling.targetCPUUtilizationPercentage | Target CPU utilization to trigger scaling. | 80 |

### **Application Configuration (ConfigMap)**

These values are populated into the csb-api-service-config ConfigMap.

| Parameter | Description | Default |
| :---- | :---- | :---- |
| config.postgresMaxConn | Max connections for the app's database pool. | 10 |
| config.allowedOrigin | The CORS allowed origin for the frontend UI. | localhost |
| config.postgresHost | Hostname for the PostgreSQL service. | csb-postgres-service |
| config.postgresPort | Port for the PostgreSQL service. | 5432 |
| config.postgresUser | Username for the PostgreSQL database. | csb\_api\_user |
| config.postgresDb | Name of the PostgreSQL database. | csb\_app\_db |
| config.redisHost | Hostname for the Redis service. | csb-redis-service |
| config.redisPort | Port for the Redis service. | 6379 |
| config.redisUser | Username for the Redis ACL user. | csb\_api\_client |

### **Secrets Management**

This chart **does not create secrets**. It maps environment variables to *existing* Kubernetes secrets.

| Parameter | Description | Default |
| :---- | :---- | :---- |
| secrets.enabled | (Deprecated) Placeholder, as secrets are mounted from existing ones. | false |
| secrets.apiToken.name | Name of the *existing* secret holding the API token. | csb-api-token-secret |
| secrets.apiToken.key | Key within the secret for the API token. | csb-api-token |
| secrets.postgres.name | Name of the *existing* secret holding the DB password. | csb-postgres-api-user-secret |
| secrets.postgres.key | Key within the secret for the DB password. | csb-api-user-pswd |
| secrets.redis.name | Name of the *existing* secret holding the Redis password. | csb-redis-user-secret |
| secrets.redis.key | Key within the secret for the Redis password. | csb-api-redis-pswd |

### **NetworkPolicy Settings**

| Parameter | Description | Default |
| :---- | :---- | :---- |
| networkPolicy.enabled | If true, a NetworkPolicy is created to firewall pods. | false |
| networkPolicy.egress.postgres.podSelector | Labels to select the PostgreSQL pods (for egress). | app.kubernetes.io/name: postgresql |
| networkPolicy.egress.redis.podSelector | Labels to select the Redis pods (for egress). | app.kubernetes.io/name: redis |
| networkPolicy.egress.dns.podSelector | Labels to select the Kubernetes DNS pods (for egress). | k8s-app: kube-dns |
