#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge PostgreSQL Service - CI Process Validation Script
#
# This script automates the validation of the build and deployment mechanics for
# the postgres_service. It is designed to be run locally to test the
# automation before it's integrated into a full CI/CD pipeline.
#
# It executes the following stages:
#   1. Checks all env configuration for runtime and kubernetes resources.
#   2. Builds the PostgreSQL Docker image.
#   3. Securely creates the database password secret in the cluster.
#   4. Deploys the postgres_service Helm chart.
#   5. Verifies that the StatefulSet becomes ready.
#   6. Generates a report and tears down the entire test env for database.
#
# Usage: ./run_db_tests.sh
# -----------------------------------------------------------------------------

# Global configuration
set -e
set -o pipefail # Exit on pipe failures
. ./set_test_env.sh

log_info "Starting database testing"

# Test Configuration
CSB_NAMESPACE="csb-qa"
CSB_SA_NAME="csb-app-sa"
CSB_ROLE_NAME="csb-app-deployer-role"
CSB_DB_SERVICE_PATH="../postgres-db/"
CSB_DB_HELM_CHART_PATH="${CSB_DB_SERVICE_PATH}/helm"
CSB_DB_RELEASE_NAME="csb-db-rel"

# Environment setup function
validate_platform_config() {

  local platform_val_status=0
  # Check environment variables
  log_info "Verifying github environment variables..."
  if [ -z ${GH_USER} ] || [ -z ${GH_TOKEN} ]; then
    log_info "${RED}Environment vars missing for the containerization section...${RESET}"
    platform_val_status=1
  fi

  # Environment variables for kubernetes secrets
  log_info "Verifying postgres environment variables..."
  if [ -z "${CSB_POSTGRES_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    platform_val_status=1
  fi

  # Environment variables for user administration
  log_info "Verifying database user environment variables..."
  if [ -z "${CSB_APP_USER_PSWD}" ] || [ -z "${CSB_API_USER_PSWD}" ]; then
    log_info "${RED} Missing environment variables for testing app and api user administration"
    return 2
  fi
  
  # Platform configuration - Check Namespace
  log_info "Verifying kubernetes namespace..."
  if ! kubectl get namespace "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Namespace '${CSB_NAMESPACE}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    platform_val_status=1
  fi

  # Platform configuration - Check Service account
  log_info "Verifying kubernetes service account..."
  if ! kubectl get serviceaccount "$CSB_SA_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: ServiceAccount '${CSB_SA_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    platform_val_status=1
  fi

  # Platform configuration - Check RBAC
  log_info "Verifying kubernetes RBAC..."
  if ! kubectl get role "$CSB_ROLE_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Role '${CSB_ROLE_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    platform_val_status=1
  fi

  return $platform_val_status
}

run_db_ci_cd_tests() {
  log_info "Running Database Service CI Validation..."
  local overall_status=0
  ###############################
  # Section 1: Containerization #
  ###############################
  log_info "Section 1: Containerization Tests..."

  # Local Env Vars for Testing
  local IMAGE_NAME="csb-db-qa"
  local IMAGE_TAG="latest"
  local GHCR_IMAGE="ghcr.io/${GH_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

  # DB-01: Test build success
  if ! run_test "DB-01  :: Docker Image Build" "success" "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ${CSB_DB_SERVICE_PATH}"; then
    return 2
  fi

  # DB-02: Test docker login(Section A) and push to github container registry(Section B)
  if ! run_test "DB-02A :: GitHub Container Registry Login" "success" "docker login ghcr.io -u ${GH_USER} -p ${GH_TOKEN}"; then
    overall_status=1
  else
    # If login successful, tag and test push
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$GHCR_IMAGE" 2>/dev/null
    if ! run_test "DB-02B :: Image Push to GitHub Container Registry" "success" "docker push ${GHCR_IMAGE}"; then
      overall_status=1
    fi
  fi

  # DB-03: Test build failure - by introducing a syntax error in the Dockerfile
  sed -i.bak 's/COPY/COPPY/' "${CSB_DB_SERVICE_PATH}/Dockerfile"
  if ! run_test "DB-03  :: Docker Image Build (Failure)" "failure" "docker build -t csb-db-qa-fail:latest ${CSB_DB_SERVICE_PATH}"; then
    overall_status=1
  fi

  # Clean up after test
  git restore "${CSB_DB_SERVICE_PATH}/Dockerfile"
  if [ $? -eq 0 ]; then
    rm -f "${CSB_DB_SERVICE_PATH}/Dockerfile.bak"
  fi

  ###############################
  # Section 2: Kubernetes Tests #
  ###############################
  log_info "Section 2: Kubernetes Tests..."

  # This command mimics a CI/CD pipeline securely creating the secret for admin user
  # Secret name is "postgres-admin-secret"
  # Secret key is "csb-admin-password"
  # Secret value is the actual password, retrieved from env vars (secrets on pipeline)

  # DB-04 : Kubernetes DB Secret Creation
  if ! run_test "DB-04  :: Kubernetes DB Secret Creation" "success" "kubectl create secret generic postgres-admin-secret \
    --from-literal=csb-admin-password="${CSB_POSTGRES_PSWD}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for admin password...${RESET}"
    return 127
  fi
  
  # DB-05 : Kubernetes Check Secret - DB Admin Password
  if ! run_test "DB-05  :: Kubernetes DB Secret Check" "success" "kubectl get secret postgres-admin-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for admin password...${RESET}"
    return 127
  fi

  # This command mimics a CI/CD pipeline securely creating the secret for github token
  # Secret name is "csb-gh-secret"
  # Secret type is a Docker registry secret, comprising of username, access token and server name

  # DB-06 : Kubernetes GH Token Secret Creation
  if ! run_test "DB-06  :: Kubernetes Image Secret Creation" "success" "kubectl create secret docker-registry csb-gh-secret \
    --docker-server="ghcr.io" \
    --docker-username="${GH_USER}" \
    --docker-password="${GH_TOKEN}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for image token...${RESET}"
    return 127
  fi
  
  # DB-07 : Kubernetes Check Secret - GH Token
  if ! run_test "DB-07  :: Kubernetes Image Secret Check" "success" "kubectl get secret csb-gh-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for image token...${RESET}"
    return 127
  fi

  ###################################
  # Section 3: Helm Deployment Test #
  ###################################
  log_info "Section 3: Helm Deployment Tests..."

  # DB-08 : Helm Deployment Test
  if ! run_test "DB-08  :: Helm Installation Test" "success" "helm upgrade \
  --install ${CSB_DB_RELEASE_NAME} ${CSB_DB_HELM_CHART_PATH} \
  --namespace ${CSB_NAMESPACE} \
  --set statefulset.image.uri=${GHCR_IMAGE} \
  --wait --timeout=5m > /tmp/helm_install_$$.log 2>&1"; then
    log_info "${RED}Failed to deploy helm chart...${RESET}"
    return 127
  fi
  sleep 5

  # DB-09 : Helm Installation Check
  if ! run_test "DB-09  :: Helm Installation Validation" "success" "helm list \
  -A -n ${CSB_NAMESPACE} | grep ${CSB_DB_RELEASE_NAME}"; then
    log_info "${RED}Failed to validate helm chart deployment...${RESET}"
    return 127
  fi

  ###################################################
  # Section 4: Post Deployment Checks on Kubernetes #
  ###################################################
  log_info "Section 4: Post Deployment Checks on Kubernetes..."

  # Local variables for the section
  local POSTGRES_CONFIGMAP="postgres-hba-config"
  local POSTGRES_NETWORK_POLICY="postgres-service"
  local POSTGRES_SERVICE_NAME="postgres-service"
  local POSTGRES_VOL_TEMPLATE="postgres-db-data"
  local POSTGRES_STATEFULSET="postgres-service"

  # DB-10 : Check if HBA ConfigMap Exists
  if ! run_test "DB-10  :: PostgresDB HBA Config Map Validation" "success" "kubectl \
  get configmap ${POSTGRES_CONFIGMAP} -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to validate the HBA Configmap...${RESET}"
    overall_status=1
  fi

  # DB-11 : Check if Network Policy Exists
  # Note : This is a simple test, validating the existence of the network policy.
  #        Parse the response of operation using json objects, 
  #        to perform more advanced validations for specific networking rules.
  if ! run_test "DB-11  :: PostgresDB Network Policy Validation" "success" "kubectl \
  get networkpolicy ${POSTGRES_NETWORK_POLICY} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the Network Policy...${RESET}"
    overall_status=1
  fi

  # DB-12 : Check if the ClusterIP Service Exists
  if ! run_test "DB-12  :: PostgresDB ClusterIP Service Validation" "success" "kubectl \
  get service ${POSTGRES_SERVICE_NAME} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the ClusterIP Service...${RESET}"
    overall_status=1
  fi

  # DB-13 : Check if the StatefulSet is Ready
  # Note: This is a simple test, testing the existence of the statefulset.
  #       Parse the response of the operation using json objects, to 
  #       perform more advanced validations for specific statefulset properties.
  if ! run_test "DB-13  :: PostgresDB StatefulSet Validation" "success" "kubectl \
  get statefulset ${POSTGRES_STATEFULSET} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the StatefulSet...${RESET}"
    overall_status=1
  fi

  # DB-14 : Check if the Persistent Volume Claim Exists
  if ! run_test "DB-14  :: PostgresDB Persistent Volume Claim Validation" "success" "kubectl \
  get pvc "${POSTGRES_VOL_TEMPLATE}-$POSTGRES_STATEFULSET-0" -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the Persistent Volume Claim...${RESET}"
    overall_status=1
  fi

  # DB-15 : Check if the POD is Running
  # Note: This is a very basic check for the POD status for PostgresDB service.
  #       Additional checks to be added for the pod configuration by 
  #       parsing the output in a json format for more advanced validations.     
  if [ `kubectl get pod -n ${CSB_NAMESPACE} | grep ${POSTGRES_STATEFULSET} | wc -l` -ne 0 ]; then
    if ! run_test "DB-15  :: PostgresDB POD Validation" "success" "kubectl \
    get pod -n ${CSB_NAMESPACE} | grep ${POSTGRES_STATEFULSET}-0 | grep Running > /dev/null 2>&1"; then
      log_info "${RED}Failed to validate the POD status...${RESET}"
      overall_status=1
    fi
  else
    log_info "${RED}Failed to validate the required POD Replica (1)...${RESET}"
    overall_status=1
  fi

  ##########################################################
  # Section 5: Database Service Validation and Admin Tasks #
  ##########################################################
  log_info "Section 5: Database Service Validation and Admin Tasks..."

  local POSTGRES_POD_NAME=${POSTGRES_STATEFULSET}-0
  local POSTGRES_DB="csb_app_db"
  local POSTGRES_ADMIN="csb_admin"
  local KUBE_PSQL_EXEC_CMD="kubectl exec -n ${CSB_NAMESPACE} ${POSTGRES_POD_NAME} -- \
  psql -U ${POSTGRES_ADMIN} -d ${POSTGRES_DB} -c"

  # DB-16 :Test POD Service Status
  # Check the ready prob of postgres-service pod to ensure it is accepting connections
  if ! run_test "DB-16  :: PostgresDB Service Validation" "success" "kubectl \
  wait --for=condition=Ready pod/${POSTGRES_POD_NAME} -n ${CSB_NAMESPACE} --timeout=1m > /dev/null 2>&1"; then
    log_info "${RED}Service validation failed for postgresDB service...${RESET}"
    return 127
  fi

  # DB-17 : Test connection to database using admin and execute \conninfo query
  local PSQL_TEST_CMD="${KUBE_PSQL_EXEC_CMD} 'SELECT 1;'"
  if ! run_test "DB-17  :: PostgresDB Connection Validation" "success" "${PSQL_TEST_CMD}"; then
    log_info "${RED}Connection validation failed for postgresDB service...${RESET}"
    return 127
  fi

  # DB-18A : Validate administration for App user
  local PSQL_ALTER_APP_USER_CMD="${KUBE_PSQL_EXEC_CMD} \"ALTER ROLE CSB_APP WITH PASSWORD '${CSB_APP_USER_PSWD}';\""
  local PSQL_ALTER_API_USER_CMD="${KUBE_PSQL_EXEC_CMD} \"ALTER ROLE CSB_API_USER WITH PASSWORD '${CSB_API_USER_PSWD}';\""
  if ! run_test "DB-18A :: PostgresDB APP User Administration" "success" "${PSQL_ALTER_APP_USER_CMD}"; then
    log_info "${RED}Administration failed for app user...${RESET}"
    overall_status=1
  fi

  # DB-18B : Validate administration for Api user
  if ! run_test "DB-18B :: PostgresDB API User Administration" "success" "${PSQL_ALTER_API_USER_CMD}"; then
    log_info "${RED}Administration failed for api user...${RESET}"
    overall_status=1
  fi

  return $overall_status
}

teardown_environment() {
  local teardown_status=0
  local POSTGRES_VOL_TEMPLATE="postgres-db-data"
  local POSTGRES_STATEFULSET="postgres-service"
  log_info "Tearing down isolated test environment: ${CSB_NAMESPACE}"

  # Uninstall helm chart
  log_info "Uninstalling Helm chart $CSB_DB_RELEASE_NAME..."
  if ! helm uninstall $CSB_DB_RELEASE_NAME -n $CSB_NAMESPACE --ignore-not-found=true > /dev/null 2>&1; then
    log_info "${RED}Failed to uninstall helm chart $CSB_DB_RELEASE_NAME...${RESET}"
    teardown_status=1
  fi
  sleep 5

  # Delete persistent volume claim - if test data is no more required.
  log_info "Deleting persistent volume claim..."
  if ! kubectl delete pvc "${POSTGRES_VOL_TEMPLATE}-$POSTGRES_STATEFULSET-0" -n ${CSB_NAMESPACE} > /dev/null 2>&1; then
    log_info "${RED}Failed to delete persistent volume claim...${RESET}"
    teardown_status=1
  fi
  sleep 5

  # Optional Step - Deleting the namespace automatically garbage collects all resources within it.
  log_info "Deleting namespace $CSB_NAMESPACE..."
  if ! kubectl delete namespace "$CSB_NAMESPACE" --cascade > /dev/null 2>&1; then
    log_info "${RED}Failed to delete namespace $CSB_NAMESPACE...${RESET}"
    teardown_status=1
  fi
  sleep 5

  if [ ${teardown_status} == 0 ]; then
    log_info "Teardown complete..."
  else
    log_info "${RED}Teardown failed. Please check and clear resources manually...${RESET}"
  fi 
}

################
# Main program #
################

# Ensure teardown runs even if the script is interrupted or fails
# To persist test platform, comment the "trap" section out.
# trap teardown_environment EXIT

# Platform validation
if ! validate_platform_config; then
  log_info "${RED}One or more platform validations failed...${RESET}"
  exit 1
else
  log_info "${GREEN}All platform validations passed...${RESET}"
fi

if run_db_ci_cd_tests; then
  final_status=0
else
  final_status=$?
fi

if [ $final_status -eq 0 ]; then
  log_info "${GREEN}All CI validation tests passed successfully...${RESET}"
elif [ $final_status -eq 1 ]; then
  log_info "${RED}One or more CI validation tests failed...${RESET}"
elif [ $final_status -eq 2 ]; then
  log_info "${RED}Testing interrupted due to unexpected misconfiguration...${RESET}"
elif [ $final_status -eq 127 ]; then
  log_info "${RED}Testing aborted...${RESET}"
else
  log_info "${RED}Uknown error occurred during testing...${RESET}"
fi

# The 'trap' will handle the final teardown automatically on exit.
log_info "Script finished..."
