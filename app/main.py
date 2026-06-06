from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from bleak import BleakClient
from .mapper import map_tacx_to_controller
from .config import get_config, update_config
from .discovery import discover_tacx_trainers, discover_all_devices

app = FastAPI(title="deckdefrance", version="0.1.0")

# Serve static files (CSS, JS)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class MappingRequest(BaseModel):
    trainer_power: float
    cadence: float
    resistance: float


class ConfigRequest(BaseModel):
    tacx_mac_address: str | None = None
    max_target_watts: float | None = None
    cadence_threshold: float | None = None
    power_threshold_race: float | None = None
    power_threshold_button_a: float | None = None
    gear_multiplier: float | None = None


@app.get("/")
async def root():
    """Serve the web UI."""
    return FileResponse(static_dir / "index.html", media_type="text/html")


@app.get("/api/config")
async def get_configuration():
    """Retrieve current configuration."""
    return get_config()


@app.post("/api/config")
async def save_configuration(config: ConfigRequest):
    """Update configuration."""
    updates = config.dict(exclude_none=True)
    return update_config(updates)


@app.post("/api/map")
async def map_trainer(request: MappingRequest):
    """Map trainer metrics to controller output."""
    mapping = map_tacx_to_controller(
        trainer_power=request.trainer_power,
        cadence=request.cadence,
        resistance=request.resistance,
    )
    return {
        "input": request.dict(),
        "mapping": mapping,
    }


@app.post("/api/test-trainer")
async def test_trainer_connection():
    """Test connection to Tacx trainer."""
    config = get_config()
    mac_address = config.get("tacx_mac_address", "XX:XX:XX:XX:XX:XX")

    if mac_address == "XX:XX:XX:XX:XX:XX":
        return {
            "connected": False,
            "message": "Tacx MAC address not configured",
        }

    try:
        async with BleakClient(mac_address, timeout=10.0) as client:
            if not client.is_connected:
                await client.connect()

            if not client.is_connected:
                return {
                    "connected": False,
                    "message": f"Unable to connect to {mac_address}",
                }

            device_name = client.address or mac_address
            services = client.services
            service_count = sum(1 for _ in services) if services else 0

            return {
                "connected": True,
                "message": f"Connected to {device_name}",
                "device_name": device_name,
                "service_count": service_count,
            }
    except Exception as e:
        error_msg = str(e)
        # Check for BlueZ/DBus service errors (common on Steam Deck)
        if "ServiceUnknown" in error_msg or "org.freedesktop.DBus" in error_msg:
            return {
                "connected": False,
                "message": "BlueZ service unavailable. Bluetooth daemon may not be running or app lacks DBus access. Try: systemctl --user start bluetooth.service",
            }
        return {
            "connected": False,
            "message": error_msg,
        }


@app.post("/api/discover-tacx")
async def discover_tacx():
    """Discover Tacx trainers via Bluetooth scan."""
    try:
        devices = await discover_tacx_trainers(timeout=5)
        return {
            "found": len(devices),
            "devices": devices,
        }
    except RuntimeError as e:
        return {
            "found": 0,
            "devices": [],
            "error": str(e),
        }


@app.post("/api/discover-all")
async def discover_all():
    """Discover all Bluetooth devices."""
    try:
        devices = await discover_all_devices(timeout=5)
        return {
            "found": len(devices),
            "devices": devices,
        }
    except RuntimeError as e:
        return {
            "found": 0,
            "devices": [],
            "error": str(e),
        }
