#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge Redis Service - CI Process Validation Script
#
# This script automates the validation of the build and deployment mechanics for
# the redis service. It is designed to be run locally to test the
# automation before it's integrated into a full CI/CD pipeline.
#
# It executes the following stages:
#   1. Checks all env configuration for runtime and kubernetes resources.
#   2. Builds the Redis Docker image.
#   3. Securely creates the redis password secret in the cluster
#   4. Deploys the redis_service Helm chart.
#   5. Verifies that the StatefulSet becomes ready.
#   6. Generates a report and tears down the entire test env for redis.
#
# Usage: ./run_redis_tests.sh
# -----------------------------------------------------------------------------

# Global configuration
set -e
set -o pipefail # Exit on pipe failures
. ./set_test_env.sh

log_info "Starting Redis testing"

# Test Configuration
CSB_NAMESPACE="csb-qa"
CSB_SA_NAME="csb-app-sa"
CSB_ROLE_NAME="csb-app-deployer-role"
CSB_REDIS_PATH="../redis/"
CSB_REDIS_HELM_CHART_PATH="${CSB_REDIS_PATH}/helm"
CSB_REDIS_RELEASE_NAME="csb-redis-rel"

# Function to validate kubernetes platform configuration
validate_platform_config() {

  local platform_val_status=0
  # Check environment variables
  # This test uses the same credentials for all Github registry operations.
  log_info "Verifying github environment variables..."
  if [ -z ${GH_USER} ] || [ -z ${GH_TOKEN} ]; then
    log_info "${RED}Environment vars missing for the containerization section...${RESET}"
    platform_val_status=1
  fi

  # Environment variables for kubernetes secrets
  log_info "Verifying redis environment variables..."
  if [ -z "${CSB_REDIS_PSWD}" ]; then
    log_info "${RED}Environment vars missing for the kubernetes secrets section...${RESET}"
    platform_val_status=1
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

# Function to perform the ci-cd tests for redis service.
run_redis_ci_cd_tests() {

  local overall_status=0
  log_info "Running Redis Service CI-CD Validation..."
  
  ###############################
  # Section 1: Containerization #
  ###############################
  log_info "Section 1: Containerization Tests..."

  # Local Env Vars for Testing
  local IMAGE_NAME="csb-redis-qa"
  local IMAGE_TAG="latest"
  local GHCR_IMAGE="ghcr.io/${GH_USER}/${IMAGE_NAME}:${IMAGE_TAG}"

  # RD-01: Test build success
  if ! run_test "RD-01  :: Docker Image Build" "success" "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ${CSB_REDIS_PATH}"; then
    return 2
  fi

  # RD-02: Test docker login(Section A) and push to github container registry(Section B)
  if ! run_test "RD-02A :: GitHub Container Registry Login" "success" "docker login ghcr.io -u ${GH_USER} -p ${GH_TOKEN}"; then
    overall_status=1
  else
    # If login successful, tag and test push
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "$GHCR_IMAGE" 2>/dev/null
    if ! run_test "RD-02B :: Image Push to GitHub Container Registry" "success" "docker push ${GHCR_IMAGE}"; then
      overall_status=1
    fi
  fi

  # RD-03: Test build failure - by introducing a syntax error in the Dockerfile
  sed -i.bak 's/COPY/COPPY/' "${CSB_REDIS_PATH}/Dockerfile"
  if ! run_test "RD-03  :: Docker Image Build (Failure)" "failure" "docker build -t csb-RD-qa-fail:latest ${CSB_REDIS_PATH}"; then
    overall_status=1
  fi

  # Clean up after test
  git restore "${CSB_REDIS_PATH}/Dockerfile"
  if [ $? -eq 0 ]; then
    rm -f "${CSB_REDIS_PATH}/Dockerfile.bak"
  fi

  ###############################
  # Section 2: Kubernetes Tests #
  ###############################
  log_info "Section 2: Kubernetes Tests..."

  # This command mimics a CI/CD pipeline securely creating the secret for redis
  # Secret name is "redis-secret"
  # Secret key is "csb-redis-password"
  # Secret value is the actual password, retrieved from env vars (secrets on pipeline)

  # RD-04 : Kubernetes Redis Secret Creation
  if ! run_test "RD-04  :: Kubernetes Redis Secret Creation" "success" "kubectl create secret generic redis-secret \
    --from-literal=csb-redis-password="${CSB_REDIS_PSWD}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for redis...${RESET}"
    return 127
  fi
  
  # RD-05 : Kubernetes Check Secret - Redis Password
  if ! run_test "RD-05  :: Kubernetes Redis Secret Check" "success" "kubectl get secret redis-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for redis...${RESET}"
    return 127
  fi

  # This command mimics a CI/CD pipeline securely creating the secret for github token
  # Secret name is "csb-gh-secret"
  # Secret type is a Docker registry secret, comprising of username, access token and server name

  # RD-06 : Kubernetes GH Token Secret Creation
  if ! run_test "RD-06  :: Kubernetes Image Secret Creation" "success" "kubectl create secret docker-registry csb-gh-secret \
    --docker-server="ghcr.io" \
    --docker-username="${GH_USER}" \
    --docker-password="${GH_TOKEN}" \
    --namespace=${CSB_NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f - > /dev/null 2>&1"; then
    log_info "${RED}Failed to create kubernetes secret for image token...${RESET}"
    return 127
  fi
  
  # RD-07 : Kubernetes Check Secret - GH Token
  if ! run_test "RD-07  :: Kubernetes Image Secret Check" "success" "kubectl get secret csb-gh-secret -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to get kubernetes secret for image token...${RESET}"
    return 127
  fi

  ###################################
  # Section 3: Helm Deployment Test #
  ###################################
  log_info "Section 3: Helm Deployment Tests..."

  # RD-08 : Helm Deployment Test for Redis
  if ! run_test "RD-08  :: Helm Installation Test" "success" "helm upgrade \
  --install ${CSB_REDIS_RELEASE_NAME} ${CSB_REDIS_HELM_CHART_PATH} \
  --namespace ${CSB_NAMESPACE} \
  --set statefulset.image.uri=${GHCR_IMAGE} \
  --wait --timeout=5m > /tmp/helm_install_$$.log 2>&1"; then
    log_info "${RED}Failed to deploy helm chart...${RESET}"
    return 127
  fi
  sleep 5

  # RD-09 : Helm Installation Check
  if ! run_test "RD-09  :: Helm Installation Validation" "success" "helm list \
  -A -n ${CSB_NAMESPACE} | grep ${CSB_REDIS_RELEASE_NAME}"; then
    log_info "${RED}Failed to validate helm chart deployment...${RESET}"
    return 127
  fi

  ###################################################
  # Section 4: Post Deployment Checks on Kubernetes #
  ###################################################
  log_info "Section 4: Post Deployment Checks on Kubernetes..."

  # Local variables for the section
  local REDIS_CONFIGMAP="csb-redis-service-config"
  local REDIS_NETWORK_POLICY="csb-redis-service"
  local REDIS_SERVICE_NAME="csb-redis-service"
  local REDIS_VOL_TEMPLATE="redis-data"
  local REDIS_STATEFULSET="csb-redis-service"

  # RD-10 : Check if HBA ConfigMap Exists
  if ! run_test "RD-10  :: Config Map Validation for redis.conf" "success" "kubectl \
  get configmap ${REDIS_CONFIGMAP} -n ${CSB_NAMESPACE}"; then
    log_info "${RED}Failed to validate the redis configmap...${RESET}"
    overall_status=1
  fi

  # RD-11 : Check if Network Policy Exists
  # Note : This is a simple test, validating the existence of the network policy.
  #        Parse the response of operation using json objects, 
  #        to perform more advanced validations for specific networking rules.
  if ! run_test "RD-11  :: Redis Network Policy Validation" "success" "kubectl \
  get networkpolicy ${REDIS_NETWORK_POLICY} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the Network Policy...${RESET}"
    overall_status=1
  fi

  # RD-12 : Check if the ClusterIP Service Exists
  if ! run_test "RD-12  :: Redis ClusterIP Service Validation" "success" "kubectl \
  get service ${REDIS_SERVICE_NAME} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the ClusterIP Service...${RESET}"
    overall_status=1
  fi

  # RD-13 : Check if the StatefulSet is Ready
  # Note: This is a simple test, testing the existence of the statefulset.
  #       Parse the response of the operation using json objects, to 
  #       perform more advanced validations for specific statefulset properties.
  if ! run_test "RD-13  :: Redis StatefulSet Validation" "success" "kubectl \
  get statefulset ${REDIS_STATEFULSET} -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the StatefulSet...${RESET}"
    overall_status=1
  fi

  # RD-14 : Check if the Persistent Volume Claim Exists
  if ! run_test "RD-14  :: Redis Persistent Volume Claim Validation" "success" "kubectl \
  get pvc "${REDIS_VOL_TEMPLATE}-$REDIS_STATEFULSET-0" -n ${CSB_NAMESPACE} > /dev/null 2>&1"; then
    log_info "${RED}Failed to validate the Persistent Volume Claim...${RESET}"
    overall_status=1
  fi

  # RD-15 : Check if the POD is Running
  # Note: This is a very basic check for the POD status for Redis service.
  #       Additional checks to be added for the pod configuration by 
  #       parsing the output in a json format for more advanced validations.  
  if [ `kubectl get pod -n ${CSB_NAMESPACE} | grep ${REDIS_STATEFULSET} | wc -l` -ne 0 ]; then
    if ! run_test "RD-15  :: Redis POD Validation" "success" "kubectl \
    get pod -n ${CSB_NAMESPACE} | grep ${REDIS_STATEFULSET}-0 | grep Running > /dev/null 2>&1"; then
      log_info "${RED}Failed to validate the POD status...${RESET}"
      overall_status=1
    fi
  else
    log_info "${RED}Failed to validate the required POD Replica (1)...${RESET}"
    overall_status=1
  fi

  #######################################
  # Section 5: Redis Service Validation #
  #######################################
  log_info "Section 5: Redis Service Tests..."

  local redis_pod_name="${REDIS_STATEFULSET}-0"
  local redis_pod_exec_cmd="kubectl exec -n ${CSB_NAMESPACE} ${redis_pod_name}"
  local redis_cli_cmd="redis-cli -h localhost -p 6379"
  local redis_cmd_result=""
  local redis_test_case=""
  local eval_result=""

  # Local function to evaluate the evaluation result and set the overall status
  # The local variables will contain values corresponding the test case.
  # This will call the library function to log the test case result.
  check_and_set_overall_status() {
    if ! eval_and_log_test_case "$redis_test_case" "$eval_result"; then
      overall_status=1
    fi
  }

  # RD-16 : Test POD Service Status
  # Check the ready prob of redis service pod to ensure it is accepting connections
  if ! run_test "RD-16  :: Redis Service Validation" "success" "kubectl \
  wait --for=condition=Ready pod/${redis_pod_name} -n ${CSB_NAMESPACE} \
  --timeout=1m > /dev/null 2>&1"; then
    log_info "${RED}Service validation failed for Redis...${RESET}"
    return 127
  fi

  # RD-17 : Test Unauthenticated connection to redis
  # The current pod configuration only allows authenticated access
  redis_test_case='RD-17  :: Redis Authentication Enforcement (Failure Scenario)'
  redis_cmd_result=$($redis_pod_exec_cmd -- env REDISCLI_AUTH="" $redis_cli_cmd ping 2>&1)
  eval_result=$(([[ ${redis_cmd_result} == *NOAUTH* || ${redis_cmd_result} == *WRONGPASS* ]]) && echo 'True' || echo 'False')
  check_and_set_overall_status
  
  # RD-18 : Test Authenticated connection to redis
  redis_test_case='RD-18  :: Redis Authentication Enforcement (Success Scenario)'
  redis_cmd_result=$(${redis_pod_exec_cmd} \
  -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} ping 2>&1)
  eval_result=$([[ ${redis_cmd_result} == *PONG* ]] && echo 'True' || echo 'False')
  check_and_set_overall_status

  # RD-19 : AOF Enablement for data persistence
  redis_test_case='RD-19  :: Redis AOF Enablement'
  redis_cmd_result=$(${redis_pod_exec_cmd} \
  -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} CONFIG GET appendonly 2>&1)
  eval_result=$(([[ ${redis_cmd_result} == *appendonly* || ${redis_cmd_result} == *yes* ]]) && echo 'True' || echo 'False')
  check_and_set_overall_status

  ################################
  # Section 6: Redis Cache Tests #
  ################################
  log_info "Section 6: Redis Cache Tests..."

  local test_cache_key="csb_test:cache:key"
  local test_cache_value="csb_test_cache_12345"

  # RD-20 : Update cache on the redis server
  redis_test_case="RD-20  :: Redis Cache Update"
  redis_cmd_result=$(${redis_pod_exec_cmd} \
  -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} \
  SET ${test_cache_key} ${test_cache_value} 2>&1)
  eval_result=$([[ ${redis_cmd_result} == *OK* ]]  && echo 'True' || echo 'False')
  check_and_set_overall_status

  # RD-21 : Get cache from the redis server
  redis_test_case="RD-21  :: Redis Cache Read"
  redis_cmd_result=$(${redis_pod_exec_cmd} \
  -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} GET ${test_cache_key} 2>&1)
  eval_result=$([[ ${redis_cmd_result} == ${test_cache_value} ]]  && echo 'True' || echo 'False')
  check_and_set_overall_status

  # RD-22 : Check TTL setting for the cache
  redis_test_case="RD-22  :: Redis Cache Invalidation (TTL Expiry)"
  ${redis_pod_exec_cmd} -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} \
  SET ${test_cache_key} ${test_cache_value} EX 1 > /dev/null 2>&1
  sleep 3
  redis_cmd_result=$(${redis_pod_exec_cmd} -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} \
  GET ${test_cache_key} 2>&1)
  eval_result=$([[ -z ${redis_cmd_result} ]] && echo 'True' || echo 'False')
  check_and_set_overall_status

  ################################
  # Section 7: Redis Queue Tests #
  ################################
  log_info "Section 7: Redis Queue Tests..."

  local test_queue_key="csb:worker_queue:payload"
  local test_queue_value="{\"id\": \"2e2r3t3t\", \"data\": \"test_data\"}"

  # RD-23 : Add item to the queue (using LPUSH)
  redis_test_case='RD-23  :: Redis Queue Update'
  redis_cmd_result=$(${redis_pod_exec_cmd} -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} \
  LPUSH "${test_queue_key}" "${test_queue_value}" 2>&1)
  eval_result=$([[ ${redis_cmd_result} -eq 1 ]] && echo 'True' || echo 'False')
  check_and_set_overall_status

  # RD-24 : Retrieve and delete item from the queue (using RPOP)
  redis_test_case="RD-24  :: Redis Queue Read"
  redis_cmd_result=$(${redis_pod_exec_cmd} -- env REDISCLI_AUTH=${CSB_REDIS_PSWD} ${redis_cli_cmd} \
  RPOP "${test_queue_key}" 2>&1)
  eval_result=$([[ ${redis_cmd_result} == ${test_queue_value} ]] && echo 'True' || echo 'False')
  check_and_set_overall_status

  # Return overall test status
  return $overall_status
}

teardown_environment() {
  local teardown_status=0
  local REDIS_VOL_TEMPLATE="redis-data"
  local REDIS_STATEFULSET="redis-service"
  log_info "Tearing down isolated test environment: ${CSB_NAMESPACE}"

  # Uninstall helm chart
  log_info "Uninstalling Helm chart $CSB_REDIS_RELEASE_NAME..."
  if ! helm uninstall $CSB_REDIS_RELEASE_NAME -n $CSB_NAMESPACE --ignore-not-found=true > /dev/null 2>&1; then
    log_info "${RED}Failed to uninstall helm chart $CSB_REDIS_RELEASE_NAME...${RESET}"
    teardown_status=1
  fi
  sleep 5

  # Delete persistent volume claim - if test data is no more required.
  log_info "Deleting persistent volume claim..."
  if ! kubectl delete pvc "${REDIS_VOL_TEMPLATE}-$REDIS_STATEFULSET-0" -n ${CSB_NAMESPACE} > /dev/null 2>&1; then
    log_info "${RED}Failed to delete persistent volume claim...${RESET}"
    teardown_status=1
  fi
  sleep 5

  # Optional Step -Deleting the namespace automatically garbage collects all resources within it.
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

if run_redis_ci_cd_tests; then
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
