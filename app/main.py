from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import asyncio
import time
from collections import deque

from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
from .mapper import map_tacx_to_controller, apply_mappings, device, _BUTTON_CODES
from .config import get_config, update_config, FTP_PRESETS
from .discovery import discover_tacx_trainers, discover_all_devices
from .passthrough import (
    start_passthrough,
    stop_passthrough,
    get_passthrough_status,
    list_controller_devices,
)
import uinput

app = FastAPI(title="deckdefrance", version="0.1.0")

# Global state for streaming
streaming_task: asyncio.Task | None = None
streaming_active = False
streaming_message = ""
last_power_data = {
    "watts": 0,
    "cadence": 0,
    "timestamp": None,
}
streaming_log = deque(maxlen=100)

# Serve static files (CSS, JS)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class MappingRequest(BaseModel):
    trainer_power: float
    cadence: float
    resistance: float


class JoystickRequest(BaseModel):
    x: float = 0.0
    y: float = 0.0


class ButtonRequest(BaseModel):
    button: str
    pressed: bool


class ConfigRequest(BaseModel):
    tacx_mac_address: str | None = None
    max_target_watts: float | None = None
    cadence_threshold: float | None = None
    power_threshold_race: float | None = None
    power_threshold_button_a: float | None = None
    gear_multiplier: float | None = None
    mappings: list[dict] | None = None


@app.get("/api/config/presets")
async def get_presets():
    """Get FTP-based power preset recommendations."""
    return FTP_PRESETS


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    config = get_config()
    return {
        "status": "ok",
        "streaming": streaming_active,
        "trainer_configured": config.get("tacx_mac_address", "XX:XX:XX:XX:XX:XX") != "XX:XX:XX:XX:XX:XX",
    }


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


@app.post("/api/joystick")
async def set_joystick(request: JoystickRequest):
    """Set virtual left stick position (-1 to 1 range)."""
    x = max(-1.0, min(1.0, request.x))
    y = max(-1.0, min(1.0, request.y))
    x_val = int((x + 1.0) / 2.0 * 65535)
    y_val = int((y + 1.0) / 2.0 * 65535)
    device.emit(uinput.ABS_X, x_val)
    device.emit(uinput.ABS_Y, y_val)
    return {"x": x, "y": y}


@app.post("/api/button")
async def press_button(request: ButtonRequest):
    """Press or release a virtual button on the controller."""
    code = _BUTTON_CODES.get(request.button)
    if not code:
        return {"status": "error", "message": f"Unknown button: {request.button}"}
    device.emit(code, 1 if request.pressed else 0)
    return {"status": "ok", "button": request.button, "pressed": request.pressed}


@app.get("/api/passthrough/devices")
async def passthrough_devices():
    """List available gamepad devices that can be used as passthrough sources."""
    return {"devices": list_controller_devices()}


@app.post("/api/passthrough/start")
async def passthrough_start(source_path: str | None = None):
    """Start passthrough from a source controller device to our uinput device.
    
    Optionally specify a source_path (e.g. /dev/input/event15).
    If omitted, auto-detects the Steam Deck controller.
    """
    return start_passthrough(source_path)


@app.post("/api/passthrough/stop")
async def passthrough_stop():
    """Stop the passthrough."""
    return stop_passthrough()


@app.get("/api/passthrough/status")
async def passthrough_status():
    """Get current passthrough status."""
    return get_passthrough_status()


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
        async with BleakClient(mac_address, timeout=20.0) as client:
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


async def stream_trainer_data(mac_address: str):
    """Background task that streams trainer data to the controller."""
    global streaming_active, streaming_message, last_power_data
    
    try:
        async with BleakClient(mac_address, timeout=20.0) as client:
            if not client.is_connected:
                await client.connect()
            
            streaming_message = f"Connected to {mac_address}"
            streaming_active = True
            
            trainer = CyclingPowerService(client)

            # Read config once at stream start
            cfg = get_config()
            mappings = cfg.get("mappings", [])
            max_watts = cfg.get("max_target_watts", 300)

            def power_handler(data):
                """Handle incoming power data from trainer (synchronous callback)."""
                global last_power_data, streaming_log
                try:
                    watts = data.instantaneous_power
                    cadence = getattr(data, 'crank_revolutions', 0)
                    now = time.time()
                    
                    last_power_data = {
                        "watts": watts,
                        "cadence": cadence,
                        "timestamp": now,
                    }
                    
                    streaming_log.append({
                        "time": now,
                        "watts": watts,
                        "cadence": cadence,
                    })
                    
                    apply_mappings(mappings, watts, cadence, 0, max_watts)
                except Exception as e:
                    print(f"Error in power handler: {e}")
            
            trainer.set_cycling_power_measurement_handler(power_handler)
            await trainer.enable_cycling_power_measurement_notifications()
            
            # Keep streaming until cancelled
            while streaming_active:
                await asyncio.sleep(0.1)
    
    except Exception as e:
        streaming_message = f"Stream error: {str(e)}"
    finally:
        streaming_active = False


@app.post("/api/start-streaming")
async def start_streaming():
    """Start streaming trainer data to the virtual controller."""
    global streaming_task, streaming_active, streaming_message
    
    if streaming_active:
        return {
            "status": "already_streaming",
            "message": streaming_message,
        }
    
    config = get_config()
    mac_address = config.get("tacx_mac_address", "XX:XX:XX:XX:XX:XX")
    
    if mac_address == "XX:XX:XX:XX:XX:XX":
        return {
            "status": "error",
            "message": "Tacx MAC address not configured",
        }
    
    try:
        streaming_task = asyncio.create_task(stream_trainer_data(mac_address))
        # Wait up to 20 seconds for BLE connection
        for _ in range(40):
            if streaming_active:
                return {
                    "status": "streaming",
                    "message": f"Streaming started on {mac_address}",
                }
            if streaming_task.done():
                break
            await asyncio.sleep(0.5)

        # If the task finished, surface its exception
        if streaming_task.done():
            exc = None
            try:
                exc = streaming_task.exception()
            except Exception as _:
                exc = None

            if exc:
                msg = str(exc) or repr(exc)
                return {
                    "status": "error",
                    "message": f"Background task failed: {msg}",
                }

        return {
            "status": "error",
            "message": streaming_message or "BLE connection timed out after 20s",
        }
    except Exception as e:
        streaming_active = False
        return {
            "status": "error",
            "message": str(e),
        }


@app.post("/api/stop-streaming")
async def stop_streaming():
    """Stop streaming trainer data."""
    global streaming_task, streaming_active
    
    if not streaming_active:
        return {
            "status": "idle",
            "message": "Not currently streaming",
        }
    
    try:
        streaming_active = False
        if streaming_task and not streaming_task.done():
            streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass
        
        return {
            "status": "stopped",
            "message": "Streaming stopped",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.get("/api/stream-status")
async def stream_status():
    """Get current streaming status."""
    return {
        "streaming": streaming_active,
        "message": streaming_message,
    }


@app.get("/api/stream-data")
async def stream_data():
    """Get current streaming data (power, cadence, etc)."""
    return last_power_data


@app.get("/api/stream-log")
async def stream_log_endpoint():
    """Get recent streaming log entries."""
    return list(streaming_log)
