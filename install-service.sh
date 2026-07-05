#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="deckdefrance"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_DST="$SERVICE_DIR/$SERVICE_NAME.service"

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_DST" <<EOF
[Unit]
Description=deckdefrance — Trainer → game controller mapper
After=network-online.target bluetooth.target
Wants=network-online.target bluetooth.target

[Service]
Type=simple
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
WorkingDirectory=$APP_DIR
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

echo "Installed user service to $SERVICE_DST"
echo ""

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME.service"
echo ""
echo "Service enabled. Start it now or on next boot:"
echo "  systemctl --user start $SERVICE_NAME    # start now"
echo "  systemctl --user stop $SERVICE_NAME     # stop"
echo "  systemctl --user status $SERVICE_NAME   # check status"
echo "  journalctl --user -u $SERVICE_NAME -f   # follow logs"