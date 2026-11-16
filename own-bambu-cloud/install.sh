#!/usr/bin/env bash
# ==============================================================================
# Own your bambu Cloud — Fast Automated Installer
# An open-source, zero-database Bambu Lab farm management platform
# Author: Ryan Ben Hassine (https://ryanbenhassine.com)
# License: https://ryanbenhassine.com
# ==============================================================================

set -e

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
ORANGE='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PORT=9930

echo -e "${ORANGE}"
cat << "EOF"
   ___                       _                 _                            _ 
  / _ \__      ___ __  _   _| |__   __ _ _ __ | |__  _   _    ___| | ___  _   _  __| |
 | | | \ \ /\ / / '_ \| | | | '_ \ / _` | '_ \| '_ \| | | |  / __| |/ _ \| | | |/ _` |
 | |_| |\ V  V /| | | | |_| | |_) | (_| | | | | |_) | |_| | | (__| | (_) | |_| | (_| |
  \___/  \_/\_/ |_| |_|\__, |_.__/ \__,_|_| |_|_.__/ \__,_|  \___|_|\___/ \__,_|\__,_|
                       |___/                                                           
                       Own your bambu Cloud — by ryanbenhassine.com
EOF
echo -e "${NC}"
echo -e "${CYAN}${BOLD}Author:${NC} Ryan Ben Hassine (${BLUE}https://ryanbenhassine.com${NC})"
echo -e "${CYAN}${BOLD}License:${NC} ${BLUE}https://ryanbenhassine.com${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"

# 1. Check Docker Installation
echo -e "\n${BOLD}[1/4] Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed on this system.${NC}"
    echo -e "Please install Docker first: ${BLUE}https://docs.docker.com/engine/install/${NC}"
    exit 1
fi

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}Error: Neither 'docker compose' nor 'docker-compose' was found.${NC}"
    echo -e "Please install the Docker Compose plugin."
    exit 1
fi
echo -e "${GREEN}✓ Docker and Compose are available.${NC}"

# 2. Setup Data Directories & JSON Storage
echo -e "\n${BOLD}[2/4] Initializing JSON storage & asset directories...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p data/uploads/logos data/uploads/videos

# Initialize empty JSON stores if they do not exist
if [ ! -f data/printers.json ]; then
    echo "[]" > data/printers.json
    echo -e "${GREEN}✓ Initialized clean data/printers.json${NC}"
fi

if [ ! -f data/filaments.json ]; then
    echo "[]" > data/filaments.json
    echo -e "${GREEN}✓ Initialized clean data/filaments.json${NC}"
fi

if [ ! -f data/settings.json ]; then
    cat << 'EOF' > data/settings.json
{
  "system": { "version": "1.0.0", "theme": "dark" },
  "ai_eye": {
    "provider": "openai",
    "enabled": false,
    "auto_interval_seconds": 120,
    "openai": { "api_key": "", "model": "gpt-4o-mini" },
    "opensource": { "base_url": "http://localhost:11434/v1", "model": "llava", "api_key": "" }
  },
  "video_processor": {
    "logo_filename": null,
    "default_position": "bottom_right",
    "default_scale_pct": 15,
    "default_opacity": 0.85
  }
}
EOF
    echo -e "${GREEN}✓ Initialized data/settings.json${NC}"
fi

if [ ! -f data/ai_inspections.json ]; then
    echo "[]" > data/ai_inspections.json
fi

if [ ! -f data/timelapses.json ]; then
    echo "[]" > data/timelapses.json
fi

if [ ! -f data/bed_state.json ]; then
    echo "{}" > data/bed_state.json
fi

chmod -R 775 data

# 3. Build & Launch Container
echo -e "\n${BOLD}[3/4] Building and launching container on port ${PORT}...${NC}"
$DOCKER_COMPOSE down --remove-orphans 2>/dev/null || true
$DOCKER_COMPOSE up -d --build

# 4. Verification
echo -e "\n${BOLD}[4/4] Verifying health check...${NC}"
sleep 2

STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/printers" || echo "000")

if [ "$STATUS_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Own your bambu Cloud is running successfully!${NC}"
else
    echo -e "${ORANGE}Container is warming up. Please wait a few seconds...${NC}"
fi

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${BOLD}🎉 Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "${BOLD}Access Dashboard:${NC}  ${BLUE}http://localhost:${PORT}${NC}"
echo -e "${BOLD}API Documentation:${NC} ${BLUE}http://localhost:${PORT}/docs${NC}"
echo -e "${BOLD}Data Directory:${NC}    ${CYAN}${SCRIPT_DIR}/data/${NC}"
echo -e "${BOLD}Author Website:${NC}    ${BLUE}https://ryanbenhassine.com${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "Enjoy full local control over your Bambu Lab 3D printers!\n"
