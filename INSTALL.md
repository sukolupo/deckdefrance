<p align="center">
  <img src="app/static/deckdefrance_logo.png" alt="deckdefrance" width="240">
</p>

# Installation Guide

Step-by-step instructions to set up deckdefrance on a Steam Deck (or any Linux system).

---

## Prerequisites

- **Python 3.12+** (pre-installed on Steam Deck / SteamOS)
- **Bluetooth** adapter (built-in on Steam Deck)
- **Tacx smart trainer** (or any BLE Cycling Power Service device)
- **(Optional) Bluetooth controller** for the merge feature

---

## 1. Clone & Dependencies

```bash
cd ~/git
git clone <repo-url> deckdefrance
cd deckdefrance

# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. udev Rules & Permissions

The virtual gamepad (`/dev/uinput`) and the Tacx Virtual Gamepad device need world-writable permissions.

```bash
# Install udev rules
./install-udev.sh
```

This copies `99-tacx-gamepad.rules` to `/etc/udev/rules.d/`, reloads udev, and triggers the rules.

Then add your user to the `input` group (required for reading evdev devices, used by merge):

```bash
sudo usermod -aG input $USER
```

**Log out and back in** (or reboot) for group changes to take effect.

---

## 3. First Run

```bash
# Start the server
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Open the web UI
# http://localhost:8000
```

Check the **Status** tab — if everything is running you'll see server health as OK.

---

## 4. Configure Tacx MAC Address

**Option A — Auto-discover (recommended):**
1. Wake your Tacx trainer (pedal or power-cycle)
2. Open the **Discover** tab in the web UI
3. Click **Scan for Tacx Trainers**
4. Click **Select** on your trainer — MAC is auto-filled in Config

**Option B — Manual:**
1. Find your Tacx MAC via `bluetoothctl`:
   ```bash
   bluetoothctl scan on
   # look for your trainer, note the MAC, then:
   bluetoothctl scan off
   ```
2. Enter the MAC in the **Config** tab and click **Save**

---

## 5. BLE Connection Setup

The app will attempt to cache BLE services automatically when you click **Start Streaming**. If that fails, do it manually:

```bash
# 1. Wake the Tacx (pedal or power-cycle so it advertises)
# 2. Connect to cache services:
timeout 30 bluetoothctl -- connect F0:C5:70:96:A9:3B
# 3. Trust it (optional but recommended):
bluetoothctl trust F0:C5:70:96:A9:3B
# 4. Disconnect:
bluetoothctl disconnect F0:C5:70:96:A9:3B
# 5. Verify services are cached:
bluetoothctl info F0:C5:70:96:A9:3B
#    Should show: UUID: Cycling Power (00001818-...)
```

**Important:** Do NOT run `bluetoothctl remove F0:C5:70:96:A9:3B` — it destroys the service cache and breaks streaming.

### If `bluetoothctl -- connect` fails with `le-connection-abort-by-local`

This is a transient BlueZ issue. Retry 2–3 times — it usually succeeds. The app's auto-cache retries up to 3 times automatically.

---

## 6. Start Streaming

1. Open the **Status** tab
2. Click **Start Streaming**
3. Wait for "Connected" status (the UI polls every 2s while connecting)
4. Pedal — you should see power and cadence data, and the chart should update

### If streaming fails

- "Device with address ... was not found" → BLE services not cached. Follow step 5.
- Tacx shows 0W → power-cycle the trainer (unplug USB/power for 10s)
- Connection drops → the app auto-reconnects up to 10 times

---

## 7. (Optional) Controller Merge

Merge a Bluetooth controller so both the Tacx mappings and your controller feed into one virtual gamepad.

### Pair the controller

1. Go to Steam Deck Settings → Bluetooth → Pair a new device
2. Put your controller in pairing mode and select it

### Start merge

1. Launch your game and select **Tacx Virtual Gamepad** as Controller 1
2. Open the **Merge** tab in the web UI
3. Click **Scan** to list available gamepad devices
4. You'll see one or more "Microsoft X-Box 360 pad N" entries (these are Steam Input virtual wrappers)
   - The first one (0) is usually the Tacx Virtual Gamepad itself — **do not merge this**
   - The second one (1) is typically your built-in Deck controller
   - If you have an external controller paired, there may be more
5. Click **Detect** on a device — if events appear immediately without touching anything, that's the Deck's built-in controller (Steam Input is already driving it)
6. Click **Start Merge** on the correct device
7. Both the Tacx mappings and your physical controls now feed into **Tacx Virtual Gamepad**

### Important notes

- **Set Tacx Virtual Gamepad as Controller 1 in the game first** — this activates Steam Input's virtual Xbox pads, making them available in the device list
- **The device that shows events immediately on Detect is the one to merge** — it's the Deck's built-in controller already being driven by Steam Input
- **Do NOT merge the first "Microsoft X-Box 360 pad" (index 0)** — that's likely the Tacx Virtual Gamepad itself
- **Merge only produces events in game mode** — Steam Input only drives its virtual Xbox pads when a game is consuming them
- **The left trigger now forwards through merge** — only the right trigger is reserved for Tacx power mapping

---

## 8. Auto-Start (systemd User Service)

To have deckdefrance start automatically on boot:

```bash
./install-service.sh
```

This creates and enables a systemd user service at `~/.config/systemd/user/deckdefrance.service`.

### Manage the service

```bash
systemctl --user start deckdefrance     # start now
systemctl --user stop deckdefrance      # stop
systemctl --user restart deckdefrance   # restart
systemctl --user status deckdefrance    # check status
journalctl --user -u deckdefrance -f    # follow logs
```

### Running manually (without systemd)

```bash
# Production (single worker, kills old instance first)
./start.sh

# Or directly
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Background with nohup
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > deckdefrance.log 2>&1 &
```

**Always use a single worker** — multiple workers create duplicate uinput devices.

---

## 9. Production Start Script

`start.sh` kills any existing deckdefrance process and starts fresh:

```bash
./start.sh
```

Logs go to `deckdefrance.log` in the project root.

---

## 10. Docker (Alternative)

If you prefer Docker:

```bash
docker compose up --build
```

Note: Docker requires extra configuration for Bluetooth and uinput device access on the Steam Deck. Local installation is recommended.

---

## FTP Presets

The **Config** tab includes preset profiles based on Functional Threshold Power:

| Preset | FTP | Max Trigger | Race Mode | Button A | Cadence |
|--------|-----|-------------|-----------|----------|---------|
| Beginner | ~75W | 150W | 90W | 130W | 80 RPM |
| Average | ~125W | 250W | 120W | 200W | 90 RPM |
| Competitive | ~200W | 350W | 180W | 280W | 95 RPM |
| Pro | ~300W | 500W | 250W | 400W | 100 RPM |

---

## Troubleshooting

### Permission denied on `/dev/uinput`
→ Run `./install-udev.sh` and log out/in

### Permission denied on `/dev/input/event*`
→ Run `sudo usermod -aG input $USER` and log out/in

### BLE connection keeps failing
- Wake the Tacx (pedal or power-cycle)
- Run `bluetoothctl -- connect <mac>` manually to re-cache services
- Power-cycle the Tacx (unplug 10s)
- If you ran `bluetoothctl remove`, the service cache is gone — redo step 5

### Controller not detected in Merge tab
- Make sure the controller is paired via Steam Deck Bluetooth settings
- Try probing with the game running (Steam Input virtual pads only activate when a game is consuming them)
- Check each "Microsoft X-Box 360 pad N" entry — one of them is yours

### Right trigger works but left trigger doesn't in game
- The left trigger should now forward through merge (fixed in `merge.py`)
- Make sure you've restarted the server after pulling updates

### Port 8000 already in use
```bash
pkill -f "uvicorn"
```

### Server won't start
```bash
# Check Python version
python --version  # needs 3.12+

# Check dependencies
source .venv/bin/activate
pip install -r requirements.txt
```
