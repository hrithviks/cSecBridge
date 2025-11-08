# **cSecBridge \- Hybrid Identity & Access Gateway**

CSecBridge is a modern, cloud-native security solution designed to act as a hybrid gateway for managing Identity and Access Management (IAM). It provides a centralized bridge between traditional on-premise access management systems and various dynamic target platforms, from public clouds like AWS and Azure to enterprise solutions like HashiCorp Terraform Cloud.

## **🏛️ High-Level Architecture**

The project is built on a decoupled, microservice-based architecture designed for scalability, resilience, and maintainability. All services are containerized with Docker and intended to be deployed and orchestrated by Kubernetes.

For a detailed breakdown of the architectural design, please see the [**Technical Design Document**](https://github.com/hrithviks/cSecBridge/blob/main/docs/tech-design.md).

### **Core Components**

* **API Service (api-service):** A public-facing Flask application that acts as the stateless entry point. It validates all incoming access requests, persists them to the database with a PENDING status, and enqueues them into a Redis job queue.  
* **PostgreSQL Database (postgres-db):** The central system of record and state database for all access requests. It stores the status of every transaction.  
* **Redis (redis):** A dual-purpose service providing:  
  1. **Message Broker:** Manages job queues for different cloud providers (e.g., queue:aws).  
  2. **Cache:** Stores request statuses for fast retrieval by the API's GET endpoint.  
* **Worker Services (worker-service-aws, etc.):** Asynchronous background workers (one for each target platform) that consume jobs from the Redis queue. They are responsible for communicating with the target platform's APIs (e.g., AWS IAM) to execute the requested operations and update the request status in the database.  
* **Platform Configuration (platform-config):** A collection of Kustomize manifests to bootstrap the Kubernetes environment (Namespaces, RBAC Roles, ServiceAccounts) where the application services will be deployed.

## **📁 Repository Structure**

This is a monorepo containing the source code and configuration for all of CSecBridge's microservices and platform components.

```
csecbridge/  
├── .github/  
│   ├── actions/                # Reusable GitHub Actions for CI/CD  
│   │   ├── build-docker-image/  
│   │   ├── create-kube-secrets/  
│   │   ├── helm-deploy/  
│   │   └── setup-kube-config/  
│   └── workflows/              # CI/CD pipelines  
│       ├── api-service.yaml  
│       ├── db-service.yaml  
│       ├── platform.yaml  
│       └── release.yaml  
│  
├── api-service/  
│   ├── Dockerfile  
│   ├── helm/                   # Helm chart for the API service  
│   ├── src/                    # Python source code (Flask app)  
│   └── sql/                    # SQL scripts for table creation  
│  
├── docs/  
│   └── TECH\_DESIGN.md         # Detailed architectural document  
│  
├── func-testing/  
│   ├── cases.md  
│   └── run_*.sh                # Functional test scripts for each component  
│  
├── platform-config/  
│   ├── README.md  
│   ├── base/                   # Kustomize base configuration  
│   └── overlays/               # Environment-specific overlays (dev, qa, prod)  
│       ├── dev/  
│       ├── prod/  
│       └── qa/  
│  
├── postgres-db/  
│   ├── Dockerfile  
│   ├── helm/                   # Helm chart for PostgreSQL  
│   ├── init.sql                # Initial DB/role creation (for empty volume)  
│   └── unit_test/  
│  
├── redis/  
│   ├── Dockerfile  
│   ├── helm/                   # Helm chart for Redis  
│   ├── redis.conf              # Custom Redis configuration  
│   └── csb.acl                 # (Planned) Redis ACL definitions  
│  
├── worker-service-aws/  
│   ├── Dockerfile  
│   └── src/                    # Python source code (AWS worker)  
│  
└── README.md                   # This file
```

## **🚀 Getting Started**

This section provides a high-level guide to setting up and running the api-service in a local test environment.  
(Under Development)

## **License 📄**

This project is licensed under the MIT License.