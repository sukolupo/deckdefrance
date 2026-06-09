# deckdefrance

Steam Deck Python app to support mapping from TacX Turbo Trainer metrics to Tour de France game controller actions.

## Features

- **Web UI** - Configuration panel and trainer connection testing
- **REST API** - Map trainer metrics to controller output
- **Docker Support** - Containerized deployment
- **Configuration Management** - Persistent parameter storage

## Project Structure

```
app/
├── __init__.py          # Package init
├── main.py              # FastAPI application
├── mapper.py            # Trainer to controller mapping logic
├── config.py            # Configuration management
└── static/
    ├── index.html       # Web UI interface
    ├── style.css        # Styling
    └── app.js           # Frontend logic
docker-compose.yml       # Docker compose configuration
requirements.txt         # Python dependencies
Dockerfile              # Docker image definition
```

## Prerequisites

### For Docker Option

**Steam Deck (Arch Linux):**

1. **Disable read-only filesystem:**
   ```bash
   sudo steamos-readonly disable
   ```

2. **Install Docker:**
   ```bash
   sudo pacman -S docker
   ```

3. **Start and enable the Docker daemon:**
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

4. **Add your user to the docker group (to run without sudo):**
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

5. **Install Docker Compose (optional, but recommended):**
   ```bash
   sudo pacman -S docker-compose
   ```

6. **Re-enable read-only filesystem:**
   ```bash
   sudo steamos-readonly enable
   ```

7. **Verify installation:**
   ```bash
   docker --version
   docker run hello-world
   ```

### For Local Installation

- Python 3.9 or higher
- pip package manager

## Quick Start

### Option 1: Docker (Recommended for Production)

Build and run with Docker Compose:

```bash
docker-compose up --build
```

Access the web UI at `http://localhost:8000/`

### Option 2: Local Installation (For Development)

#### Prerequisites
- Python 3.9+
- pip

#### Installation Steps

1. **Clone and navigate to the project:**
   ```bash
   cd /home/deck/git/deckdefrance
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run the FastAPI server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   The `--reload` flag watches for file changes and auto-restarts the server (useful for development).

5. **Access the application:**
   - Open your browser to `http://localhost:8000/`
   - Or from another device: `http://<steam-deck-ip>:8000/`

#### Running Without Auto-Reload (Production)

For a stable deployment without auto-reload:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

#### Steam Deck Specific Notes

On Steam Deck, you may need to activate the virtual environment in each terminal session:

```bash
source /home/deck/git/deckdefrance/.venv/bin/activate
```

To run the app in the background:

```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > deckdefrance.log 2>&1 &
```

View the log file:

```bash
tail -f deckdefrance.log
```

Stop the background process:

```bash
pkill -f "uvicorn app.main:app"
```

#### Running the Trainer Connection Script

To run the BLE trainer connection module directly (requires pynput and bleak):

```bash
pip install bleak pycycling pynput
python -m app.mapper
```

This will start the trainer connection handler that maps Tacx power directly to uinput events.


## Web UI Features

### Status Tab
- Service health check
- Trainer connection status
- Configuration status

### Discover Tab
Automatically find your Tacx trainer via Bluetooth scanning:

- **Scan for Tacx Trainers** - Scans specifically for Tacx devices (5-second scan)
- **Discovered Devices List** - Shows all discovered Tacx trainers with:
  - Device name
  - MAC address (Bluetooth hardware ID)
  - Signal strength (RSSI in dBm)
  - One-click select button to configure the trainer
- **Scan All Devices** - Shows all nearby Bluetooth devices (for debugging)

**How to use:**
1. Power on your Tacx trainer and ensure it's in pairing mode
2. Click "Scan for Tacx Trainers"
3. Wait for the scan to complete (up to 5 seconds)
4. Click "Select" on your trainer in the list
5. The MAC address is automatically populated in the Configuration tab

### Configuration Tab
Configure the following parameters:

- **Tacx MAC Address** - Bluetooth address of your trainer (auto-filled via Discover tab)
- **Max Target Watts** - Power ceiling for mapping (default: 300W)
- **Cadence Threshold** - RPM trigger for button actions (default: 95 RPM)
- **Power Threshold (Race Mode)** - Watts to activate race mode (default: 150W)
- **Power Threshold (Button A)** - Watts to trigger button A (default: 250W)
- **Gear Multiplier** - Resistance to gear conversion multiplier (default: 2.0)

### Test Connection Tab
- **Sample Mapping** - Test trainer metrics mapping with custom values
- **Trainer Connection Test** - Verify Tacx trainer connectivity

## API Endpoints

### `GET /`
Serves the web UI interface.

### `GET /api/config`
Retrieve current configuration.

Response:
```json
{
  "tacx_mac_address": "XX:XX:XX:XX:XX:XX",
  "max_target_watts": 300,
  "cadence_threshold": 95,
  "power_threshold_race": 150,
  "power_threshold_button_a": 250,
  "gear_multiplier": 2.0
}
```

### `POST /api/config`
Update configuration parameters. Send JSON with fields to update.

### `POST /api/map`
Map trainer metrics to controller output.

Request:
```json
{
  "trainer_power": 220,
  "cadence": 95,
  "resistance": 3.5
}
```

Response:
```json
{
  "input": {
    "trainer_power": 220,
    "cadence": 95,
    "resistance": 3.5
  },
  "mapping": {
    "cycling_power": 220,
    "button_a": false,
    "button_b": true,
    "gear": 7,
    "mode": "race"
  }
}
```

### `POST /api/test-trainer`
Test connection to Tacx trainer.

## Configuration File
### `POST /api/discover-tacx`
Scan for Tacx trainers via Bluetooth.

Response:
```json
{
   "found": 1,
   "devices": [
      {
         "mac_address": "AA:BB:CC:DD:EE:FF",
         "name": "Tacx Turbo Trainer",
         "rssi": -45
      }
   ]
}
```

`rssi` is the signal strength in dBm (higher values closer to -30 indicate stronger signals).

### `POST /api/discover-all`
Scan for all nearby Bluetooth devices (not just Tacx).

Response:
```json
{
   "found": 5,
   "devices": [
      {
         "mac_address": "AA:BB:CC:DD:EE:FF",
         "name": "Tacx Turbo Trainer",
         "rssi": -45
      },
      {
         "mac_address": "11:22:33:44:55:66",
         "name": "Steam Deck",
         "rssi": -50
      }
   ]
}
```


Configuration is stored in `config.json` in the project root. You can edit this file directly or use the web UI.

Example:
```json
{
  "tacx_mac_address": "AA:BB:CC:DD:EE:FF",
  "max_target_watts": 300,
  "cadence_threshold": 95,
  "power_threshold_race": 150,
  "power_threshold_button_a": 250,
  "gear_multiplier": 2.0
}
```

## Mapping Logic

The mapper converts trainer metrics as follows:

- **Cycling Power** = Trainer Power (watts)
- **Button A** = Active when Power > Power Threshold
- **Button B** = Active when Cadence > Cadence Threshold
- **Gear** = min(10, max(1, int(Resistance * Gear Multiplier)))
- **Mode** = "race" if Power > Race Threshold, else "cruise"

## Next Steps

1. Configure your Tacx trainer MAC address in the Configuration tab
2. Test the mapping with sample values
3. Run the trainer connection test
4. Integrate with your Steam Deck's game controller

## Accessing the App from Other Devices

Once running locally on Steam Deck, you can access the web UI from any device on the same network:

1. Find your Steam Deck's IP address:
   ```bash
   hostname -I
   ```

2. From another device, open your browser to:
   ```
   http://<steam-deck-ip>:8000/
   ```

   Example: `http://192.168.1.100:8000/`

## Troubleshooting

### "ModuleNotFoundError" or "No module named 'fastapi'"
- Ensure virtual environment is activated: `source .venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Port 8000 already in use
- Check what's running on port 8000: `lsof -i :8000`
- Kill the process: `pkill -f "uvicorn"`
- Or use a different port: `uvicorn app.main:app --port 8001`

### Cannot connect to Tacx trainer
- Verify MAC address is correct in Configuration tab
- Check if trainer is powered on and in pairing mode
- Ensure Bluetooth is enabled on Steam Deck
- View logs for connection errors: `tail -f deckdefrance.log`

### Web UI not loading
- Check if server is running: `curl http://localhost:8000/`
- Verify static files exist: `ls -la app/static/`
- Check browser console for JavaScript errors (F12)

### Permission denied errors
- Ensure you have proper directory permissions:
  ```bash
  chmod -R u+rwx /home/deck/git/deckdefrance
  ```

## Performance Considerations

- For development: Use `--reload` flag to auto-restart on changes
- For production: Run with `--workers 2` or more based on CPU
- On Steam Deck: Monitor performance with `htop` to avoid thermal throttling
- BLE connections: Keep USB 2.0 devices away from Bluetooth to reduce interference

