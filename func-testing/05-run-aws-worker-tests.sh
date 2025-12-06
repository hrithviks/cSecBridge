#!/bin/bash

# -----------------------------------------------------------------------------
# CSecBridge AWS Worker - Functional Test Cases
#
# This scripts automates the testing of different functional test cases for
# AWS worker process, to accept requests forwarded to the cSecBridge app.
#
# To invoke test cases, submit requests via API-Service with necessary payload.
#
# Usage: ./run_db_tests.sh
# -----------------------------------------------------------------------------

# ------------------------------------------------------------
# AWS-TC-01: Attach S3 Read-Only Policy to Existing IAM User #
# ------------------------------------------------------------
# Invoke API, Check DB and Redis
# Invoke AWS CLI to check policy attachment to the user

# ------------------------------------------------------------
# AWS-TC-02: Revoke S3 Read-Only Policy to Existing IAM User #
# ------------------------------------------------------------
# Invoke API, Check DB and Redis
# Invoke AWS CLI to check policy detachment from the user

# ----------------------------------------------------------------
# AWS-TC-03: Attach S3 Read-Only Policy to Non-Existing IAM User #
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# AWS-TC-04: Revoke S3 Read-Only Policy to Non-Existing IAM User #
# ----------------------------------------------------------------

# ------------------------------------------------------------
# AWS-TC-05: Attach S3 Read-Only Policy to Existing IAM Role #
# ------------------------------------------------------------

# ------------------------------------------------------------
# AWS-TC-06: Revoke S3 Read-Only Policy to Existing IAM Role #
# ------------------------------------------------------------

# ----------------------------------------------------------------
# AWS-TC-07: Attach S3 Read-Only Policy to Non-Existing IAM Role #
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# AWS-TC-08: Revoke S3 Read-Only Policy to Non-Existing IAM Role #
# ----------------------------------------------------------------

# --------------------------------------------------------------------------
# AWS-TC-09: Attach S3 Read-Only Policy to Existing IAM User (Time Bound) #
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# AWS-TC-10: Revoke S3 Read-Only Policy to Existing IAM User (Time Bound) #
# --------------------------------------------------------------------------