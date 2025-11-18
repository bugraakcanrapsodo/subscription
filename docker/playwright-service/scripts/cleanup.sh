#!/bin/bash
# cleanup.sh - Clean output directories for Stripe Playwright Service
echo "Cleaning up output directories..."

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Script directory: $SCRIPT_DIR"
echo "Base directory: $BASE_DIR"

# Clean videos directory (keep .gitkeep)
echo "Cleaning videos directory..."
find "$BASE_DIR/output/videos/" -type f ! -name '.gitkeep' -exec rm -f {} + 2>/dev/null || echo "No files to clean in videos directory"

# Clean screenshots directory (keep .gitkeep)
echo "Cleaning screenshots directory..."
find "$BASE_DIR/output/screenshots/" -type f ! -name '.gitkeep' -exec rm -f {} + 2>/dev/null || echo "No files to clean in screenshots directory"

# Clean logs directory (keep .gitkeep)
echo "Cleaning logs directory..."
find "$BASE_DIR/output/logs/" -type f ! -name '.gitkeep' -exec rm -f {} + 2>/dev/null || echo "No files to clean in logs directory"

# Clean attachments directory (keep .gitkeep)
echo "Cleaning attachments directory..."
find "$BASE_DIR/output/attachments/" -type f ! -name '.gitkeep' -exec rm -f {} + 2>/dev/null || echo "No files to clean in attachments directory"

echo "✓ All directories cleaned successfully!"
