#!/bin/bash
# Object Detection & Counting Application Launcher
# =================================================

set -e

CONDA_ENV="ml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Object Detection & Counting${NC}"
echo -e "${GREEN}================================${NC}"

cd "${SCRIPT_DIR}"

# Try to activate conda
if command -v conda &> /dev/null; then
    echo -e "${YELLOW}Activating conda: ${CONDA_ENV}${NC}"
    eval "$(conda shell.bash hook)"
    conda activate ${CONDA_ENV} 2>/dev/null || {
        echo -e "${RED}Warning: Could not activate ${CONDA_ENV}${NC}"
    }
fi

# Install if requested
if [ "$1" == "--install" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}Done!${NC}"
fi

# Run
echo -e "${GREEN}Starting application...${NC}"
python app.py
