#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=============================="
echo "  deckdefrance — Setup"
echo "=============================="
echo ""

# Step 1: udev rules
echo "[1/3] Installing udev rules..."
./install-udev.sh

# Step 2: user in input group
echo ""
echo "[2/3] Checking input group..."
if groups "$USER" | grep -q '\binput\b'; then
    echo "  User '$USER' is already in the 'input' group."
else
    echo "  Adding '$USER' to the 'input' group..."
    sudo usermod -aG input "$USER"
    echo "  You'll need to log out and back in for this to take effect."
fi

# Step 3: start the server
echo ""
echo "[3/3] Starting deckdefrance..."
./start.sh

echo ""
echo "  Logs: tail -f $APP_DIR/deckdefrance.log"
echo "  Stop: pkill -f uvicorn"