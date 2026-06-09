# deckdefrance — Installation Guide

## Prerequisites

- **Steam Deck** (or any Linux system with Bluetooth + uinput support)
- **Python 3.12+** and `pip`
- **Git**
- **Tacx smart trainer** (or any BLE Cycling Power Service trainer)
- **Bluetooth** adapter (built into Steam Deck)

---

## 1. Clone the Repo

```bash
git clone <repo-url> /home/deck/git/deckdefrance
cd /home/deck/git/deckdefrance
```

## 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. udev Rules — uinput & Controller Access

The virtual gamepad needs permission to create uinput devices and be visible to Steam.

### Install the udev rules:

```bash
sudo cp 99-tacx-gamepad.rules /etc/udev/rules.d/99-tacx-gamepad.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

This ensures the Tacx Virtual Gamepad gets proper permissions and Steam detects it.

## 5. User Groups

You must be in the `input` group to access `/dev/uinput`:

```bash
sudo usermod -aG input $USER
```

**Log out and back in** (or reboot) for the group change to take effect.

Verify after re-login:

```bash
groups | grep input
```

## 6. Configure Your Trainer MAC

The configured MAC is `XX:XX:XX:XX:XX:XX` in `config.json`. To change it:

```bash
nano config.json
```

Or use the web UI **Configuration** tab after starting the app.

## 7. Run the App

### Development (with auto-reload):

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production (background process):

```bash
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > deckdefrance.log 2>&1 &
```

Or use the convenience script (kills any running instance first):

```bash
./start.sh
```

### Access the web UI:

Open `http://localhost:8000/` in a browser.

From another device on the same network: `http://<steam-deck-ip>:8000/`

### Stop the app:

```bash
pkill -f "uvicorn app.main:app"
```

---

## 8. Steam Controller Integration

The Tacx Virtual Gamepad is configured as an Xbox 360 controller (`vendor=0x045e, product=0x028e`). After the app is running, Steam should detect it.

> **Note:** Some games (e.g. Tour de France) only accept input from the first controller (js0). Since the Tacx pad is a separate device, the game won't see inputs from both the Steam Deck and the Tacx pad unless you use the **Controller Passthrough** feature to combine them into one device.

### Controller Passthrough (Recommended)

The **Controller Passthrough** feature reads inputs from the Steam Deck controller (or any gamepad) and forwards them through the Tacx Virtual Gamepad. This means the game sees **one controller** that combines:
- Steam Deck controls (left stick, dpad, face buttons, bumpers, triggers)
- Tacx trainer inputs (right trigger from power mapping, configurable button presses)

#### How to use:

1. Start the app (see step 7)
2. Open the web UI at `http://localhost:8000/`
3. Go to the **Control** tab
4. Under **Controller Passthrough**, click **Start Passthrough**
   - The app auto-detects the Steam Deck's virtual Xbox 360 pad
   - All Steam Deck inputs are forwarded to the Tacx Virtual Gamepad
5. In Steam, configure your game to use **Tacx Virtual Gamepad** as player 1 instead of the Steam Deck controller
   - Open Steam Big Picture → Controller Settings for your game
   - Select "Tacx Virtual Gamepad" as the active controller
6. Optionally start BLE streaming to also map trainer power to the right trigger

The passthrough runs independently from BLE streaming — you can use the Steam Deck controls even without a trainer connected.

### Manual Steam Setup (Alternative)

If you prefer not to use passthrough, configure **Additional Controllers** in Steam:

1. Open **Steam Big Picture** → launch your game
2. Press **Steam button** → **Controller Settings** → select the game's config
3. Near the bottom you'll see **"Additional Controllers"** — click it
4. Bind game actions to **both** the Steam Deck controller and the Tacx pad
5. Steam merges inputs from all configured controllers

A pre-made template `controller_tacx_gamepad.vdf` can help with step 4:
```bash
cp controller_tacx_gamepad.vdf ~/.steam/steam/controller_base/templates/
```

### If Steam doesn't see the Tacx pad:

- Restart the deckdefrance app (it creates the device on startup)
- Restart Steam
- Run `ls /dev/input/js*` to confirm a Tacx pad `js*` exists
- Run `cat /proc/bus/input/devices | grep -A10 "Tacx Virtual Gamepad"` to verify vendor/product IDs

---

## 9. BLE Streaming

1. Open the web UI at `http://localhost:8000/`
2. Go to the **Discovery** tab and scan for your Tacx trainer
3. Go to the **Config** tab and verify the MAC address
4. Go to the **Control** tab and click **Start Streaming**
5. The chart will show live power/cadence data
6. The right trigger (ABS_RZ) output scales 0-255 from 0–max_target_watts (default 250W)

---

## 10. Virtual Steering

The **Steer** tab provides a draggable virtual joystick that controls the in-game character's left stick (steering).

1. Navigate to the **Steer** tab in the web UI
2. Drag the purple thumbstick with your mouse or touch
3. X and Y values (-1 to 1) are sent to the left stick of the Tacx Virtual Gamepad
4. Release to snap back to center
5. Works independently of BLE streaming — no trainer connection required

The joystick sends updates at ~30fps via `POST /api/joystick` with `{ x, y }` in -1 to 1 range, mapped to 0–65535 on the uinput device.

Works alongside the **Controller Passthrough** feature — both write to the same Tacx Virtual Gamepad, so the game sees steering from either source.

### Remote Steering from a Phone or Tablet

Open the web UI on any device on the same network:

1. Find the Steam Deck's IP address:
   ```bash
   ip addr show | grep "inet " | grep -v 127.0.0.1
   ```
2. On your phone or tablet, open a browser to `http://<steam-deck-ip>:8000/`
3. Go to the **Steer** tab and drag the virtual joystick to control the game

This works over Wi-Fi — no trainer or BLE connection needed. The joystick input goes directly to the uinput device on the Steam Deck.

---

## 11. Troubleshooting

| Problem | Fix |
|---------|-----|
| `PermissionError: /dev/uinput` | Not in `input` group — run `sudo usermod -aG input $USER` and re-login |
| Steam doesn't detect Tacx pad | Restart app, restart Steam, check `/dev/input/js*` for Tacx pad |
| BLE connection fails | Ensure trainer is powered on, Bluetooth is enabled, MAC is correct |
| `ModuleNotFoundError` | Activate venv: `source .venv/bin/activate` |
| Port 8000 in use | `pkill -f "uvicorn"` or use `--port 8001` |
| Web UI not loading | `curl http://localhost:8000/` — check if server is running |
| Garbled text in terminal | Use Konsole instead of default terminal, or set `TERM=xterm-256color` |

---

## File Layout

```
deckdefrance/
├── INSTALL.md              ← this file
├── AGENTS.md               ← project overview (for AI assistants)
├── start.sh                ← convenience startup script
├── controller_tacx_gamepad.vdf ← Steam Input template for Tacx pad
├── 99-tacx-gamepad.rules   ← udev rule for Steam detection
├── config.json             ← persistent config (MAC, thresholds)
├── requirements.txt        ← Python dependencies
├── Dockerfile              ← Docker image
├── docker-compose.yml      ← Docker Compose
└── app/
    ├── main.py             ← FastAPI app + routes + streaming
    ├── mapper.py           ← uinput device + power mapping
    ├── config.py           ← JSON config read/write
    ├── discovery.py        ← BLE device scanning
    ├── passthrough.py      ← Steam Deck controller passthrough to uinput
    └── static/             ← Web UI (HTML, JS, CSS)
```
