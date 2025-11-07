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
  local tc_name=$1
  shift
  local message="$@"
  echo "${BOLD}${BLUE}[TEST] $tc_name  $message... ${BOLD}${GREEN}[SUCCESS]${RESET}"
}

# Format failure message
log_failure() {
  local tc_name=$1
  shift
  local message="$@"
  echo "${BOLD}${BLUE}[TEST] $tc_name  $message... ${BOLD}${RED}[FAILURE]${RESET}"
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
      echo " ${BOLD}${RED}[FAILURE]${RESET}"
      result=1
    fi
  else
    # Command failed
    if [ "$expected_outcome" == "failure" ]; then
      echo " ${BOLD}${GREEN}[SUCCESS]${RESET}"
      result=0
    else
      echo " ${BOLD}${RED}[FAILURE]${RESET}"
      result=1
    fi
  fi
  return $result
}

# Evaluate results and log test case to stdout
eval_and_log_test_case() {
  local test_name=$1

  # The rest of the arguments form the command to run
  shift
  local condition="$@"
  echo -n "${BOLD}${BLUE}[TEST] $test_name..."
  
  # Execute the command, redirecting output to /dev/null to keep the report clean
  if $condition; then
    echo " ${BOLD}${GREEN}[SUCCESS]${RESET}"
    return 0
  else
    echo " ${BOLD}${RED}[FAILURE]${RESET}"
    return 1
  fi
}
