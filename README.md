<p align="center">
  <img src="app/static/deckdefrance_white_square.png" alt="deckdefrance" width="320">
</p>

> **Turn any bike trainer into a game controller. Ride in Tour de France, race in Rocket League, drive in Forza — if a game supports a controller, deckdefrance works with it.**

When you pedal harder, the game goes faster. When you steer with a Bluetooth controller, the game turns. Everything feeds into one virtual gamepad that the game sees as a single controller.

<p align="center">
  <a href="https://youtu.be/fl-AArkezSE">
    <img src="https://img.youtube.com/vi/fl-AArkezSE/maxresdefault.jpg" width="600" alt="deckdefrance demo video">
  </a>
</p>

---

## What It Works With

### Compatible Trainers

Any smart trainer that broadcasts **Cycling Power Service** over Bluetooth Low Energy. The `pycycling` library we use has been tested with:

- **Tacx** — NEO, NEO 2T, Flux, Bushido, Vortex, Satori, Booster
- **Elite** — Suito-T, Justo, Direto, Drivo, Rampa, Sterzo Smart (steering plate)
- **Wahoo** — KICKR, KICKR Core (broadcasts CPS — untested but should work)
- **Zwift Hub / Zwift Hub One** (broadcasts CPS — untested but should work)
- **CycleOps** — Magnus, H3 (broadcasts CPS — untested but should work)
- **Garmin** — Vector 3 power meter pedals
- **Magene** — S3+ Speed/Cadence sensor
- **Power meters** — Any BLE power meter pedals or crank-based meters (4iiii, Stages, Favero, etc.)

If your trainer shows power in apps like Zwift or TrainerRoad, it'll work here.

### Compatible Games

Any game that supports a controller. The app creates a standard Xbox 360 virtual gamepad, so it shows up in every game on Steam. Great for:

- **Tour de France 2023 / 2024 / 2025** (the original use case)
- **Rocket League** — pedal for boost, steer with a controller
- **Forza Horizon / Motorsport** — power = acceleration
- **Euro Truck Simulator / American Truck Simulator** — cadence = speed
- **Grand Theft Auto V** — throttle with your legs
- **Cyberpunk 2077** — any driving game, really
- **Any racing or driving game**

### What You'll Need

- A **Steam Deck** (or any Linux PC)
- A **compatible smart trainer** (see above)
- A **Bluetooth controller** (Xbox, PlayStation, Steam Controller) — optional if you just want power/speed control

---

## Quick Start (5 minutes)

Open the **Terminal** app (Konsole) and run:

```bash
cd ~/git/deckdefrance
./setup.sh
```

One command. Type your password if prompted. The server starts automatically.

<details>
<summary><b>Advanced: run steps individually</b></summary>

```bash
./install-udev.sh   # permissions (once)
./start.sh          # start the server
```

</details>

<details>
<summary><b>Advanced: start manually</b></summary>

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use this if you want to see server logs in the terminal or run with auto-reload for development.

</details>

### 2. Open the Dashboard

On your Steam Deck, open a web browser and go to:

```
http://localhost:8000
```

You'll see the **deckdefrance** dashboard.

### 3. Set Up Your Trainer

1. Click the **Discover** tab
2. Click **Scan for Trainers**
3. Find your trainer in the list and click **Select**
4. Go to the **Status** tab and click **Start Streaming**

Wait about 15–30 seconds. Once it says "Connected", start pedaling — you'll see power and cadence data on the chart.

### 4. Play the Game

1. Start **Tour de France** on Steam
2. Go to the game's controller settings
3. Select **Trainer Virtual Gamepad** as your controller
4. Pedal to accelerate — the right trigger responds to your power

---

## Adding a Bluetooth Controller

Want to steer with a physical controller too? Here's how:

### Important: Controller Order in Steam

Tour de France (and many games) only accepts input from **Controller 1**. You need to reorder the controllers in Steam so that **Trainer Virtual Gamepad** is first.

1. Open Steam → right-click Tour de France → **Properties** → **Controller**
2. Click **Reorder Controllers**
3. Make sure **Trainer Virtual Gamepad** is at the top of the list
4. Launch the game

### Merge the Built-In Deck Controller

Once the game is running:

1. **Keep the game running** — Steam Input only activates virtual Xbox pads when a game is consuming them
2. **Switch to the web browser** (don't close the game)
3. Open the dashboard's **Merge** tab
4. Click **Scan**
5. You'll see "Microsoft X-Box 360 pad" devices
   - **Index 0** is the Trainer Virtual Gamepad itself — **do not merge this**
   - **Index 1** is your built-in Steam Deck controls
   - If you have extra Bluetooth controllers paired, they'll be further down
6. Click **Detect** on index 1 — events should appear **immediately without touching anything** — that's the Deck's built-in controls already being driven by Steam Input
7. Click **Start Merge**
8. Go back to your game — the Trainer mappings and your physical Deck controls now both work on **Trainer Virtual Gamepad**

---

## Dashboard Tabs

| Tab | What it does |
|-----|-------------|
| **Status** | See your power, cadence, and a live chart. Start/stop the trainer connection |
| **Control** | Test buttons and joysticks manually |
| **Discover** | Find your trainer via Bluetooth |
| **Steer** | A virtual joystick you can drag with your mouse/touchscreen |
| **Config** | Change settings like max power, button thresholds, or use a preset (Beginner/Average/Competitive/Pro) |
| **Test** | Preview how your settings will work without needing the trainer |
| **Merge** | Add a Bluetooth controller to work alongside the trainer |

## Screenshots

<p align="center">
  <img src="app/screenshots/status-tab.png" width="700" alt="Status tab with live chart">
  <br><em>Status tab — live power, cadence, and chart</em>
</p>

<p align="center">
  <img src="app/screenshots/merge-tab.png" width="700" alt="Merge tab scanning for controllers">
  <br><em>Merge tab — add a Bluetooth controller - (note: run when in game mode to detect the inbuilt steam deck controller)</em>
</p>

<p align="center">
  <img src="app/screenshots/controller-tab.png" width="350" alt="Full-screen Virtual touch gamepad">
  <br><em>Play page — full-screen Virtual touch gamepad</em>
</p>

---

## Tips

- **Run in the background** — After `./start.sh`, you can close the terminal and the server keeps running. Open the browser whenever you need it
- **Stop the server** — `pkill -f uvicorn` in a terminal
- **Restart** — `./start.sh` again (it kills the old process first)
- **Restart after config changes** — Click **Stop Streaming** then **Start Streaming** in the dashboard
- **Signal drops** — The app auto-reconnects up to 10 times. Just wait
- **Need the full guide?** See [INSTALL.md](INSTALL.md) for detailed setup, troubleshooting, and auto-start

---

## What's Under the Hood

For the curious: Python + FastAPI backend, Bluetooth Low Energy via `bleak`/`pycycling`, virtual gamepad via `evdev.UInput`, vanilla JS frontend with Chart.js. The app creates a virtual Xbox 360 controller that both the Trainer power data and your physical controller feed into, so the game sees one combined device.
