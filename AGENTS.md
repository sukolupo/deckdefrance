# deckdefrance

Tacx turbo trainer → Tour de France controller mapper. Connects to a Tacx smart trainer over BLE, maps power/cadence to virtual gamepad (uinput) inputs, and serves a web dashboard.

## Stack

- **Backend**: FastAPI (Python 3.12) via uvicorn, port 8000
- **BLE**: `bleak` + `pycycling` (Cycling Power Service)
- **Virtual gamepad**: `python-uinput` — Xbox 360 controller vendor/product IDs (0x045e/0x028e), 6 axes + 4 buttons, configurable mappings via `apply_mappings()`
- **Frontend**: Vanilla HTML/CSS/JS + Chart.js (CDN)
- **Dependencies**: `requirements.txt`, Docker optional

## File Structure

```
deckdefrance/
├── AGENTS.md
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app — routes, streaming, global state
│   ├── mapper.py        # Tacx → controller mapping logic + uinput device
│   ├── config.py        # JSON config read/write + FTP presets
│   ├── discovery.py     # BLE device discovery via BleakScanner
│   └── static/
│       ├── index.html   # Web UI (5 tabs: Status, Control, Discover, Config, Test)
│       ├── app.js       # Frontend logic — polling, chart, streaming, config/mappings UI
│       └── style.css    # Purple gradient theme
├── start.sh             # Production startup script (kills old, starts single worker)
├── config.json          # Persistent config (live: F0:C5:70:96:A9:3B)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `index.html` |
| GET | `/api/health` | `{ status: "ok" }` |
| GET | `/api/config` | Get current config |
| POST | `/api/config` | Save config (partial update, `exclude_none`) |
| POST | `/api/map` | Test mapping (power, cadence, resistance → buttons/gear/mode) |
| POST | `/api/joystick` | Set left stick position (`{ x, y }` in -1 to 1 range) |
| POST | `/api/test-trainer` | Test BLE connection to configured MAC |
| POST | `/api/discover-tacx` | BLE scan for Tacx trainers (5s timeout) |
| POST | `/api/discover-all` | BLE scan for all devices |
| POST | `/api/start-streaming` | Start BLE streaming background task (waits up to 20s for connection) |
| POST | `/api/stop-streaming` | Cancel streaming task |
| GET | `/api/stream-status` | `{ streaming: bool, message: str }` |
| GET | `/api/stream-data` | `{ watts, cadence, timestamp }` |
| GET | `/api/stream-log` | Array of last 100 `{ time, watts, cadence }` entries |

## Streaming Data Flow

```
Tacx Trainer (BLE)
  → BleakClient (async, 10s timeout)
  → pycycling CyclingPowerService (notification handler)
  → power_handler(data) callback:
      1. extracts data.instantaneous_power → watts
      2. getattr(data, 'crank_revolutions', 0) → cadence
      3. updates global last_power_data dict + streaming_log deque (maxlen=100)
      4. calls apply_mappings(mappings, watts, cadence, 0, max_watts)
         → scales per mapping rules, emits to uinput (ABS_RZ for right trigger)
  → Frontend polls GET /api/stream-data every 200ms
  → Frontend polls GET /api/stream-log every 1s
  → Chart updates every poll (200ms, with Chart.js animation)
```

## Global State (in main.py)

- `streaming_active` (bool), `streaming_message` (str), `streaming_task` (Task | None)
- `last_power_data` = `{ watts, cadence, timestamp }`
- `streaming_log` = `deque(maxlen=100)` of `{ time, watts, cadence }`

## Configuration (config.json)

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

### FTP Presets

Presets are available via `GET /api/config/presets` and in the Config UI. Based on Functional Threshold Power (avg watts over 1hr):

| Preset | FTP | Max Trigger | Race Mode | Button A | Cadence |
|--------|-----|-------------|-----------|----------|---------|
| Beginner | ~75W | 150W | 90W | 130W | 80 RPM |
| Average | ~125W | 250W | 120W | 200W | 90 RPM |
| Competitive | ~200W | 350W | 180W | 280W | 95 RPM |
| Pro | ~300W | 500W | 250W | 400W | 100 RPM |

## Mapping Logic (mapper.py)

- `trainer_power` → `cycling_power` (pass-through)
- `trainer_power > 250` → `button_a = True`
- `cadence > 95` → `button_b = True`
- `resistance * 2` (clamped 1-10) → `gear`
- `trainer_power > 150` → `mode = "race"`, else `"cruise"`

### Configurable Mappings (`config.json` → `mappings[]`)

Users define which trainer metrics map to which controller outputs. Each mapping has:

| Field | Description |
|-------|-------------|
| `source` | One of `"power"`, `"cadence"`, `"resistance"` |
| `target` | Controller output: `right_trigger`, `left_trigger`, `left_stick_x`, `left_stick_y`, `right_stick_x`, `right_stick_y`, `btn_a`, `btn_b`, `btn_x`, `btn_y` |
| `threshold` | (optional, buttons only) Source value above which the button is pressed |

**Scaling rules:**
- **Axes**: source value 0→max scales to target range. Triggers use 0–255, sticks use 0–65535. Y-axis sticks center at 0W (32768) and deflect up as power increases.
- **Buttons**: emit press when source exceeds threshold, release when below.

**Default mappings:**
```json
[
  { "source": "power", "target": "right_trigger" },
  { "source": "power", "target": "btn_a", "threshold": 200 }
]
```

## Frontend Polling

Polling only runs while streaming is active (started/stopped in `startStreamDataPolling` / `stopStreamDataPolling`):
- **Stream data**: every 200ms via `/api/stream-data`
- **Stream log**: every 1s via `/api/stream-log`
- **Status poll**: every 5s via `/api/stream-status`
- **Chart**: rolling 120-point buffer (~2 min), 3 lines (Watts green, Cadence blue, Trigger red)

## Virtual Steering Tab

The **Steer** tab provides a draggable virtual joystick widget that maps to the left stick (ABS_X/ABS_Y) on the uinput device.

- Widget is a 200px circular base with a 70px purple thumb, built with divs + CSS
- Mouse and touch events track displacement from center, clamped to base radius
- X/Y values (-1 to 1) are sent to `POST /api/joystick` with 30ms throttle
- Backend maps -1..1 to 0..65535 and emits `uinput.ABS_X` + `uinput.ABS_Y`
- Works independently of BLE streaming — no trainer required
- Releases snap back to center and send (0, 0)

## Running

```bash
# Local
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# With reload
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (single worker, kills old instance first)
./start.sh

# Docker
docker compose up --build
```

The app runs on the Steam Deck. The configured Tacx MAC is `F0:C5:70:96:A9:3B`.

## Known Issues / Notes

- BLE connection can take 2-15s; start-streaming waits up to 20s (40×0.5s polls)
- The `start_streaming` endpoint used to wait only 0.5s — was too short, bumped to 10s then 20s
- `import time` was originally inside the power handler — moved to module top
- `crank_revolutions` may not exist on all trainer models — falls back to 0 with `getattr`
- Frontend JS cache-busting uses `?v=N` in script tag — bump on changes
- The trainer sends notifications even at 0W (idle), so data flow is always active
- Config is read once at stream start (not on every notification) — restart streaming after config changes
- Right trigger emits on ABS_RZ, left trigger on ABS_Z (SDL/game convention on Linux)
- Always use a single uvicorn worker (`--workers` defaults to 1) — multiple workers create stale duplicate devices
- Chart.js loaded from CDN (not bundled) — requires internet
