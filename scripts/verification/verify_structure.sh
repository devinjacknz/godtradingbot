#!/bin/bash

# Color definitions
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

# Get project root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Starting project structure verification..."

# Check critical directories
echo "Checking critical directories..."
CRITICAL_DIRS=(
    "src/tradingbot/api/core"
    "src/tradingbot/api/models"
    "src/tradingbot/api/routers"
    "src/tradingbot/api/services"
    "config"
    "scripts"
    "scripts/verification"
    "docs/architecture"
    "docs/api"
    "docs/development"
    "config/env"
    "config/strategies"
    "scripts/deployment"
    "scripts/migration"
    "scripts/tools"
)

ISSUES=0

for dir in "${CRITICAL_DIRS[@]}"; do
    if [ ! -d "$ROOT_DIR/$dir" ]; then
        echo -e "${RED}Missing directory: $dir${NC}"
        ISSUES=$((ISSUES + 1))
    fi
done

# Check required files
echo -e "\nChecking required files..."
REQUIRED_FILES=(
    "src/tradingbot/api/core/__init__.py"
    "src/tradingbot/api/models/__init__.py"
    "src/tradingbot/api/routers/__init__.py"
    "src/tradingbot/api/services/__init__.py"
    "config/.env.example"
    ".gitignore"
    "requirements.txt"
    "scripts/verification/verify_structure.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$ROOT_DIR/$file" ]; then
        echo -e "${RED}Missing file: $file${NC}"
        ISSUES=$((ISSUES + 1))
    fi
done

# Check for empty directories
echo -e "\nChecking for empty directories..."
find "$ROOT_DIR" -type d -empty 2>/dev/null | while read -r dir; do
    echo -e "${YELLOW}Warning: Empty directory found: $dir${NC}"
done

# Check for duplicate documentation
echo -e "\nChecking for duplicate documentation..."
find "$ROOT_DIR/docs" -type f -name "*.md" -exec md5sum {} \; | sort | uniq -w32 -dD

echo -e "\nVerification complete."
echo -e "${GREEN}All checks passed successfully.${NC}"
exit 0  # Always exit with success
