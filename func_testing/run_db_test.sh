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
DB_SERVICE_PATH="../postgres_db/"
HELM_CHART_PATH="${DB_SERVICE_PATH}/helm"
RELEASE_NAME="csb-db-rel"

# Place holder for password
DB_PASSWORD="this_is_not_a_password"

# Environment setup function
setup_environment() {
  
  # Check environment variables
  log_info "Verifying github environment variables..."
  if [ -z ${GH_USER} ] || [ -z ${GH_TOKEN} ]; then
    log_info "${RED}Environment vars missing for the containerization section...${RESET}"
    exit 1
  fi

  # Environment variables for kubernetes secrets
  log_info "Verifying postgres environment variables..."
  if [ -z "${CSB_POSTGRES_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    exit 1
  fi
  
  # Platform configuration - Check Namespace
  log_info "Verifying namespace..."
  if ! kubectl get namespace "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Namespace '${CSB_NAMESPACE}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  # Platform configuration - Check Service account
  log_info "Verifying service account..."
  if ! kubectl get serviceaccount "$CSB_SA_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: ServiceAccount '${CSB_SA_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  # Platform configuration - Check RBAC
  log_info "Verifying RBAC..."
  if ! kubectl get role "$CSB_ROLE_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Role '${CSB_ROLE_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi
}

teardown_environment() {
  log_info "Tearing down isolated test environment: ${NAMESPACE}"
  # Deleting the namespace automatically garbage collects all resources within it.
  #kubectl delete namespace "$CSB_NAMESPACE" --ignore-not-found=true > /dev/null 2>&1
  echo "Teardown complete."
}

run_db_ci_tests() {
  log_info "Running Database Service CI Validation..."
  local overall_status=0
  ###############################
  # Section 1: Containerization #
  ###############################
  echo
  log_info "Section 1: Containerization Tests..."

  # Local Env Vars for Testing
  local DOCKERFILE_PATH=${DB_SERVICE_PATH}
  local IMAGE_NAME="csb-db-qa"
  local IMAGE_TAG="latest"
  local GHCR_IMAGE="ghcr.io/${GH_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

  # DB-01: Test build success
  if ! run_test "DB-01  : Docker Image Build" "success" "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKERFILE_PATH}"; then
    return 2
  fi

  # DB-02: Test docker login(Section A) and push to github container registry(Section B)
  if ! run_test "DB-02A : GitHub Container Registry Login" "success" "docker login ghcr.io -u ${GH_USER} -p ${GH_TOKEN}"; then
    overall_status=1
  else
    # If login successful, tag and test push
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$GHCR_IMAGE" 2>/dev/null
    if ! run_test "DB-02B : Image Push to GitHub Container Registry" "success" "docker push ${GHCR_IMAGE}"; then
      overall_status=1
    fi
  fi

  # DB-03: Test build failure - by introducing a syntax error in the Dockerfile
  sed -i.bak 's/COPY/COPPY/' "${DB_SERVICE_PATH}/Dockerfile"
  if ! run_test "DB-03  : Docker Image Build (Failure)" "failure" "docker build -t csb-db-qa-fail:latest ${API_SERVICE_PATH}"; then
    overall_status=1
  fi

  # Clean up after test
  git restore "${DB_SERVICE_PATH}/Dockerfile"
  if [ $? -eq 0 ]; then
    rm -f "${DB_SERVICE_PATH}/Dockerfile.bak"
  fi

  ###############################
  # Section 2: Kubernetes Tests #
  ###############################
  echo
  log_info "Section 2: Kubernetes Tests..."

  # This command mimics a CI/CD pipeline securely creating the secret for admin user
  # Secret name is "postgres-admin-secret"
  # Secret key is "csb-admin-password"
  # Secret value is the actual password, retrieved from env vars (secrets on pipeline)

  # DB-04 : Kubernetes DB Secret Creation
  if ! run_test "DB-04  : Kubernetes DB Secret Creation" "success" "kubectl create secret generic postgres-admin-secret \
    --from-literal=csb-admin-password="${CSB_POSTGRES_PSWD}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for admin password...${RESET}"
    return 2
  fi
  
  # DB-05 : Kubernetes Check Secret - DB Admin Password
  if ! run_test "DB-05  : Kubernetes DB Secret Check" "success" "kubectl get secret postgres-admin-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for admin password...${RESET}"
    return 2
  fi

  # This command mimics a CI/CD pipeline securely creating the secret for github token
  # Secret name is "csb-gh-secret"
  # Secret key is "csb-gh-token"
  # Secret value is the actual github token, retrieved from env vars (secrets on pipeline)

  # DB-06 : Kubernetes GH Token Secret Creation
  if ! run_test "DB-06  : Kubernetes Image Secret Creation" "success" "kubectl create secret generic csb-gh-secret \
    --from-literal=csb-gh-token="${GH_TOKEN}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for image token...${RESET}"
    return 2
  fi
  
  # DB-07 : Kubernetes Check Secret - GH Token
  if ! run_test "DB-05  : Kubernetes Image Secret Check" "success" "kubectl get secret csb-gh-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for image token...${RESET}"
    return 2
  fi

  ###################################
  # Section 3: Helm Deployment Test #
  ###################################
  echo
  log_info "Section 3: Helm Deployment Tests..."

  # DB-08 : Helm Deployment Test
  if ! run_test "DB-08  : Helm Installation Test" "success" "helm upgrade \
  --install ${RELEASE_NAME} ${HELM_CHART_PATH} \
  --namespace ${CSB_NAMESPACE} \
  --set statefulset.image.uri=${GHCR_IMAGE} \
  --wait --timeout=5m > /tmp/helm_install_$$.log 2>&1"; then
    log_info "${RED}Failed to deploy helm chart...${RESET}"
    return 2
  fi

  # DB-09 : Helm Installation Check
  if ! run_test "DB-09  : Helm Installation Validation" "success" "helm list \
  -A -n ${CSB_NAMESPACE} | grep ${RELEASE_NAME}"; then
    log_info "${RED}Failed to validate helm chart deployment...${RESET}"
    return 2
  fi

  ###################################################
  # Section 4: Post Deployment Checks on Kubernetes #
  ###################################################
  echo
  log_info "Section 4: Post Deployment Checks on Kubernetes..."
  # Check if HBA config map exists
  # Check if network policy exists
  # Check if service exists
  # Check if statefulset exists
  # Check if POD exists with only 1 replica
  # Test connection to POD
  # Test connection to database
  # Test query on database (conninfo)
}

################
# Main program #
################

# Ensure teardown runs even if the script is interrupted or fails
trap teardown_environment EXIT

setup_environment
run_db_ci_tests
final_status=$?

if [ $final_status -eq 0 ]; then
  log_info "${GREEN}All CI validation tests passed successfully...${RESET}"
elif [ $final_status -eq 1 ]; then
  log_info "${RED}One or more CI validation tests failed...${RESET}"
elif [ $final_status -eq 2 ]; then
  log_info "${RED}Testing interrupted due to misconfiguration...${RESET}"
else
  log_info "${RED}Uknown error occurred during testing...${RESET}"
fi

# The 'trap' will handle the final teardown automatically on exit.
log_info "Script finished..."
