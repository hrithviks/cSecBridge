#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge CleanUp Script for Test Resources
#
# This script removes of all test resources explicitly
#
# It executes the following stages:
#   1. Uninstall helm charts.
#   2. Delete persistent volume claims.
#   3. Delete namespaces.
#   4. Delete local docker images.
#   5. Unset all sensitive environment variables for testing.
#
# Usage: ./run_cleanup.sh
# -----------------------------------------------------------------------------

# Global configuration
set -o pipefail # Exit on pipe failures
. ./set_test_env.sh

# Test Configuration
CSB_NAMESPACE="csb-qa"

# Uninstall helm chart
cleanup_status=0
log_info "Uninstalling helm charts..."
for REL in `helm list -n ${CSB_NAMESPACE} | grep -v NAME | awk -F" " '{print $1}'`; do
  log_info "Uninstalling $REL..."
  helm uninstall $REL -n $CSB_NAMESPACE --ignore-not-found=true > /dev/null 2>&1

  if [ $? -ne 0 ]; then
    log_info "${RED}Failed to uninstall helm chart $REL...${RESET}"
    log_info "${RED}Please clean up manually...${RESET}"
    cleanup_status=1
  else
    log_info "${GREEN}Helm chart $REL uninstalled successfully...${RESET}"
    sleep 2
  fi
done
sleep 5

# Optional - Delete persistent volume claim
log_info "Deleting persistent volume claims..."
for PVC in `kubectl get pvc -n ${CSB_NAMESPACE} | grep -v NAME | awk -F" " '{print $1}'`; do
  log_info "Deleting $PVC..."
  kubectl delete pvc $PVC -n $CSB_NAMESPACE > /dev/null 2>&1

  if [ $? -ne 0 ]; then
    log_info "${RED}Failed to delete persistent volume claim $PVC...${RESET}"
    log_info "${RED}Please clean up manually...${RESET}"
    cleanup_status=1
  else
    log_info "${GREEN}Persistent volume claim $PVC deleted successfully...${RESET}"
  fi
done
sleep 5

# Optional - Delete namespaces
log_info "Deleting namespaces..."
log_info "Deleting $CSB_NAMESPACE..."
kubectl delete namespace $CSB_NAMESPACE --cascade > /dev/null 2>&1
if [ $? -ne 0 ]; then
  log_info "${RED}Failed to delete namespace ${CSB_NAMESPACE}...${RESET}"
  log_info "${RED}Please clean up manually...${RESET}"
  cleanup_status=1
else
  log_info "${GREEN}Namespace $CSB_NAMESPACE deleted successfully...${RESET}"
fi
sleep 5

exit $cleanup_status