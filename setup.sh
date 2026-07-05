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
if [ ! -f "99-tacx-gamepad.rules" ]; then
    echo "ERROR: 99-tacx-gamepad.rules not found"
    exit 1
fi
sudo cp 99-tacx-gamepad.rules /etc/udev/rules.d/99-tacx-gamepad.rules
sudo chmod 644 /etc/udev/rules.d/99-tacx-gamepad.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "  Done."

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
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > deckdefrance.log 2>&1 &
PID=$!
sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "  deckdefrance is running (PID $PID)."
    echo ""
    echo "  Open the dashboard:"
    echo "    http://localhost:8000"
else
    echo "  ERROR: deckdefrance failed to start. Check deckdefrance.log for details."
    exit 1
fi

echo ""
echo "  Logs: tail -f $APP_DIR/deckdefrance.log"
echo "  Stop: pkill -f uvicorn"