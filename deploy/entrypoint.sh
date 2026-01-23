#!/bin/bash
# Anneal GCP Entrypoint
#
# This script is the entrypoint for Cloud Run Jobs.
# It runs the Python job runner which handles:
# - Reading job parameters from environment
# - Running Anneal
# - Uploading results to GCS
# - Calling the webhook

set -e

echo "=============================================="
echo "Anneal GCP Container Starting"
echo "Job ID: ${JOB_ID:-not-set}"
echo "Project: ${PROJECT_NAME:-generated}"
echo "=============================================="

# Change to app directory
cd /app

# Run the job runner
exec python deploy/job_runner.py
