#!/usr/bin/env bash
# Own your bambu Cloud - Startup Script
# Author: Ryan Ben Hassine (https://ryanbenhassine.com)
# License: https://ryanbenhassine.com

set -e

echo "=================================================="
echo " Own your bambu Cloud"
echo " Author: Ryan Ben Hassine (https://ryanbenhassine.com)"
echo " License: https://ryanbenhassine.com"
echo "=================================================="

# Create data directories if not present
mkdir -p data/uploads/logos data/uploads/videos

# Launch container
docker compose up -d

echo ""
echo "Own your bambu Cloud is running!"
echo "Dashboard: http://localhost:9930"
echo "API Docs:  http://localhost:9930/docs"
echo "=================================================="
