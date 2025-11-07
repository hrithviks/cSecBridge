#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge API Service - CI Process Validation Script
#
# This script automates the validation of the core CI/CD mechanics for the
# api-service, including linting, containerization, and deployment. It is
# designed to be run locally to test the automation itself.
#
# It executes the following stages:
#   1. Verifies that the prerequisite Kubernetes environment exists.
#   2. Runs linting tests (both success and failure cases).
#   3. Runs Docker build tests (both success and failure cases).
#   4. Runs Helm deployment tests (success, template error, runtime error).
#   5. Generates a report in the console.
#   6. Tears down all test-specific resources created by the script.
#
# Usage: ./run_api_ci_tests.sh
# -----------------------------------------------------------------------------

# Global configuration
set -o pipefail # Exit on pipe failures
. ./set_test_env.sh

# Test configuration for QA environment
CSB_NAMESPACE="csb-qa"
CSB_SA_NAME="csb-app-sa"
CSB_ROLE_NAME="csb-app-deployer-role"
CSB_API_SERVICE_PATH="../api-service"
CSB_API_HELM_CHART_PATH="${CSB_API_SERVICE_PATH}/helm"
CSB_API_RELEASE_NAME="csb-api-rel"
CSB_DB_SERVICE="csb-postgres-service"
CSB_REDIS_SERVICE="csb-redis-service"

# Environment setup function
validate_environment() {

  log_info "Verifying test environment configuration data..."
  # Environment variable for build section
  if [ -z "${GH_USER}" ] || [ -z "${GH_TOKEN}" ]; then
    log_info "${RED}Environment vars missing for the containerization section...${RESET}"
    exit 1
  fi

  # Environment variables for kubernetes secrets
  if [ -z "${CSB_API_AUTH_TOKEN}" ] || [ -z "${CSB_POSTGRES_PSWD}" ] || [ -z "${CSB_REDIS_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    exit 1
  fi

  # Environment variables for build database objects
  if [ -z $CSB_POSTGRES_APP_USER ] \
    || [ -z $CSB_POSTGRES_APP_PSWD ]; then
    log_info "${RED}Environment vars missing for configuration postgres database objects...${RESET}"
  fi

  # Platform configuration
  log_info "Verifying test platform..."
  if ! kubectl get namespace "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Namespace '${CSB_NAMESPACE}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  if ! kubectl get serviceaccount "$CSB_SA_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: ServiceAccount '${CSB_SA_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  if ! kubectl get role "$CSB_ROLE_NAME" -n "$CSB_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Role '${CSB_ROLE_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  # Backend services configuration
  log_info "Verifying backend services..."

  # Check postgres service
  if ! kubectl get service $CSB_DB_SERVICE -n $CSB_NAMESPACE | grep '5432/TCP' > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Service '${CSB_DB_SERVICE}' not configured for port 5432...${RESET}"
  fi

  # Check redis service
  if ! kubectl get service $CSB_REDIS_SERVICE -n $CSB_NAMESPACE | grep '6379/TCP' > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Service '${CSB_REDIS_SERVICE}' not configured for port 6379...${RESET}"
  fi

  log_info "Test environment is ready..."
}

teardown_environment() {
  log_info "Tearing down test resources..."

  # Use --ignore-not-found to prevent errors during cleanup
  helm uninstall $RELEASE_NAME -n $NAMESPACE --ignore-not-found=true > /dev/null 2>&1
  
  # Restore any files that were modified during the tests
  git restore "${CSB_API_SERVICE_PATH}/source/app/routes.py"
  git restore "${CSB_API_SERVICE_PATH}/Dockerfile"
  git restore "${CSB_API_SERVICE_PATH}/helm/templates/deployment.yaml"
  
  log_info "Teardown complete."
}

run_ci_tests() {
  log_info "Simulating CI/CD Process Validation Tests..."
  local overall_status=0

  #############################################
  # Section 1: Code Quality Check and Linting #
  #############################################

  # CI-01: Test lint success
  log_info "Section 1: Linting Tests..."
  if ! run_test "CI-01  : Python Linting" "success" "flake8 ${CSB_API_SERVICE_PATH}/src/"; then
    overall_status=1
  fi
  
  # CI-02: Test lint failure - by introducing an unused import
  echo "import os" >> "${CSB_API_SERVICE_PATH}/src/logging_config.py"
  if ! run_test "CI-02  : Python Linting (Failure)" "failure" "flake8 ${CSB_API_SERVICE_PATH}/source/"; then
    overall_status=1
  fi
  git restore "${CSB_API_SERVICE_PATH}/src/logging_config.py" # Clean up

  ###############################
  # Section 2: Containerization #
  ###############################
  log_info "Section 2: Containerization Tests..."

  # Local Env Vars for Testing
  local DOCKERFILE_PATH=${CSB_API_SERVICE_PATH}
  local IMAGE_NAME="csb-api-qa"
  local IMAGE_TAG="latest"
  local GHCR_IMAGE="ghcr.io/${GH_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

  # CI-03: Test build success
  if ! run_test "CI-03  : Docker Image Build" "success" "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKERFILE_PATH}"; then
    overall_status=1
  fi

  # CI-04: Test docker login(Section A) and push to github container registry(Section B)
  if ! run_test "CI-04A : GitHub Container Registry Login" "success" "docker login ghcr.io -u ${GH_USER} -p ${GH_TOKEN}"; then
    overall_status=1
  else
    # If login successful, tag and test push
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$GHCR_IMAGE" 2>/dev/null
    if ! run_test "CI-04B : Image Push to GitHub Container Registry" "success" "docker push ${GHCR_IMAGE}"; then
      overall_status=1
    fi
  fi

  # CI-05: Test build failure - by introducing a syntax error in the Dockerfile
  sed -i.bak 's/COPY/COPPY/' "${CSB_API_SERVICE_PATH}/Dockerfile"
  if ! run_test "CI-05  : Docker Image Build (Failure)" "failure" "docker build -t csb-api-qa-fail:latest ${CSB_API_SERVICE_PATH}"; then
    overall_status=1
  fi

  # Clean up after test
  git restore "${CSB_API_SERVICE_PATH}/Dockerfile"
  if [ $? -eq 0 ]; then
    rm -f "${CSB_API_SERVICE_PATH}/Dockerfile.bak"
  fi
  
  ###############################
  # Section 3: Kubernetes Tests #
  ###############################
  log_info "Section 3: Kubernetes Tests..."

  # This command mimics a CI/CD pipeline securely creating secrets for db-user, redis-user and api-token
  # Secret names and keys are hardcoded in the helm's values.yaml file.
  # Secret values are passed as environment variables (secrets on a pipeline)
  # CI-06 : Create Kubernetes Secret for Backend Database User
  if ! run_test "CI-06  :: Kubernetes DB Secret Creation" "success" "kubectl create secret generic csb-postgres-api-user-secret \
    --from-literal=csb-api-user-pswd="${CSB_POSTGRES_PSWD}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for admin password...${RESET}"
    return 127
  fi
  
  # CI-07 : Check Kubernetes Secret for Backend Database User
  if ! run_test "CI-07  :: Kubernetes DB Secret Check" "success" "kubectl get secret csb-postgres-api-user-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for admin password...${RESET}"
    return 127
  fi

  # CI-08 : Create Kubernetes Secret for Backend Redis User
  if ! run_test "CI-08  :: Kubernetes Redis Secret Creation" "success" "kubectl create secret generic csb-redis-user-secret \
    --from-literal=csb-api-redis-pswd="${CSB_REDIS_PSWD}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for admin password...${RESET}"
    return 127
  fi
  
  # CI-09 : Check Kubernetes Secret for Backend Redis User
  if ! run_test "CI-09  :: Kubernetes Redis Secret Check" "success" "kubectl get secret csb-redis-user-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for admin password...${RESET}"
    return 127
  fi

  # CI-10 : Create Kubernetes Secret for API Token
  if ! run_test "CI-10  :: Kubernetes API Token Secret Creation" "success" "kubectl create secret generic csb-api-token-secret \
    --from-literal=csb-api-token="${CSB_API_AUTH_TOKEN}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for admin password...${RESET}"
    return 127
  fi
  
  # CI-11 : Check Kubernetes Secret for Backend Redis User
  if ! run_test "CI-11  :: Kubernetes API Token Secret Check" "success" "kubectl get secret csb-api-token-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for admin password...${RESET}"
    return 127
  fi

  # This command mimics a CI/CD pipeline securely creating the secret for github token
  # Secret name is "csb-gh-secret"
  # Secret type is a Docker registry secret, comprising of username, access token and server name

  # CI-08 : Kubernetes GH Token Secret Creation
  if ! run_test "CI-12  :: Kubernetes Image Secret Creation" "success" "kubectl create secret docker-registry csb-gh-secret \
    --docker-server="ghcr.io" \
    --docker-username="${GH_USER}" \
    --docker-password="${GH_TOKEN}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for image token...${RESET}"
    return 127
  fi
  
  # CI-09 : Kubernetes Check Secret - GH Token
  if ! run_test "CI-13  :: Kubernetes Image Secret Check" "success" "kubectl get secret csb-gh-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for image token...${RESET}"
    return 127
  fi

  exit 0

  ######################################
  # Section 4: Helm Installation Tests #
  ######################################
  log_info "Section 4: Helm Installation Tests"


  ########################################
  # Section 5: Kubernetes Resource Tests #
  ########################################
  log_info "Section 5: Kubernetes Resources Tests, post deployment"


  return $overall_status
}

################
# Main program #
################

# NOTE: To inspect created resources after a test run, comment out the teardown section in "trap"

# Ensures teardown runs even if the script is interrupted (e.g., with Ctrl+C)
# trap teardown_environment EXIT

validate_environment
run_ci_tests
final_status=$?

echo
if [ $final_status -eq 0 ]; then
  log_info "${GREEN}All CI validation tests passed successfully!${RESET}"
elif [ $final_status -eq 1 ]; then
  log_info "${RED}One or more CI validation tests failed.${RESET}"
else
  log_info "${RED}Testing interrupted due to misconfiguration.${RESET}"
fi

# The 'trap' will handle the final teardown automatically on exit.
log_info "Script finished."
exit $final_status