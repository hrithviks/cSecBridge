#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge - Set Test Environment Variables and Functions
#
# This script defines all the reusable environment vars and functions across all
# the test scripts.
# -----------------------------------------------------------------------------

# Report styles
export BOLD=$(tput bold)
export BLUE=$(tput setaf 4)
export GREEN=$(tput setaf 2)
export YELLOW=$(tput setaf 3)
export RED=$(tput setaf 1)
export RESET=$(tput sgr0)

# Logger function
log_info() {
  DT=`date "+%Y-%m-%d %H:%M:%S"`
  echo "${DT} :: ${BOLD}${BLUE}==> ${RESET}${BOLD}$1${RESET}"
}

# Format success message
log_success() {
  echo "    ${BOLD}${GREEN}[SUCCESS]${RESET} $1"
}

# Format failure message
log_failure() {
  echo "    ${BOLD}${RED}[FAILURE]${RESET} $1"
  exit 1
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

# Set environment variables
# export CSB_API_AUTH_TOKEN="dummy_test_non_sensitive_token_value"

# Postgres
# export CSB_POSTGRES_HOST=
# export CSB_POSTGRES_DB="csb_db"
# export CSB_POSTGRES_PORT=2345
# export CSB_POSTGRES_USER="CSB_API_USER"
# export CSB_POSTGRES_PSWD="dummy_password_for_db"
# export CSB_POSTGRES_MAX_CONN=5

# Redis
# export CSB_REDIS_HOST=
# export CSB_REDIS_PORT=2367
# export CSB_REDIS_PSWD=