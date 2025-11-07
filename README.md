# **cSecBridge \- Hybrid Identity & Access Gateway**

CSecBridge is a modern, cloud-native security solution designed to act as a hybrid gateway for managing Identity and Access Management (IAM). It provides a centralized bridge between traditional on-premise access management systems and various dynamic target platforms, from public clouds like AWS and Azure to enterprise solutions like HashiCorp Terraform Cloud.

## **🏛️ High-Level Architecture**

The project is built on a decoupled, microservice-based architecture designed for scalability, resilience, and maintainability. All services are containerized with Docker and intended to be deployed and orchestrated by Kubernetes.

For a detailed breakdown of the architectural design, please see the [**Architectural Design Document**](https://www.google.com/search?q=./csecbridge_architecture.md).

The core components of the system are:

* **API Service (api-service):** A Flask-based, public-facing entry point that validates and queues all incoming access requests.  
* **Worker Services:** Asynchronous background workers, each specialized for a target platform (e.g., AWS, Azure), responsible for communicating with platform APIs to execute the requested IAM operations.  
* **State Database (PostgreSQL):** The central system of record for the state of all access requests.  
* **Cache & Message Broker (Redis):** Provides a low-latency cache for status checks and acts as the message queue for decoupling the API from the workers.  
* **Observability (EFK Stack):** A centralized logging and monitoring stack to provide system-wide visibility.

## **📁 Repository Structure**

This is a monorepo containing the source code and configuration for all of CSecBridge's microservices and platform components.

```
csecbridge/
├── .github/
│   └── workflows/
├── platform-config/
│   ├── base/
│   └── overlays/
├── api-service/
│   ├── Dockerfile
│   ├── helm/
│   ├── src/
│   ├── sql/
│   └── unit_test/
├── frontend-service/
├── worker-service-aws/
├── worker-service-azure/
├── postgres-db/
│   ├── Dockerfile
│   ├── init.sql
│   ├── helm/
│   └── unit_test/
├── cache/
├── observability/
└── func_testing/
```

## **🚀 Getting Started**

This section provides a high-level guide to setting up and running the api-service in a local test environment.
**Under Development**

# License 📄
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
