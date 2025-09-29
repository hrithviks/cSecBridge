# **CSecBridge API Service \- Platform Configuration**

This section contains all the Kubernetes manifests required to set up and manage the platform environments (namespaces, RBAC, etc.) where the api-service application will be deployed.

This configuration is managed using **Kustomize**, the native Kubernetes configuration management tool. This allows us to define a common base configuration and apply environment-specific overlays for dev and prod, following the DRY (Don't Repeat Yourself) principle.

## **Directory Structure**

The configuration is organized into a base and overlays structure:

platform-config/  
├── base/  
│   ├── kustomization.yaml     \# Lists all common resources  
│   ├── namespace.yaml         \# Template for the application namespace  
│   ├── deployment-role.yaml   \# Common RBAC Role for deployments  
│   └── service-account.yaml   \# Template for the CI/CD ServiceAccount  
└── overlays/  
    ├── dev/  
    │   ├── kustomization.yaml \# Defines the 'dev' environment  
    │   └── role-binding.yaml  \# Binds the role to a developer group  
    └── prod/  
        ├── kustomization.yaml \# Defines the 'prod' environment  
        └── role-binding.yaml  \# Binds the role to the CI/CD ServiceAccount

## **Core Components Explained**

### **1\. Namespace**

The base/namespace.yaml file provides a template for creating an isolated logical space for the application. The actual name of the namespace (e.g., csecbridge-dev, csecbridge-prod) is set by the corresponding overlay. This ensures that resources for different environments do not conflict.

### **2\. ServiceAccount (csecbridge-deployer)**

The base/service-account.yaml file defines a non-human identity named csecbridge-deployer. This is the identity that automated processes, specifically the **CI/CD pipeline**, will use to authenticate with the Kubernetes cluster. Using a dedicated ServiceAccount is a critical security best practice that avoids the use of human user credentials in automation.

### **3\. Role (deployment-manager-role)**

The base/deployment-role.yaml file defines a namespaced Role that contains all the permissions necessary to deploy, manage, and troubleshoot the application. This includes permissions to create Deployments, Services, Secrets, and view pod logs. By defining this in the base, we ensure that the set of permissions is consistent across all environments.

### **4\. RoleBinding**

The RoleBinding is an environment-specific resource defined in the overlays. Its job is to grant the permissions from the deployment-manager-role to a specific subject within that environment's namespace.

* **In dev:** The role-binding.yaml grants the role to a human user group (e.g., csecbridge-developers), allowing developers to deploy manually.  
* **In prod:** The role-binding.yaml grants the role to the csecbridge-deployer ServiceAccount, ensuring that only the automated CI/CD pipeline can perform deployments.

## **How to Use**

This platform configuration should be applied **before** the application's Helm chart is deployed. The commands are designed to be run from the root of the api\_service/ directory.

### **To Deploy the dev Environment**

This single command uses Kustomize (-k) to build and apply the complete configuration for the development environment.

kubectl apply \-k platform-config/overlays/dev

### **To Deploy the prod Environment**

Similarly, this command applies the production environment configuration.

kubectl apply \-k platform-config/overlays/prod