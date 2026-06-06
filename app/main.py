from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

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

    # Check if MAC address is configured
    if mac_address == "XX:XX:XX:XX:XX:XX":
        return {
            "connected": False,
            "message": "Tacx MAC address not configured",
        }

    # Attempt to test connection (would require actual BLE implementation)
    try:
        # This is a placeholder - actual implementation would use bleak
        return {
            "connected": False,
            "message": f"Attempting to connect to {mac_address}... (Run trainer-specific code for actual connection)",
            "device_name": None,
            "power": None,
        }
    except Exception as e:
        return {
            "connected": False,
            "message": str(e),
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
