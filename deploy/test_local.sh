#!/bin/bash
# Local Test Script for Anneal GCP Deployment
#
# Tests the job runner locally without needing GCP infrastructure.
# Simulates what Cloud Run Jobs would do.
#
# Usage:
#   ./test_local.sh "Create a stack data structure"
#   ./test_local.sh  # Uses default prompt

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[TEST]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Default prompt if not provided
PROMPT="${1:-Create a simple counter with increment and get operations}"
PROJECT_NAME="${2:-test_project}"
JOB_ID="local-$(date +%s)"

log "=============================================="
log "Anneal Local Test"
log "=============================================="
log "Job ID: $JOB_ID"
log "Project: $PROJECT_NAME"
log "Prompt: $PROMPT"
log ""

# Check for secrets
if [ ! -f "$PROJECT_ROOT/secrets.toml" ]; then
    error "secrets.toml not found. Create it with your API keys."
    exit 1
fi

# Source .env if exists (for API keys)
if [ -f "$SCRIPT_DIR/.env" ]; then
    log "Loading .env file..."
    export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | xargs)
fi

# Option 1: Test with Docker (full simulation)
test_with_docker() {
    log "Building Docker image..."
    docker build -t anneal-local -f "$SCRIPT_DIR/Dockerfile.gcp" "$PROJECT_ROOT"
    
    log "Running container..."
    docker run --rm \
        -e JOB_ID="$JOB_ID" \
        -e PROMPT="$PROMPT" \
        -e PROJECT_NAME="$PROJECT_NAME" \
        -e GEMINI_API_KEY="${GEMINI_API_KEY}" \
        -e ARISTOTLE_API_KEY="${ARISTOTLE_API_KEY}" \
        -e LOCAL_MODE="true" \
        -v "$SCRIPT_DIR/output:/app/output" \
        anneal-local
}

# Option 2: Test without Docker (faster iteration)
test_without_docker() {
    log "Running directly (no Docker)..."
    cd "$PROJECT_ROOT"
    
    # Set environment
    export JOB_ID="$JOB_ID"
    export PROMPT="$PROMPT"
    export PROJECT_NAME="$PROJECT_NAME"
    export LOCAL_MODE="true"
    
    # Read keys from secrets.toml
    export GEMINI_API_KEY=$(grep GEMINI_API_KEY secrets.toml | cut -d'"' -f2)
    export ARISTOTLE_API_KEY=$(grep ARISTOTLE_API_KEY secrets.toml | cut -d'"' -f2)
    
    python deploy/job_runner.py
}

# Parse options
case "${3:-direct}" in
    docker)
        test_with_docker
        ;;
    direct|*)
        test_without_docker
        ;;
esac

log ""
log "=============================================="
log "Test Complete!"
log "=============================================="
log "Check generated files in:"
log "  - generated/$PROJECT_NAME/"
log "  - spec/Spec/$PROJECT_NAME/"
