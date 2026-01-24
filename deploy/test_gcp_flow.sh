#!/bin/bash
# Test Full GCP Flow Locally
#
# Starts Pub/Sub emulator, GCS emulator, and runs the Anneal worker.
# This simulates the complete cloud environment.
#
# Usage:
#   ./test_gcp_flow.sh                    # Run worker directly
#   ./test_gcp_flow.sh submit             # Submit job via Pub/Sub
#   ./test_gcp_flow.sh down               # Tear down emulators

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[GCP-TEST]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }

# Check for .env file with API keys
if [ ! -f ".env" ]; then
    if [ -f "../secrets.toml" ]; then
        log "Creating .env from secrets.toml..."
        GEMINI_KEY=$(grep GEMINI_API_KEY ../secrets.toml | cut -d'"' -f2)
        ARISTOTLE_KEY=$(grep ARISTOTLE_API_KEY ../secrets.toml | cut -d'"' -f2)
        echo "GEMINI_API_KEY=$GEMINI_KEY" > .env
        echo "ARISTOTLE_API_KEY=$ARISTOTLE_KEY" >> .env
        log "Created .env file"
    else
        echo "ERROR: No .env file and no secrets.toml found"
        echo "Create deploy/.env with:"
        echo "  GEMINI_API_KEY=your-key"
        echo "  ARISTOTLE_API_KEY=your-key"
        exit 1
    fi
fi

case "${1:-up}" in
    up|start)
        log "=============================================="
        log "Starting GCP Emulators + Anneal Worker"
        log "=============================================="
        
        docker compose -f docker-compose.gcp-test.yaml up --build
        ;;
    
    submit)
        log "Submitting test job via Pub/Sub..."
        docker compose -f docker-compose.gcp-test.yaml --profile submit up submit-job
        ;;
    
    down|stop)
        log "Stopping all services..."
        docker compose -f docker-compose.gcp-test.yaml down -v
        ;;
    
    logs)
        docker compose -f docker-compose.gcp-test.yaml logs -f anneal-worker
        ;;
    
    *)
        echo "Usage: $0 [up|submit|down|logs]"
        echo ""
        echo "Commands:"
        echo "  up      - Start emulators and run worker (default)"
        echo "  submit  - Submit a test job via Pub/Sub"
        echo "  down    - Stop all services"
        echo "  logs    - Follow worker logs"
        ;;
esac
