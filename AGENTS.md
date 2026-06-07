# deckdefrance

Tacx turbo trainer → Tour de France controller mapper. Connects to a Tacx smart trainer over BLE, maps power/cadence to virtual gamepad (uinput) inputs, and serves a web dashboard.

## Stack

- **Backend**: FastAPI (Python 3.12) via uvicorn, port 8000
- **BLE**: `bleak` + `pycycling` (Cycling Power Service)
- **Virtual gamepad**: `python-uinput` — emits `ABS_Z` (right trigger, 0-255) mapped from watts
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
│   ├── config.py        # JSON config read/write
│   ├── discovery.py     # BLE device discovery via BleakScanner
│   └── static/
│       ├── index.html   # Web UI (4 tabs: Status, Control, Discover, Config, Test)
│       ├── app.js       # Frontend logic — polling, chart, streaming control
│       └── style.css    # Purple gradient theme
├── config.json          # Persistent config (live: F0:C5:70:96:A9:3B)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `index.html` |
| GET | `/api/config` | Get current config |
| POST | `/api/config` | Save config (partial update, `exclude_none`) |
| POST | `/api/map` | Test mapping (power, cadence, resistance → buttons/gear/mode) |
| POST | `/api/test-trainer` | Test BLE connection to configured MAC |
| POST | `/api/discover-tacx` | BLE scan for Tacx trainers (5s timeout) |
| POST | `/api/discover-all` | BLE scan for all devices |
| POST | `/api/start-streaming` | Start BLE streaming background task (waits up to 10s for connection) |
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
      4. emits uinput ABS_Z (trigger_value = min(watts, 300) / 300 * 255)
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
  "max_target_watts": 300,
  "cadence_threshold": 95,
  "power_threshold_race": 150,
  "power_threshold_button_a": 250,
  "gear_multiplier": 2.0
}
```

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
- **Axes** (triggers, sticks): source value 0→max scales to target 0→255. Joystick Y-axes invert (higher source = higher stick deflection).
- **Buttons**: emit press when source exceeds threshold, release when below.

**Default mappings:**
```json
[
  { "source": "power", "target": "right_trigger" },
  { "source": "power", "target": "left_stick_y" }
]
```

## Frontend Polling

Polling only runs while streaming is active (started/stopped in `startStreamDataPolling` / `stopStreamDataPolling`):
- **Stream data**: every 200ms via `/api/stream-data`
- **Stream log**: every 1s via `/api/stream-log`
- **Status poll**: every 5s via `/api/stream-status`
- **Chart**: rolling 120-point buffer (~2 min), 3 lines (Watts green, Cadence blue, Trigger red)

## Running

```bash
# Local
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# With reload
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

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
- The trainer sends notifications even at 0W (idle), so data flow is always active
- Chart.js loaded from CDN (not bundled) — requires internet
