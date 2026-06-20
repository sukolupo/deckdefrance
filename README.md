# deckdefrance

Tacx turbo trainer → Tour de France game controller mapper. Connects to a Tacx smart trainer over BLE, maps power/cadence/resistance to a virtual gamepad (uinput), merges a paired Bluetooth controller into the same device, and serves a web dashboard with a full-screen touch gamepad page.

The game sees **one** controller ("Tacx Virtual Gamepad") with all inputs: Tacx power→trigger mappings + BT controller joystick/buttons.

## Features

- **BLE Streaming** — Connects to Tacx trainers via Cycling Power Service with auto-reconnect
- **Virtual Gamepad** — Creates a uinput Xbox 360 controller with 8 axes + 11 buttons
- **Configurable Mappings** — Map power/cadence/resistance to triggers, buttons, or sticks
- **Controller Merge** — Forward a Bluetooth gamepad's inputs to the same virtual device
- **Web Dashboard** — Status, config, discover, steer, test, and merge tabs
- **Full-Screen Touch Gamepad** — PWA play page with virtual joystick and buttons
- **Auto-Cache BLE Services** — Detects missing BlueZ service cache and caches it automatically
- **FTP Presets** — Beginner/Average/Competitive/Pro power threshold profiles

## Quick Start

```bash
# Install udev rules (required for uinput)
./install-udev.sh

# Run server
./start.sh
# OR
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Open browser to http://localhost:8000
```

## Setup

### 1. udev Rules

Run once to allow creating the virtual gamepad:

```bash
./install-udev.sh
```

Also ensure your user is in the `input` group:

```bash
sudo usermod -aG input $USER
# then log out and back in
```

### 2. Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Running

```bash
# Development (with auto-reload)
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (single worker — multiple workers create duplicate uinput devices)
./start.sh

# As a systemd user service (auto-start on boot)
./install-service.sh
systemctl --user start deckdefrance
```

### 4. BLE Connection

The app auto-caches BLE services on stream start. If that fails:

```bash
# Wake the Tacx (pedal or power-cycle)
bluetoothctl -- connect F0:C5:70:96:A9:3B   # cache services
bluetoothctl trust F0:C5:70:96:A9:3B         # trust
bluetoothctl disconnect F0:C5:70:96:A9:3B    # disconnect
# Then Start Streaming from the UI
```

**Do NOT run `bluetoothctl remove`** — it destroys the service cache.

### 5. Controller Merge

1. Pair a Bluetooth controller via System Settings → Bluetooth
2. Open the **Merge** tab in the web UI
3. Scan, Detect (press a button on your controller), then Start Merge
4. In the game, select **Tacx Virtual Gamepad** as the controller

## Web UI

| Tab | Description |
|-----|-------------|
| **Status** | Connection state, stream data, live chart (Watts/Cadence/Trigger) |
| **Control** | Manual virtual joystick, D-pad, and button test |
| **Discover** | BLE scan for Tacx trainers |
| **Steer** | Draggable virtual joystick widget |
| **Config** | MAC address, mappings, FTP presets, thresholds |
| **Test** | Sample mapping preview + BLE connection test |
| **Merge** | Scan, probe, and start Bluetooth controller merge |
| **Play** | `/play` — full-screen touch gamepad (PWA, installable) |

## Configurable Mappings

Mappings are defined in `config.json` or via the Config tab:

```json
{
  "tacx_mac_address": "F0:C5:70:96:A9:3B",
  "max_target_watts": 250,
  "mappings": [
    { "source": "power", "target": "right_trigger" },
    { "source": "power", "target": "btn_a", "threshold": 200 }
  ]
}
```

**Sources:** `power`, `cadence`, `resistance`
**Targets:** `right_trigger`, `left_trigger`, `left_stick_x/y`, `right_stick_x/y`, `btn_a/b/x/y`

- Axes scale 0→max over the source range to the target range
- Buttons press when source exceeds threshold, release below

## Project Structure

```
deckdefrance/
├── AGENTS.md              # Project knowledge base (detailed)
├── README.md
├── config.json            # Persistent config
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── start.sh               # Production start script
├── install-udev.sh        # Install udev rules for uinput
├── install-service.sh     # Install systemd user service
├── 99-tacx-gamepad.rules  # Udev rules for Tacx Virtual Gamepad
└── app/
    ├── main.py            # FastAPI app — routes, streaming, auto-cache
    ├── mapper.py          # Tacx → controller mapping + shared uinput device
    ├── config.py          # JSON config read/write + FTP presets
    ├── discovery.py       # BLE device discovery
    ├── passthrough.py     # (DEPRECATED) Steam Deck evdev passthrough
    ├── merge.py           # Bluetooth controller merge into shared uinput
    └── static/
        ├── index.html     # Web UI (all tabs)
        ├── play.html      # Full-screen touch gamepad (PWA start page)
        ├── app.js         # Frontend logic
        ├── style.css      # Yellow/black Tour de France theme
        ├── manifest.json  # PWA manifest
        ├── icon.svg       # PWA icon
        └── sw.js          # Service worker
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server status with streaming/merge state |
| GET/POST | `/api/config` | Get/save config |
| POST | `/api/start-streaming` | Start BLE streaming (auto-caches services) |
| POST | `/api/stop-streaming` | Stop streaming |
| GET | `/api/stream-status` | `{ streaming, connecting, message }` |
| GET | `/api/stream-data` | `{ watts, cadence, timestamp }` |
| GET | `/api/stream-log` | Last 100 data points for chart |
| GET | `/api/merge/devices` | List gamepad devices |
| GET | `/api/merge/status` | Merge active state |
| POST | `/api/merge/start` | Start merge on a device path |
| POST | `/api/merge/stop` | Stop merge |
| POST | `/api/joystick` | Set left stick position |
| POST | `/api/button` | Press/release a button |
| GET | `/play` | Full-screen touch gamepad |

## BLE Streaming Flow

```
Tacx Trainer (BLE)
  → BleakClient (async, auto-reconnects up to 10 retries)
  → pycycling CyclingPowerService notifications
  → power_handler extracts watts, calculates cadence from crank revs
  → apply_mappings() scales and emits to uinput
  → Frontend polls /api/stream-data every 200ms + chart updates
```

## Troubleshooting

- **Merge shows "Microsoft X-Box 360 pad N"** — These are Steam Input virtual devices. Try each one; events only appear when a game is consuming them.
- **BLE connection fails** — Wake the Tacx, run `bluetoothctl -- connect <mac>` to re-cache services, then Start Streaming.
- **Deck's built-in controls** — Steam Input grabs them at kernel level; the built-in controller cannot be merged. Use an external controller via USB or Bluetooth.
- **Bluetooth controller drops Tacx connection** — The single Bluetooth radio may struggle with both. Use a USB cable for the controller or a USB BT dongle for the Tacx.
- **"le-connection-abort-by-local"** — Transient BlueZ issue. Retry bluetoothctl connect up to 3 times; the app's auto-cache does this automatically.
