# **CSecBridge \- Platform Configuration**

This directory contains all the Kubernetes manifests required to set up and manage the foundational platform (namespaces, RBAC, etc.) where the csecbridge application services will be deployed.

This configuration is managed using **Kustomize**, the native Kubernetes configuration management tool. This allows us to define a common base configuration and apply environment-specific overlays for dev, qa, and prod.

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
    │   └── role-binding.yaml  \# Binds the role to the SA in the 'csb-dev' namespace  
    ├── qa/  
    │   ├── kustomization.yaml \# Defines the 'qa' environment  
    │   └── role-binding.yaml  \# Binds the role to the SA in the 'csb-qa' namespace  
    └── prod/  
        ├── kustomization.yaml \# Defines the 'prod' environment  
        └── role-binding.yaml  \# Binds the role to the SA in the 'csb-prod' namespace

## **Core Components**

### **1\. Namespace**

The base/namespace.yaml file provides a template (csb-placeholder) for creating an isolated logical space for the application. The *actual name* of the namespace (e.g., csb-dev, csb-qa, csb-prod) is patched by the corresponding overlay. This ensures that resources for different environments do not conflict.

### **2\. ServiceAccount (csb-app-sa)**

The base/service-account.yaml file defines a non-human identity named csb-app-sa. This is the identity that automated processes, specifically the **CI/CD pipeline (GitHub Actions)**, will use to authenticate with the Kubernetes cluster. Using a dedicated ServiceAccount is a critical security best practice that avoids the use of human user credentials in automation.

### **3\. Role (csb-app-deployer-role)**

The base/deployment-role.yaml file defines a namespaced Role that contains all the permissions necessary to deploy, manage, and troubleshoot the application (e.g., create Deployments, Services, Secrets, and view pod logs). By defining this in the base, we ensure that the set of permissions is consistent across all environments.

### **4\. RoleBinding**

The RoleBinding is an environment-specific resource defined in each overlay. Its job is to grant the permissions from the csb-app-deployer-role to a specific **subject** within that environment's namespace.

In all (dev, qa, prod) overlays, the role-binding.yaml grants the csb-app-deployer-role to the csb-app-sa ServiceAccount, ensuring that only the automated CI/CD pipeline can perform deployments.

## **How to Use**

This platform configuration should be applied **before** any application Helm charts are deployed. The commands are designed to be run from the root of the repository.

### **To Deploy/Update the qa Environment**

This single command uses kubectl apply \-k (which invokes Kustomize) to build and apply the complete configuration for the qa environment.

kubectl apply \-k platform-config/overlays/qa

### **To Deploy/Update the dev Environment**

kubectl apply \-k platform-config/overlays/dev

### **To Deploy/Update the prod Environment**

kubectl apply \-k platform-config/overlays/prod  
