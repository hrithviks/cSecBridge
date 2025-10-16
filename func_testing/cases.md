# **CSecBridge \- Integration Test Plan**

**Objective:** To define and execute a series of integration tests that validate the core functionality, reliability, and data integrity of the CSecBridge microservices as they are developed.

**Scope:** This initial version of the test plan focuses specifically on the integration between the api-service and its backend dependencies (postgres\_db and redis). It is a living document that will be expanded to include worker services and full end-to-end request lifecycle tests in the future.

## **1\. Platform and Environment Validation**
This section validates that the foundational Kubernetes environment is correctly configured before any application services are deployed. 

To perform quick testing and validation, run the **bash script** - `bash func_testing/run_platform_test.sh`

* \[ \] **TC-P01: kubectl Cluster Connectivity Verification**  
  * **Action:** Run `kubectl cluster-info`
  * **Expected Result:** The command should execute successfully and display the addresses of the Kubernetes control plane and services, confirming connectivity to the cluster.

* \[ \] **TC-P02: Namespace Validation**  
  * **Action:** Run `kubectl get namespace csecbridge-dev`  
  * **Expected Result:** The command should return the csecbridge-dev namespace with a status of Active.

* \[ \] **TC-P03: RBAC Role Validation**  
  * **Action:** Run `kubectl get role csb-app-manager -n csecbridge-dev`
  * **Expected Result:** Commands should return the role definition successfully.

* \[ \] **TC-P04: ServiceAccount Validation**  
  * **Action:** Run `kubectl get serviceaccount csecbridge-deployer -n csecbridge-dev`
  * **Expected Result:** Commands should return the service account definition successfully.

* \[ \] **TC-P05: RBAC RoleBinding Validation**  
  * **Action:** Run `kubectl get rolebinding dev-deployment-manager-binding -n csecbridge-dev -o json | jq -e '(.roleRef.name == "csb-app-manager") && (.subjects[0].kind == \"ServiceAccount\") && (.subjects[0].name == \"csecbridge-deployer\")'` 
  * **Expected Result:** The jsonified output should clearly show that the deployment-manager-role (Role) is bound to the csecbridge-deployer (ServiceAccount).
