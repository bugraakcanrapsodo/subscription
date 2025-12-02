#!/bin/bash
# localrun.sh - Start Stripe Playwright Service

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Stopping and removing any existing stripe-playwright-service container..."
docker stop stripe-playwright-service 2>/dev/null || true
docker rm stripe-playwright-service 2>/dev/null || true

echo "Cleaning docker-compose processes..."
docker-compose -f "$BASE_DIR/config/docker-compose.yml" down

echo "Cleaning output directories..."
bash "$SCRIPT_DIR/cleanup.sh"

# Enable BuildKit for faster, cached builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "Building stripe-playwright-service (using cache)..."
docker-compose -f "$BASE_DIR/config/docker-compose.yml" build

echo "Starting stripe-playwright-service..."
docker-compose -f "$BASE_DIR/config/docker-compose.yml" up -d

echo ""
echo "✓ Service started successfully on port 3001"
echo "  Waiting for service to be ready (VPN initializing in background)..."
sleep 3
echo "✓ Service ready! VPN will be available shortly"
echo ""
echo "  Health check: curl http://localhost:3001/api/health"
echo "  Test VPN: curl -X POST http://localhost:3001/api/vpn/test -H 'Content-Type: application/json' -d '{\"country\":\"de\"}'"