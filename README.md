<p align="center">
  <img src="app/static/deckdefrance_logo.png" alt="deckdefrance" width="320">
</p>

# deckdefrance

**Tacx turbo trainer → Tour de France controller mapper.** Connects to a Tacx smart trainer over BLE, maps power/cadence/resistance to a virtual gamepad (uinput), merges a paired Bluetooth controller into the same device, and serves a web dashboard with a full-screen touch gamepad page.

The game sees **one** controller — *Tacx Virtual Gamepad* — with all inputs: Tacx power→trigger mappings + Bluetooth controller joystick/buttons.

<p align="center">
  <a href="https://youtu.be/fl-AArkezSE">
    <img src="https://img.youtube.com/vi/fl-AArkezSE/maxresdefault.jpg" width="600" alt="deckdefrance demo video">
  </a>
</p>

---

## Features

- **BLE Streaming** — Connects to Tacx trainers via Cycling Power Service with auto-reconnect (up to 10 retries)
- **Virtual Gamepad** — Creates a uinput Xbox 360 controller (0x045e/0x028e) with 8 axes + 11 buttons
- **Configurable Mappings** — Map power/cadence/resistance to triggers, buttons, or sticks
- **Controller Merge** — Forward a Bluetooth gamepad's inputs to the same virtual device
- **Web Dashboard** — Status monitoring, live chart, config, BLE discovery, steering, test controls
- **Full-Screen Touch Gamepad** — PWA `/play` page with virtual joystick and buttons (installable on Android)
- **Auto-Cache BLE Services** — Automatically caches BlueZ services before connecting
- **FTP Presets** — Beginner / Average / Competitive / Pro power threshold profiles
- **PWA Support** — Installable web app with service worker caching

---

## Quick Start

```bash
# 1. Install udev rules (required once for uinput access)
./install-udev.sh

# 2. Start the server
./start.sh
# Or manually: .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Open in browser
open http://localhost:8000
```

---

## Installation

See [INSTALL.md](INSTALL.md) for a complete step-by-step guide covering:

- Python virtual environment setup
- udev rules and permissions
- BLE connection setup
- Controller merge configuration
- Auto-start with systemd

---

## Web UI

| Tab | Description |
|-----|-------------|
| **Status** | Connection state, live power/cadence data, real-time chart |
| **Control** | Manual virtual joystick, D-pad, and button test |
| **Discover** | BLE scan for Tacx trainers |
| **Steer** | Draggable virtual joystick widget with mouse/touch |
| **Config** | MAC address, mappings, FTP presets, thresholds |
| **Test** | Sample mapping preview + BLE connection test |
| **Merge** | Scan, probe, and start Bluetooth controller merge |
| **Play** | `/play` full-screen touch gamepad (PWA start page) |

---

## Configurable Mappings

Mappings define how trainer metrics map to controller outputs. Configured in `config.json` or the Config tab:

```json
{
  "tacx_mac_address": "F0:C5:70:96:A9:3B",
  "max_target_watts": 250,
  "cadence_threshold": 90,
  "power_threshold_race": 120,
  "power_threshold_button_a": 200,
  "gear_multiplier": 2.0,
  "mappings": [
    { "source": "power", "target": "right_trigger" },
    { "source": "power", "target": "btn_a", "threshold": 200 }
  ]
}
```

### Sources & Targets

| Source | Description |
|--------|-------------|
| `power` | Instantaneous power in watts |
| `cadence` | Pedal cadence in RPM |
| `resistance` | Trainer resistance (future) |

| Target | Description | Range |
|--------|-------------|-------|
| `right_trigger` | Right trigger (Tacx power) | 0–255 |
| `left_trigger` | Left trigger | 0–255 |
| `left_stick_x/y` | Left analog stick | 0–65535 |
| `right_stick_x/y` | Right analog stick | 0–65535 |
| `btn_a/b/x/y` | Face buttons | Press/release |

**Scaling rules:**
- **Axes**: source value 0→max scales linearly to target range. Y-stick axes center at 50% (32768).
- **Buttons**: press when source exceeds `threshold`, release when below.

---

## Project Structure

```
deckdefrance/
├── AGENTS.md                 # Full project knowledge base
├── README.md                 # This file
├── INSTALL.md                # Detailed installation guide
├── config.json               # Persistent configuration
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image
├── docker-compose.yml        # Docker Compose
├── start.sh                  # Production start script
├── install-udev.sh           # Install udev rules for uinput
├── install-service.sh        # Install systemd user service
├── 99-tacx-gamepad.rules     # udev rules for Tacx Virtual Gamepad
└── app/
    ├── __init__.py
    ├── main.py               # FastAPI app — routes, streaming, auto-cache
    ├── mapper.py             # Tacx → controller mapping + shared uinput device
    ├── config.py             # JSON config read/write + FTP presets
    ├── discovery.py          # BLE device discovery
    ├── passthrough.py        # (DEPRECATED) Steam Deck passthrough
    ├── merge.py              # Bluetooth controller merge into shared uinput
    └── static/
        ├── index.html        # Web UI (all tabs)
        ├── play.html         # Full-screen touch gamepad (PWA)
        ├── app.js            # Frontend logic
        ├── style.css         # Yellow/black Tour de France theme
        ├── manifest.json     # PWA manifest
        ├── icon.svg          # PWA app icon
        ├── sw.js             # Service worker
        ├── deckdefrance_logo.png
        ├── deckdefrance_white.png
        ├── deckdefrance_black.png
        └── deckdefrance_white_square.png
```

---

## API Endpoints

### Health & Config
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server status with streaming/merge state |
| GET | `/api/config` | Get current config |
| POST | `/api/config` | Save config (partial update) |
| GET | `/api/config/presets` | List FTP presets |

### Streaming
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/start-streaming` | Start BLE streaming |
| POST | `/api/stop-streaming` | Stop streaming |
| GET | `/api/stream-status` | `{ streaming, connecting, message }` |
| GET | `/api/stream-data` | Latest `{ watts, cadence, timestamp }` |
| GET | `/api/stream-log` | Last 100 data points for chart |

### Controller
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/map` | Test mapping with sample values |
| POST | `/api/joystick` | Set left stick position (-1..1) |
| POST | `/api/dpad` | Set D-pad axes (-1/0/1) |
| POST | `/api/button` | Press/release a virtual button |

### Discovery
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/test-trainer` | Test BLE connection to configured MAC |
| POST | `/api/discover-tacx` | Scan for Tacx trainers (5s) |
| POST | `/api/discover-all` | Scan for all BLE devices |

### Merge
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/merge/devices` | List gamepad evdev devices |
| GET | `/api/merge/status` | Merge active state |
| POST | `/api/merge/probe` | Watch device for 3s, return events |
| POST | `/api/merge/start` | Start merge on source device path |
| POST | `/api/merge/stop` | Stop merge |

### Frontend
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web dashboard |
| GET | `/play` | Full-screen touch gamepad |

---

## BLE Streaming Flow

```
Tacx Trainer (BLE)
  → BleakClient (async with, auto-reconnects up to 10×)
  → pycycling CyclingPowerService notifications
  → power_handler: extracts watts, calculates cadence from crank revs
  → apply_mappings(): scales values per config, emits to uinput
  → Frontend polls /api/stream-data (200ms) + /api/stream-log (1s)
  → Chart.js renders rolling 120-point buffer (Watts, Cadence, Trigger)
```

### Reconnection Behavior
- On BLE drop: up to 10 retries with 3s delay (split into 0.5s polls)
- UI shows "Connecting..." during reconnection
- No idle data timeout — connection stays alive when not pedaling
- `async with BleakClient` pattern handles connect/disconnect lifecycle

---

## Controller Merge

Merge a paired Bluetooth controller with the Tacx trainer into one combined virtual gamepad:

```
Bluetooth Controller (evdev)
  → merge.py reads axis/button events
  → scales axis values from source range to target 0–65535
  → skips ABS_RZ (right trigger reserved for Tacx power)
  → writes to shared uinput device
  → Game sees Tacx Virtual Gamepad with ALL inputs
```

### Forwarded Inputs
| Source | Forwarded | Notes |
|--------|-----------|-------|
| Left stick (ABS_X/Y) | ✅ Scaled | Source min/max → 0..65535 |
| Right stick (ABS_RX/RY) | ✅ Scaled | Source min/max → 0..65535 |
| D-pad (ABS_HAT0X/Y) | ✅ Scaled | -1/1 forwarded as-is |
| Face buttons (A/B/X/Y) | ✅ Raw | EV_KEY forwarded as-is |
| Bumpers/thumb clicks | ✅ Raw | EV_KEY forwarded as-is |
| Left trigger (ABS_Z) | ✅ Scaled | Now forwarded |
| Right trigger (ABS_RZ) | ❌ Skipped | Reserved for Tacx power |

---

## Known Issues

- **Merge events only in game mode** — Steam Input virtual Xbox pads only produce events when a game consuming them is running. Probe/scan with the game open.
- **Steam Deck's built-in controller** — It works via merge! Once the game loads and **Tacx Virtual Gamepad** is set as Controller 1, the built-in Deck controls appear as a "Microsoft X-Box 360 pad N" device. When you click **Detect**, events show up immediately (Steam Input is already driving it) — that's the one to merge. Set Tacx Virtual Gamepad as first controller, merge the other pad as second.
- **BLE + Classic Bluetooth interference** — The Deck's single radio struggles with mixed connections. Use a USB BT dongle for the Tacx, or a USB cable for the controller.
- **`le-connection-abort-by-local`** — Transient BlueZ issue. Auto-cache retries up to 3×. If it persists, power-cycle the Tacx.
- **Do NOT run `bluetoothctl remove`** — Destroys the BlueZ service cache. `async with BleakClient` requires cached services.

---

## Development

```bash
# With auto-reload (development)
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Single worker only — multiple workers create duplicate uinput devices
```

---

## License

MIT
