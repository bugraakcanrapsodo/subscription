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

echo "Pruning Docker build cache to avoid corruption..."
docker builder prune -f

echo "Starting stripe-playwright-service..."
docker-compose -f "$BASE_DIR/config/docker-compose.yml" up --build -d

echo ""
echo "✓ Service started successfully on port 3001"
echo "  Health check: curl http://localhost:3001/api/health"