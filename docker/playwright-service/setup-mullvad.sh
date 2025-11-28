#!/bin/bash

# Mullvad VPN Setup Script
# This script helps you set up Mullvad VPN configurations for the Playwright service

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Mullvad VPN Setup for Playwright Service              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if vpn-configs directory exists
if [ ! -d "vpn-configs" ]; then
    echo "Creating vpn-configs directory..."
    mkdir -p vpn-configs
fi

echo "📋 Step 1: Download Mullvad Configurations"
echo "────────────────────────────────────────────────────────────────"
echo ""
echo "Please follow these steps:"
echo ""
echo "1. Go to: https://mullvad.net/en/account/"
echo "2. Login with your Mullvad account number"
echo "3. Click on 'WireGuard configuration'"
echo "4. Generate configurations for these locations:"
echo ""
echo "   Required locations:"
echo "   • United States (us)"
echo "   • Canada (ca)"
echo "   • Australia (au)"
echo "   • United Kingdom (gb)"
echo "   • Germany (de)"
echo "   • France (fr)"
echo "   • Spain (es)"
echo "   • Japan (jp)"
echo "   • Singapore (sg)"
echo ""
echo "5. Download each .conf file"
echo "6. Place them in: $(pwd)/vpn-configs/"
echo "7. Rename them to match location codes:"
echo "   - us-xxx.conf → us.conf"
echo "   - de-xxx.conf → de.conf"
echo "   - etc."
echo ""

read -p "Press Enter when you've downloaded all configs..."

echo ""
echo "📂 Step 2: Checking Configuration Files"
echo "────────────────────────────────────────────────────────────────"
echo ""

# Expected locations
locations=("us" "ca" "au" "gb" "de" "fr" "es" "jp" "sg")
missing=()

for loc in "${locations[@]}"; do
    if [ -f "vpn-configs/${loc}.conf" ]; then
        echo -e "${GREEN}✓${NC} Found: ${loc}.conf"
    else
        echo -e "${RED}✗${NC} Missing: ${loc}.conf"
        missing+=("$loc")
    fi
done

echo ""

if [ ${#missing[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All configuration files found!${NC}"
else
    echo -e "${YELLOW}⚠️  Missing ${#missing[@]} configuration(s): ${missing[*]}${NC}"
    echo ""
    echo "You can add missing locations later. Continuing with available configs..."
fi

echo ""
echo "🔐 Step 3: Securing Configuration Files"
echo "────────────────────────────────────────────────────────────────"
echo ""

# Set proper permissions
chmod 600 vpn-configs/*.conf 2>/dev/null || true
echo -e "${GREEN}✓${NC} Set permissions to 600 (read/write owner only)"

echo ""
echo "🐳 Step 4: Docker Configuration"
echo "────────────────────────────────────────────────────────────────"
echo ""

# Check if docker-compose.yml has cap_add
if grep -q "cap_add:" config/docker-compose.yml 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Docker Compose has NET_ADMIN capability"
else
    echo -e "${YELLOW}⚠️  Docker Compose may need NET_ADMIN capability${NC}"
    echo "   Make sure docker-compose.yml includes:"
    echo "   cap_add:"
    echo "     - NET_ADMIN"
fi

echo ""
echo "🧪 Step 5: Testing VPN Connections"
echo "────────────────────────────────────────────────────────────────"
echo ""

read -p "Do you want to test VPN connections now? (y/n): " test_vpn

if [ "$test_vpn" = "y" ] || [ "$test_vpn" = "Y" ]; then
    echo ""
    echo "Starting Docker container..."
    
    # Build and start
    docker-compose -f config/docker-compose.yml up -d --build
    
    echo "Waiting for service to start..."
    sleep 5
    
    echo ""
    echo "Testing VPN connections..."
    echo ""
    
    for loc in "${locations[@]}"; do
        if [ -f "vpn-configs/${loc}.conf" ]; then
            echo -n "Testing ${loc}.conf... "
            
            response=$(curl -s -X POST http://localhost:3000/api/vpn/test \
                -H "Content-Type: application/json" \
                -d "{\"location\": \"${loc}\"}" || echo '{"success": false}')
            
            if echo "$response" | grep -q '"success":true'; then
                country=$(echo "$response" | grep -o '"country":"[^"]*"' | cut -d'"' -f4)
                echo -e "${GREEN}✓ Connected${NC} (${country})"
            else
                echo -e "${RED}✗ Failed${NC}"
            fi
        fi
    done
    
    echo ""
    echo "Stopping Docker container..."
    docker-compose -f config/docker-compose.yml down
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ Setup Complete!                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the Playwright service:"
echo "   cd docker/playwright-service"
echo "   docker-compose -f config/docker-compose.yml up"
echo ""
echo "2. Test VPN connection:"
echo "   curl -X POST http://localhost:3000/api/vpn/test \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"location\": \"de\"}'"
echo ""
echo "3. Run your test cases:"
echo "   pytest tests/test_data_driven.py --excel examples/mvp_test_cases.xlsx"
echo ""
echo "Documentation:"
echo "  • Mullvad Integration: MULLVAD_INTEGRATION.md"
echo "  • Location-based Testing: LOCATION_BASED_TESTING.md"
echo ""



