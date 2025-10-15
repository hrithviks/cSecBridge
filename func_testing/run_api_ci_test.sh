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
# Usage: ./run_api_ci_test.sh
# -----------------------------------------------------------------------------

# Global configuration
set -o pipefail # Exit on pipe failures

# Report styles
BOLD=$(tput bold)
BLUE=$(tput setaf 4)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
RED=$(tput setaf 1)
RESET=$(tput sgr0)

# Test configuration for QA environment
K_NAMESPACE="csb-qa"
K_SA_NAME="csb-app-sa"
K_ROLE_NAME="csb-app-deployer-role"

API_SERVICE_PATH="../api_service"
HELM_CHART_PATH="${API_SERVICE_PATH}/helm"
RELEASE_NAME="ci-qa-api"

# Logger function
log_info() {
  DT=`date "+%Y-%m-%d %H:%M:%S"`
  echo "${DT} :: ${BOLD}${BLUE}==> ${RESET}${BOLD}$1${RESET}"
}

# Test runner function
run_test() {
  local test_name=$1
  local expected_outcome=$2 # "success" or "failure"
  shift 2
  local command_to_run="$@"
  local result=0

  echo -n "${BOLD}${BLUE}[TEST] $test_name..."
  
  # Suppress command output for a clean report
  if eval "$command_to_run" > /dev/null 2>&1; then
    # Command succeeded
    if [ "$expected_outcome" == "success" ]; then
      echo " ${BOLD}${GREEN}[SUCCESS]${RESET}"
      result=0
    else
      echo " ${BOLD}${RED}[FAILURE]${RESET} (Expected failure, but it succeeded)"
      result=1
    fi
  else
    # Command failed
    if [ "$expected_outcome" == "failure" ]; then
      echo " ${BOLD}${GREEN}[SUCCESS]${RESET} (Correctly failed as expected)"
      result=0
    else
      echo " ${BOLD}${RED}[FAILURE]${RESET}"
      result=1
    fi
  fi
  return $result
}

# Environment setup function
setup_environment() {

  log_info "Verifying test environment configuration data..."
  # Environment variable for build section
  if [ -z "${GITHUB_USER}" ] || [ -z "${GITHUB_TOKEN}" ]; then
    log_info "${RED}Environment vars missing for the containerization section...${RESET}"
    exit 1
  fi

  # Environment variables for kubernetes secrets
  if [ -z "${CSB_API_AUTH_TOKEN}" ] || [ -z "${CSB_DB_PSWD}" ] || [ -z "${CSB_REDIS_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    exit 1
  fi

  # Environment variables for helm section
  # Postgres
  if [ -z "${CSB_API_AUTH_TOKEN}" ] || [ -z "${CSB_DB_PSWD}" ] || [ -z "${CSB_REDIS_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    exit 1
  fi


  # Platform configuration
  log_info "Verifying test platform..."
  if ! kubectl get namespace "$K_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Namespace '${K_NAMESPACE}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  if ! kubectl get serviceaccount "$K_SA_NAME" -n "$K_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: ServiceAccount '${K_SA_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  if ! kubectl get role "$K_ROLE_NAME" -n "$K_NAMESPACE" > /dev/null 2>&1; then
    log_info "${RED}Prerequisites missing: Role '${K_ROLE_NAME}' does not exist...${RESET}"
    log_info "${RED}Please apply platform config before running tests...${RESET}"
    exit 1
  fi

  # Backend services configuration
  log_info "Verifying backend services..."

  # Kubernetes configuration (pre-requisite for helm deployment)
  log_info "Verifying Kubernetes configuration values..."

  # Helm configuration
  log_info "Verifying Helm configuration values..."

  log_info "Test environment is ready..."
}

teardown_environment() {
  log_info "Tearing down test resources..."

  # Use --ignore-not-found to prevent errors during cleanup
  helm uninstall $RELEASE_NAME -n $NAMESPACE --ignore-not-found=true > /dev/null 2>&1
  
  # Restore any files that were modified during the tests
  git restore "${API_SERVICE_PATH}/source/app/routes.py"
  git restore "${API_SERVICE_PATH}/Dockerfile"
  git restore "${API_SERVICE_PATH}/helm/templates/deployment.yaml"
  
  log_info "Teardown complete."
}

run_ci_tests() {
  log_info "Simulating CI/CD Process Validation Tests..."
  local overall_status=0

  #############################################
  # Section 1: Code Quality Check and Linting #
  #############################################
  # CI-01: Test lint success
  echo
  log_info "Section 1: Linting Tests..."
  if ! run_test "CI-01  : Python Linting" "success" "flake8 ${API_SERVICE_PATH}/source/"; then
    overall_status=1
  fi
  
  # CI-02: Test lint failure - by introducing an unused import
  echo "import os" >> "${API_SERVICE_PATH}/source/app/routes.py"
  if ! run_test "CI-02  : Python Linting (Failure)" "failure" "flake8 ${API_SERVICE_PATH}/source/"; then
    overall_status=1
  fi
  git restore "${API_SERVICE_PATH}/source/app/routes.py" # Clean up

  ###############################
  # Section 2: Containerization #
  ###############################
  echo
  log_info "Section 2: Containerization Tests..."

  # Local Env Vars for Testing
  local DOCKERFILE_PATH=${API_SERVICE_PATH}
  local IMAGE_NAME="csb-api-qa"
  local IMAGE_TAG="latest"
  local GHCR_IMAGE="ghcr.io/${GITHUB_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

  # CI-03: Test build success
  if ! run_test "CI-03  : Docker Image Build" "success" "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKERFILE_PATH}"; then
    overall_status=1
  fi

  # CI-04: Test docker login(Section A) and push to github container registry(Section B)
  if ! run_test "CI-04A : GitHub Container Registry Login" "success" "docker login ghcr.io -u ${GITHUB_USER} -p ${GITHUB_TOKEN}"; then
    overall_status=1
  else
    # If login successful, tag and test push
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$GHCR_IMAGE" 2>/dev/null
    if ! run_test "CI-04B : Image Push to GitHub Container Registry" "success" "docker push ${GHCR_IMAGE}"; then
      overall_status=1
    fi
  fi

  # CI-05: Test build failure - by introducing a syntax error in the Dockerfile
  sed -i.bak 's/COPY/COPPY/' "${API_SERVICE_PATH}/Dockerfile"
  if ! run_test "CI-04  : Docker Image Build (Failure)" "failure" "docker build -t csb-api-qa-fail:latest ${API_SERVICE_PATH}"; then
    overall_status=1
  fi

  # Clean up after test
  git restore "${API_SERVICE_PATH}/Dockerfile"
  if [ $? -eq 0 ]; then
    rm -f "${API_SERVICE_PATH}/Dockerfile.bak"
  fi
  
  ##############################################
  # Section 3: Kubernetes Pre-Deployment Tests #
  ##############################################
  echo
  log_info "Section 3: Kubernetes Pre-Deployment Tests"
  return 2

  # CI-08: Check if all environment variables (including secrets are defined)

  # CI-09: Create and check kubernetes secrets (pre-requisite for helm deployment)

  ######################################
  # Section 4: Helm Installation Tests #
  ######################################
  log_info "Section 4: Helm Installation Tests"

  # We test that Helm can render and apply, but the pod will fail (tested in CI-07).
  run_test "[TEST] CI-05: Successful Helm Deployment Apply" "success" "helm install ${RELEASE_NAME} ${HELM_CHART_PATH} -n ${NAMESPACE} --set config.postgresHost=fake-host --set config.redisHost=fake-host" || overall_status=1
  helm uninstall $RELEASE_NAME -n $NAMESPACE > /dev/null 2>&1 # Clean up immediately

  # Test template failure
  echo "{{ if }}" >> "${API_SERVICE_PATH}/helm/templates/deployment.yaml" # Invalid template syntax
  run_test "[TEST] CI-06: Helm Deployment Failure (Template Error)" "failure" "helm install ${RELEASE_NAME} ${HELM_CHART_PATH} -n ${NAMESPACE}" || overall_status=1
  git restore "${API_SERVICE_PATH}/helm/templates/deployment.yaml" # Clean up

  # Test runtime failure
  log_info "[TEST] CI-07: Post-Deployment Pod Failure (Runtime Config)..."
  helm install $RELEASE_NAME $HELM_CHART_PATH -n $NAMESPACE --set config.postgresHost=non-existent-db-host > /dev/null 2>&1
  echo "    Waiting for pod to enter a crash loop..."
  sleep 15 # Give the pod time to start and fail
  if kubectl get pod -l app.kubernetes.io/instance=${RELEASE_NAME} -n $NAMESPACE -o json | jq -e '.items[0].status.containerStatuses[0].state.waiting.reason == "CrashLoopBackOff"'; then
    echo "    ${BOLD}${GREEN}[SUCCESS]${RESET} (Pod correctly entered CrashLoopBackOff)"
  else
    echo "    ${BOLD}${RED}[FAILURE]${RESET} (Pod did not crash as expected)"
    overall_status=1
  fi
  helm uninstall $RELEASE_NAME -n $NAMESPACE > /dev/null 2>&1 # Clean up

  ########################################
  # Section 5: Kubernetes Resource Tests #
  ########################################
  log_info "Section 5: Kubernetes Resources Tests, post deployment"
  log_info "Installing Helm charts for qa instance..."
  return $overall_status
}

################
# Main program #
################

# NOTE: To inspect created resources after a test run, comment out the teardown section in "trap"

# Ensures teardown runs even if the script is interrupted (e.g., with Ctrl+C)
trap teardown_environment EXIT

setup_environment
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