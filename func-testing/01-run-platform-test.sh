#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge Platform Configuration -  Validation Script
#
# This script automates the validation of the foundational Kubernetes platform
# configuration for the 'qa' environment. It performs the following steps:
#   1. Sets up the required resources (Namespace, RBAC) using Kustomize.
#   2. Runs a series of tests to verify each resource was created correctly.
#   3. Generates a report in the console with the status of each test case.
#   4. Tears down all created resources to clean up the environment.
#
# Usage: ./run_platform_tests.sh
# -----------------------------------------------------------------------------

# Global configuration
set -o pipefail # Exit on pipe failures
. ./set_test_env.sh

# Test configuration for QA environment
PLATFORM_OVERLAY_PATH="../platform-config/overlays/qa"
NAMESPACE="csb-qa"
ROLE_NAME="csb-app-deployer-role"
SA_NAME="csb-app-sa"
RB_NAME="qa-deployer-role-binding"

# Test runner function
run_test() {
  local test_name=$1

  # The rest of the arguments form the command to run
  shift
  local command_to_run="$@"

  echo -n "${BOLD}${BLUE}[TEST] $test_name..."
  
  # Execute the command, redirecting output to /dev/null to keep the report clean
  if eval "$command_to_run" > /dev/null 2>&1; then
    echo " ${BOLD}${GREEN}[SUCCESS]${RESET}"
    return 0
  else
    echo " ${BOLD}${RED}[FAILURE]${RESET}"
    return 1
  fi
}

# Setup function
setup_environment() {
  log_info "Setting up qa test environment..."
  if ! kubectl get nodes > /dev/null 2>&1; then
    log_info "${RED}Failed to connect to Kubernetes cluster. Aborting.${RESET}"
    exit 1
  fi
  log_info "Connected to Kubernetes cluster. Applying platform configuration..."

  if ! kubectl apply -k "$PLATFORM_OVERLAY_PATH" >/dev/null 2>&1; then
    log_info "${RED}Failed to apply platform configuration. Aborting.${RESET}"
    exit 1
  fi
  # Induce a pause for resources to be fully created
  sleep 5
  log_info "Kubernetes platform setup complete..."
}

# Validation function for all test cases
run_validation_tests() {
  log_info "Running platform validation tests..."
  local all_tests_passed=true

  # TC-P01: `kubectl` Connectivity Verification
  if ! run_test "TC-P01  :: Kubectl Connectivity" "kubectl cluster-info"; then
    all_tests_passed=false
  fi

  # TC-P02: Namespace Existence
  if ! run_test "TC-P02  :: Namespace '${NAMESPACE}' exists" "kubectl get namespace ${NAMESPACE}"; then
    all_tests_passed=false
  fi

  # TC-P03: RBAC Role Existence
  if ! run_test "TC-P03  :: Role '${ROLE_NAME}' exists" "kubectl get role ${ROLE_NAME} -n ${NAMESPACE}"; then
    all_tests_passed=false
  fi

  # TC-P04: ServiceAccount Existence
  if ! run_test "TC-P04  :: ServiceAccount '${SA_NAME}' exists" "kubectl get serviceaccount ${SA_NAME} -n ${NAMESPACE}"; then
    all_tests_passed=false
  fi

  # TC-P05: RBAC RoleBinding Validation
  # This test, requires jq executable to parse the JSON output.
  local get_rb_json="kubectl get rolebinding ${RB_NAME} -n ${NAMESPACE} -o json"
  local check_binding_command="${get_rb_json} | jq -e '
    (.roleRef.name == \"${ROLE_NAME}\") and 
    (.subjects[0].kind == \"ServiceAccount\") and 
    (.subjects[0].name == \"${SA_NAME}\")'"
  if ! run_test "TC-P05  :: RoleBinding '${RB_NAME}' links correctly" "${check_binding_command}"; then
    all_tests_passed=false
  fi

  if [ "$all_tests_passed" == true ]; then
    log_info "${GREEN}All platform validation tests passed!${RESET}"
  else
    log_info "${RED}One or more platform validation tests failed.${RESET}"
    # Continue to tear down the test resources; Ideally script should exit with error-code.
  fi
}

# Teardown function
teardown_environment() {
  log_info "Tearing down test environment..."
  if ! kubectl delete -k "$PLATFORM_OVERLAY_PATH"; then
    log_info "${RED}Failed to delete platform resources. Please clean up manually.${RESET}"
  fi
  log_info "Test environment teardown complete..."
}

################
# Main program #
################

# Ensure teardown runs even if the script is interrupted (e.g., with Ctrl+C)
# trap teardown_environment EXIT

# Run the stages in order
setup_environment
run_validation_tests

# The 'trap' will handle the final teardown automatically on exit.
log_info "Testing finished for platform configuration..."
