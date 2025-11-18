#!/bin/bash
# collect_logs.sh - Collect Docker Compose logs for Stripe Playwright Service

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Create logs directory if it doesn't exist
LOGS_DIR="${BASE_DIR}/output/logs"
mkdir -p "${LOGS_DIR}"

# Create timestamp for log filename
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="${LOGS_DIR}/playwright_service_${TIMESTAMP}.log"

# Change to the base directory to run docker-compose
cd "${BASE_DIR}"

# Collect Docker Compose logs and save to file
echo "Collecting Playwright Service logs..."
docker-compose -f config/docker-compose.yml logs > "${LOG_FILE}"

echo "✓ Logs saved to: ${LOG_FILE}"