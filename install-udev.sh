#!/usr/bin/env bash
set -euo pipefail

RULES_SRC="$(dirname "$0")/99-tacx-gamepad.rules"
RULES_DST="/etc/udev/rules.d/99-tacx-gamepad.rules"

if [ ! -f "$RULES_SRC" ]; then
    echo "ERROR: $RULES_SRC not found"
    exit 1
fi

echo "Installing udev rules..."
sudo cp "$RULES_SRC" "$RULES_DST"
sudo chmod 644 "$RULES_DST"

echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done. /dev/uinput and Tacx Virtual Gamepad devices now world-writable."
echo ""
echo "Also ensure you're in the 'input' group for evdev access:"
echo "  sudo usermod -aG input \$USER"
echo "Then log out and back in (or reboot)."