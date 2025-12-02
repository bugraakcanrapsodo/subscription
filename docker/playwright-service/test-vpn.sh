#!/bin/bash

# Quick VPN Test Script
# Tests if VPN connections work for all configured locations

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Mullvad VPN Connection Test                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if service is running
if ! curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
    echo -e "${RED}✗ Playwright service is not running on port 3001${NC}"
    echo ""
    echo "Start it with:"
    echo "  cd docker/playwright-service"
    echo "  docker-compose -f config/docker-compose.yml up"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Playwright service is running${NC}"
echo ""

# Test each location
locations=("us" "ca" "au" "gb" "de" "fr" "es" "jp" "sg")

echo "Testing VPN connections..."
echo ""

for loc in "${locations[@]}"; do
    echo -n "Testing ${loc}.conf... "
    
    response=$(curl -s -X POST http://localhost:3001/api/vpn/test \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"${loc}\"}" \
        --max-time 30 || echo '{"success": false}')
    
    if echo "$response" | grep -q '"success":true'; then
        country=$(echo "$response" | grep -o '"country":"[^"]*"' | cut -d'"' -f4 | head -1)
        ip=$(echo "$response" | grep -o '"ip":"[^"]*"' | cut -d'"' -f4 | head -1)
        echo -e "${GREEN}✓ Connected${NC} - $country ($ip)"
    elif echo "$response" | grep -q "Config not found"; then
        echo -e "${YELLOW}⚠ Config not found${NC} (${loc}.conf missing)"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Test Complete                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next: Add 'location' parameter to your API calls:"
echo ""
echo "  curl -X POST http://localhost:3001/api/checkout/pay-card \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{
      \"checkoutUrl\": \"...\",
      \"location\": \"de\",
      \"cardNumber\": \"4242424242424242\",
      ...
    }'"
echo ""



