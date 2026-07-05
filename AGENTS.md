# deckdefrance

Trainer turbo trainer → Tour de France controller mapper. Connects to a Trainer smart trainer over BLE, maps power/cadence/resistance to a virtual gamepad (uinput), merges a paired Bluetooth controller into the same device, and serves a web dashboard with a full-screen touch gamepad page.

The game sees **one** controller ("Trainer Virtual Gamepad") with all inputs: Trainer power→trigger mappings + BT controller joystick/buttons.

## Stack

- **Backend**: FastAPI (Python 3.12) via uvicorn, port 8000
- **BLE**: `bleak` + `pycycling` (Cycling Power Service), auto-reconnects on drop
- **Virtual gamepad**: `evdev.UInput` — Xbox 360 controller vendor/product IDs (0x045e/0x028e), 8 axes + 11 buttons, shared by both Trainer mapper and external controller merge
- **Controller Merge**: `evdev` — reads events from a paired Bluetooth controller and forwards them (with axis range scaling) to the same virtual gamepad, so the game sees one combined controller
- **Frontend**: Vanilla HTML/CSS/JS + Chart.js (CDN)
- **Dependencies**: `requirements.txt`, Docker optional

## File Structure

```
deckdefrance/
├── AGENTS.md
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app — routes, streaming, global state
│   ├── mapper.py        # Trainer → controller mapping logic + shared uinput device
│   ├── config.py        # JSON config read/write + FTP presets
│   ├── discovery.py     # BLE device discovery via BleakScanner
│   ├── passthrough.py   # Steam Deck controller evdev passthrough (DEPRECATED — use merge)
│   ├── merge.py         # External Bluetooth controller merge into shared uinput device
│   └── static/
│       ├── index.html   # Web UI (Status, Control, Discover, Steer, Config, Test, Merge tabs)
│       ├── play.html    # Full-screen touch gamepad page (PWA start page)
│       ├── app.js       # Frontend logic — polling, chart, config, mappings, virtual joystick, merge, commands
│       ├── style.css    # Purple gradient theme
│       ├── manifest.json # PWA manifest
│       ├── icon.svg     # PWA app icon
│       └── sw.js        # Service worker (caches static assets)
├── start.sh             # Production start (single worker, kills old instance)
├── config.json          # Persistent config (MAC, FTP, mappings)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## User Workflow

1. **Start the server** (see Running)
2. **Configure** — set the Trainer MAC address in the Config tab (or Discover → Select)
3. **(Optional) Start merge** — pair a Bluetooth controller, go to Merge tab → Scan → Select device → Start Merge
4. **Start streaming** — Status tab → Start Streaming; trainer connects, power→trigger mapping begins
5. **Play** — open the Play page (`/play`) or go to the game and select **Trainer Virtual Gamepad** as the controller
6. **Pedal** — power drives the right trigger; cadence/power thresholds activate buttons per your mappings
7. **Steer** — use the BT controller's joystick (via merge) or the on-screen virtual joystick on the Play page

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `index.html` |
| GET | `/api/health` | `{ status: "ok" }` |
| GET | `/api/config` | Get current config |
| POST | `/api/config` | Save config (partial update, `exclude_none`) |
| POST | `/api/map` | Test mapping (power, cadence, resistance → buttons/gear/mode) |
| POST | `/api/joystick` | Set left stick position (`{ x, y }` in -1 to 1 range) |
| POST | `/api/dpad` | Set D-pad axes (`{ x, y }` in -1/0/1) |
| POST | `/api/button` | Press/release a virtual button `{ button, pressed }` |
| POST | `/api/test-trainer` | Test BLE connection to configured MAC |
| POST | `/api/discover-trainer` | BLE scan for trainers (5s timeout) |
| POST | `/api/discover-all` | BLE scan for all devices |
| POST | `/api/start-streaming` | Start BLE streaming background task (returns immediately; poll status for result) |
| POST | `/api/stop-streaming` | Cancel streaming task |
| GET | `/api/stream-status` | `{ streaming: bool, connecting: bool, message: str }` |
| GET | `/api/stream-data` | `{ watts, cadence, timestamp }` |
| GET | `/api/stream-log` | Array of last 100 `{ time, watts, cadence }` entries |
| GET | `/api/merge/devices` | List available gamepad evdev devices for merging |
| GET | `/api/merge/status` | `{ active: bool, source, device_name }` |
| POST | `/api/merge/probe` | Watch a device for 3s and return any events detected (identify which controller is which) |
| POST | `/api/merge/start` | Start merge from `source_path` query param |
| POST | `/api/merge/stop` | Stop merge |
| GET | `/play` | Full-screen touch gamepad page |

## PWA

- `manifest.json`, `icon.svg`, `sw.js` in `/static/`
- Service worker caches all pages and static assets on first load (stale-while-revalidate)
- Installable on Android Chrome ("Add to Home Screen") — opens `/play` in standalone mode
- After updating static files, bump `?v=N` in both HTML files AND update `sw.js` PRECACHE paths to force re-cache

## Streaming Data Flow

```
Trainer (BLE)
  → BleakClient (async, auto-reconnects on drop, up to 10 retries)
  → pycycling CyclingPowerService (notification handler)
  → power_handler(data) callback:
      1. extracts data.instantaneous_power → watts
      2. getattr(data, 'crank_revolutions', 0) → cadence
      3. updates global last_power_data dict + streaming_log deque (maxlen=100)
      4. calls apply_mappings(mappings, watts, cadence, 0, max_watts)
         → scales per mapping rules, emits to uinput
  → Frontend polls GET /api/stream-data every 200ms
  → Frontend polls GET /api/stream-log every 1s
  → Chart updates every poll (200ms, with Chart.js animation)
```

### Reconnection Behavior

- If BLE drops, the background task attempts reconnection (up to 10 retries, 3s delay between attempts)
- The UI shows "Connecting..." during reconnection attempts via status polling
- Streaming remains active across reconnections — the frontend polling continues
- There is **no idle data timeout** — the connection stays alive even when not pedaling

## Global State (in main.py)

- `streaming_active` (bool), `streaming_message` (str), `streaming_task` (Task | None)
- `last_power_data` = `{ watts, cadence, timestamp }`
- `streaming_log` = `deque(maxlen=100)` of `{ time, watts, cadence }`

## Configuration (config.json)

```json
{
  "trainer_mac_address": "XX:XX:XX:XX:XX:XX",
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

## Configurable Mappings (`config.json` → `mappings[]`)

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
- **Status poll**: every 2s while connecting, every 5s while streaming via `/api/stream-status`
- **Chart**: rolling 120-point buffer (~2 min), 3 lines (Watts green, Cadence blue, Trigger red)

## Virtual Steering

The **Steer** tab and the **Play** page both provide a draggable virtual joystick widget that maps to the left stick (ABS_X/ABS_Y) on the uinput device.

- Widget is a circular base with a purple thumb, built with divs + CSS
- Mouse and touch events track displacement from center, clamped to base radius
- X/Y values (-1 to 1) are sent to `POST /api/joystick` with 30ms throttle
- Backend maps -1..1 to 0..65535 and emits to uinput (both axes in a single SYN frame)
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

The app runs on the Steam Deck. The configured Trainer MAC is `XX:XX:XX:XX:XX:XX`.

### Connection Approach

- Uses `async with BleakClient(mac_address, timeout=20.0) as client:` — requires the device to be cached in BlueZ with resolved services
- **Auto-cache**: On `POST /api/start-streaming`, the app checks `bluetoothctl info <mac>` for UUIDs. If none found, it runs `bluetoothctl -- connect <mac>` (up to 3 retries with timeout) then `bluetoothctl disconnect <mac>` to populate the service cache. Only then does it start the `BleakClient` streaming task.
- The `bluetoothctl -- connect <mac>` syntax (double-dash) is critical — it runs connect as a non-interactive command and reliably discovers services. Piped `bluetoothctl connect ... | grep` does not.
- **Do NOT use `bluetoothctl remove`** — it destroys the service cache and breaks streaming
- The `async with` context manager auto-disconnects on exit (normal or error)
- If the BLE link drops during streaming, the `async with` block exits and the outer retry loop reconnects (up to 10 retries, 3s delay)

### Critical: BLE Connection Lessons (June 2026)

The streaming code **must** use `async with BleakClient(mac_address, timeout=20.0) as client:` — this is the only pattern that works reliably. Here's what was tried and why other approaches fail:

**Do NOT use manual connect/disconnect:**
```python
# BAD — bypasses bleak's service discovery, connection never stabilizes
client = BleakClient(mac_address, timeout=45.0)
await client.connect()
```
- `client.connect()` without `async with` bypasses bleak's internal service discovery path
- Even though `connect()` returns `True`, subsequent GATT operations fail with "failed to discover services, device disconnected"
- With `async with`, bleak properly discovers services on entry and disconnects on exit

**Do NOT use longer timeouts:**
- 45s timeout was tried because `client.connect()` took 30-35s to return
- With `async with` and cached services, 20s timeout works fine (connects in 5-15s)
- The long timeout in manual mode masked a fundamentally broken connection path

**Do NOT poll `client.is_connected` to detect disconnects:**
- `is_connected` can return stale `True` after the BLE link is already down
- The `async with` pattern handles this naturally: when the link drops, the context exits with an exception
- The outer exception handler catches it and triggers reconnection

**Do NOT add idle data timeouts:**
- The Trainer sends notifications even at 0W when idle
- If the user stops pedaling, data may pause — a timeout would needlessly disconnect
- The existing pattern (just `await asyncio.sleep(0.5)` in the streaming loop) is correct
- Connection stays alive as long as the BLE link is up, regardless of data

## Controller Merge (Bluetooth + Trainer)

Merge a paired Bluetooth controller with the trainer into one combined virtual gamepad. Both inputs go to the same device — the game sees a single "Trainer Virtual Gamepad".

### Setup

1. **Pair your Bluetooth controller** with the Steam Deck via System Settings → Bluetooth
2. Open the **Merge** tab in the web UI
3. Click **Scan** to list available gamepad devices
4. Select your controller from the list (may appear as "Microsoft X-Box 360 pad N" — these are Steam virtual wrappers; try each one)
5. Click **Start Merge**
6. In the game, select **Trainer Virtual Gamepad** as the controller

Both the trainer mappings and your Bluetooth controller inputs now feed into one virtual gamepad.

### What Gets Forwarded

| Source Input | Forwarded? | Notes |
|-------------|------------|-------|
| Left stick (ABS_X/Y) | ✅ Scaled | Source min/max → 0..65535 |
| Right stick (ABS_RX/RY) | ✅ Scaled | Source min/max → 0..65535 |
| D-pad (ABS_HAT0X/Y) | ✅ Scaled | Source -1/1 → target -1/1 |
| Face buttons (A/B/X/Y) | ✅ Raw | EV_KEY events forwarded as-is |
| Bumpers/thumb clicks | ✅ Raw | EV_KEY events forwarded as-is |
| Triggers (ABS_Z/RZ) | ❌ Skipped | Reserved for Trainer power→trigger mapping (merge would overwrite with idle 0) |

### How It Works

```
Bluetooth Controller (evdev)
  → merge._run_merge() (async evdev reader)
    → reads axis & button events
    → scales axis values from source range (e.g. -32767..32767) to our device range (0..65535)
    → skips trigger axes (Trainer-owned)
    → writes to our shared UInput device
  → Combined with trainer power mappings on the same device
  → Game sees one controller (Trainer Virtual Gamepad) with ALL inputs
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/merge/devices` | List available gamepad evdev devices for merging |
| GET | `/api/merge/status` | `{ active: bool, source, device_name }` |
| POST | `/api/merge/start?source_path=/dev/input/eventN` | Start merge from a device path |
| POST | `/api/merge/stop` | Stop merge |

### Notes

- The Steam virtual Xbox pads (`0x28de:0x11ff`) are created by Steam Input and may wrap your Bluetooth controller. Try each one if you don't see your controller's real name.
- Axis values are dynamically scaled from the source device's absinfo ranges to match our device's declared ranges.
- Merge and trainer streaming operate independently — use both at the same time or separately.
- Merge does not forward ABS_RZ (right trigger) — reserved for Trainer power mapping. ABS_Z (left trigger) is now forwarded from the controller.
- If you change the source BT controller, stop merge, scan again, and start on the new device path.

## Known Issues / Notes

### BLE Connection Setup (Fresh Start)

The app **auto-caches** services on `POST /api/start-streaming` — if `bluetoothctl info` shows no UUIDs, the app runs `bluetoothctl -- connect` + `disconnect` up to 3 times. Usually no manual steps needed.

If the auto-cache fails or you need to do it manually:

1. **Wake the Trainer** — pedal or power-cycle the trainer so it advertises
2. **Scan** via the app: `POST /api/discover-all` (or click Discover in UI)
3. **Cache services via bluetoothctl**:
   ```bash
   timeout 30 bluetoothctl -- connect XX:XX:XX:XX:XX:XX
   ```
   Use `bluetoothctl -- connect <mac>` (double-dash) not `bluetoothctl connect <mac>`. The `--` runs it as a non-interactive command with proper service discovery. Retry a few times if `le-connection-abort-by-local` — it usually succeeds within 3 attempts.
4. **Trust it**: `bluetoothctl trust XX:XX:XX:XX:XX:XX`
5. **Disconnect**: `bluetoothctl disconnect XX:XX:XX:XX:XX:XX`
6. **Verify**: `bluetoothctl info XX:XX:XX:XX:XX:XX` should show `UUID: Cycling Power (00001818-...)`
7. **Start streaming** from the UI — `async with BleakClient` uses the cached services

**Do NOT run `bluetoothctl remove`** — it destroys the service cache and the `async with BleakClient` approach requires the device to be in BlueZ's cache with resolved services.

### BLE Troubleshooting

If streaming fails with "Device with address XX:XX:XX:XX:XX:XX was not found", the device isn't cached in BlueZ. Run the BLE Connection Setup steps above.

- `start-streaming` returns immediately; poll `/api/stream-status` for the connection result (the UI does this automatically every 2s while connecting)
- Streaming auto-reconnects on BLE drop (up to 10 retries, 3s delay)
- There is **no idle data timeout** — the connection stays alive when not pedaling
- `crank_revolutions` may not exist on all trainer models — falls back to 0 with `getattr`
- Frontend JS/CSS cache-busting uses `?v=N` in script/link tags and `sw.js` PRECACHE — bump all on changes
- Config is read once at stream start (not on every notification) — restart streaming after config changes
- Right trigger emits on ABS_RZ, left trigger on ABS_Z (SDL/game convention on Linux)
- Always use a single uvicorn worker (`--workers` defaults to 1) — multiple workers create stale duplicate uinput devices
- Chart.js loaded from CDN (not bundled) — requires internet
- Passthrough.py (Steam Deck controller passthrough) is deprecated.
- Built-in Steam Deck controller IS mergeable with this exact workflow:
  1. In Steam, reorder controllers for the game so **Trainer Virtual Gamepad** is Controller 1 (right-click game → Properties → Controller → Reorder Controllers)
  2. Launch the game — Steam Input creates virtual Xbox pads only when a game consumes them
  3. Keep the game running, switch to browser, open Merge tab
  4. Scan — the first pad (index 0) is Trainer Virtual Gamepad itself — **do not merge this**
  5. Click **Detect** on index 1 — events appear immediately without touching anything (Steam Input is already driving it)
  6. Click **Start Merge**
  7. The built-in Deck controls now feed into Trainer Virtual Gamepad alongside the trainer mappings
- Tour de France (and most games) only reads **Controller 1** — if Trainer Virtual Gamepad isn't first in the Steam controller order, the game won't see it
