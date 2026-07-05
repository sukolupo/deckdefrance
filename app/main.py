from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import asyncio
import contextlib
import time
from collections import deque

from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
from evdev import ecodes
from .mapper import map_trainer_to_controller, apply_mappings, device, emit, _BUTTON_CODES
from .config import get_config, update_config, FTP_PRESETS
from .discovery import discover_trainers, discover_all_devices
from .merge import start_merge, stop_merge, get_merge_status, probe_device
from .passthrough import (
    start_passthrough,
    stop_passthrough,
    get_passthrough_status,
    get_passthrough_debug,
    list_controller_devices,
)

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


class DpadRequest(BaseModel):
    x: int = 0
    y: int = 0


class ButtonRequest(BaseModel):
    button: str
    pressed: bool


class ConfigRequest(BaseModel):
    trainer_mac_address: str | None = None
    max_target_watts: float | None = None
    cadence_threshold: float | None = None
    power_threshold_race: float | None = None
    power_threshold_button_a: float | None = None
    gear_multiplier: float | None = None
    auto_merge_device: str | None = None
    mappings: list[dict] | None = None


@app.get("/api/config/presets")
async def get_presets():
    """Get FTP-based power preset recommendations."""
    return FTP_PRESETS


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    cfg = get_config()
    merge = get_merge_status()
    return {
        "status": "ok",
        "streaming": streaming_active,
        "merge_active": merge.get("active", False),
        "auto_merge_device": cfg.get("auto_merge_device", ""),
        "trainer_configured": cfg.get("trainer_mac_address", "XX:XX:XX:XX:XX:XX") != "XX:XX:XX:XX:XX:XX",
    }


@app.get("/")
async def root():
    """Serve the web UI."""
    return FileResponse(static_dir / "index.html", media_type="text/html")


@app.get("/play")
async def play_page():
    """Serve the full-screen play page."""
    return FileResponse(static_dir / "play.html", media_type="text/html")


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
    mapping = map_trainer_to_controller(
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
    device.write(ecodes.EV_ABS, ecodes.ABS_X, x_val)
    device.write(ecodes.EV_ABS, ecodes.ABS_Y, y_val)
    device.syn()
    return {"x": x, "y": y}


@app.post("/api/dpad")
async def set_dpad(request: DpadRequest):
    """Set dpad position (-1, 0, or 1 per axis)."""
    x = max(-1, min(1, request.x))
    y = max(-1, min(1, request.y))
    device.write(ecodes.EV_ABS, ecodes.ABS_HAT0X, x)
    device.write(ecodes.EV_ABS, ecodes.ABS_HAT0Y, y)
    device.syn()
    return {"x": x, "y": y}


@app.post("/api/button")
async def press_button(request: ButtonRequest):
    """Press or release a virtual button on the controller."""
    code = _BUTTON_CODES.get(request.button)
    if not code:
        return {"status": "error", "message": f"Unknown button: {request.button}"}
    emit(code, 1 if request.pressed else 0)
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


@app.get("/api/passthrough/debug")
async def passthrough_debug():
    """Get passthrough debug info (event counts, source exists, etc)."""
    return get_passthrough_debug()


@app.get("/api/merge/devices")
async def merge_devices():
    """List gamepad evdev devices available for merging."""
    return {"devices": list_controller_devices()}


@app.get("/api/merge/status")
async def merge_status():
    """Get current merge status."""
    return get_merge_status()


@app.post("/api/merge/start")
async def merge_start(source_path: str):
    """Start merging a source controller into the shared virtual gamepad."""
    return await start_merge(source_path)


@app.post("/api/merge/probe")
async def merge_probe(source_path: str):
    """Watch a device for events for 3s to help identify which controller it is."""
    result = await probe_device(source_path)
    return result

@app.post("/api/merge/stop")
async def merge_stop():
    """Stop the merge."""
    return await stop_merge()


@app.post("/api/test-trainer")
async def test_trainer_connection():
    """Test connection to trainer."""
    config = get_config()
    mac_address = config.get("trainer_mac_address", "XX:XX:XX:XX:XX:XX")

    if mac_address == "XX:XX:XX:XX:XX:XX":
        return {
            "connected": False,
            "message": "Trainer MAC address not configured",
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


@app.post("/api/discover-trainer")
async def discover_trainer():
    """Discover trainers via Bluetooth scan."""
    try:
        devices = await discover_trainers(timeout=5)
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
    """Background task that streams trainer data to the controller.

    Automatically reconnects on BLE disconnection.
    """
    global streaming_active, streaming_message, last_power_data
    
    max_retries = 10
    retry_count = 0
    
    while streaming_active and retry_count < max_retries:
        try:
            async with BleakClient(mac_address, timeout=45.0) as client:
                print(f"BLE connected to {mac_address}")
                streaming_message = f"Connected to {mac_address}"
                streaming_active = True
                retry_count = 0
                
                trainer = CyclingPowerService(client)

                cfg = get_config()
                mappings = cfg.get("mappings", [])
                max_watts = cfg.get("max_target_watts", 300)

                prev_crank_revs = 0
                prev_crank_time = 0
                last_cadence = 0.0

                def power_handler(data):
                    global last_power_data, streaming_log
                    nonlocal prev_crank_revs, prev_crank_time, last_cadence
                    try:
                        watts = data.instantaneous_power
                        crank_revs = getattr(data, 'cumulative_crank_revs', None)
                        crank_time = getattr(data, 'last_crank_event_time', None)
                        cadence = 0
                        if crank_revs is not None and crank_time is not None:
                            if prev_crank_revs > 0 and crank_revs > prev_crank_revs:
                                delta_revs = crank_revs - prev_crank_revs
                                delta_time = crank_time - prev_crank_time
                                if delta_time > 0:
                                    cadence = (delta_revs * 60.0 * 1024.0) / delta_time
                                prev_crank_revs = crank_revs
                                prev_crank_time = crank_time
                            elif prev_crank_revs == 0:
                                prev_crank_revs = crank_revs
                                prev_crank_time = crank_time
                        last_cadence = cadence

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
                
                # Stay connected as long as streaming is active — no data timeout.
                # Poll is_connected to detect silent BLE drops.
                while streaming_active:
                    if not client.is_connected:
                        print("BLE link lost — raising ConnectionError")
                        raise ConnectionError("BLE link lost")
                    await asyncio.sleep(0.5)
        
        except asyncio.CancelledError:
            break
        except Exception as e:
            retry_count += 1
            import traceback
            print(f"Stream error (retry {retry_count}/{max_retries}):", traceback.format_exc())
            streaming_message = f"Stream error: {str(e)} (retry {retry_count}/{max_retries})"
            if retry_count < max_retries:
                for _ in range(6):
                    await asyncio.sleep(0.5)
                    if not streaming_active:
                        break
            else:
                streaming_message = "Stream stopped — max retries reached"
    
    streaming_active = False


async def _services_cached(mac_address: str) -> bool:
    """Check if BLE services are cached in BlueZ for this device."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "info", mac_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        return b"UUID:" in stdout
    except Exception:
        return False

async def _cache_services(mac_address: str) -> bool:
    """Cache BLE services via bluetoothctl connect + disconnect."""
    for attempt in range(3):
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "--", "connect", mac_address,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=30.0)
            await asyncio.sleep(2)
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "disconnect", mac_address,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            if await _services_cached(mac_address):
                print(f"Services cached for {mac_address}")
                return True
        except asyncio.TimeoutError:
            print(f"Service cache attempt {attempt + 1} timed out")
        await asyncio.sleep(3)
    print(f"Failed to cache services for {mac_address}")
    return False


@app.post("/api/start-streaming")
async def start_streaming():
    """Start streaming trainer data to the virtual controller (returns immediately, poll status)."""
    global streaming_task, streaming_active, streaming_message
    
    if streaming_active:
        return {
            "status": "streaming",
            "message": streaming_message,
        }
    
    config = get_config()
    mac_address = config.get("trainer_mac_address", "XX:XX:XX:XX:XX:XX")
    
    if mac_address == "XX:XX:XX:XX:XX:XX":
        return {
            "status": "error",
            "message": "Trainer MAC address not configured",
        }
    
    # Ensure BLE services are cached in BlueZ for reliable BleakClient connection
    if not await _services_cached(mac_address):
        print(f"Services not cached for {mac_address}, caching now...")
        cached = await _cache_services(mac_address)
        if not cached:
            return {
                "status": "error",
                "message": "Could not cache BLE services — ensure trainer is powered on and advertising",
            }
    
    streaming_active = True
    streaming_message = "Connecting..."
    streaming_task = asyncio.create_task(stream_trainer_data(mac_address))
    return {"status": "starting", "message": "Connecting to trainer..."}


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
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(streaming_task, timeout=5.0)
        
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
    is_connecting = streaming_message == "Connecting..."
    return {
        "streaming": streaming_active,
        "connecting": is_connecting,
        "message": streaming_message,
    }


@app.on_event("startup")
async def startup_auto_merge():
    """Auto-start merge if configured."""
    cfg = get_config()
    device_path = cfg.get("auto_merge_device", "")
    if device_path:
        print(f"Auto-starting merge on {device_path}")
        asyncio.create_task(auto_start_merge(device_path))


async def auto_start_merge(device_path: str):
    """Start merge in background with a small delay."""
    await asyncio.sleep(2)
    try:
        await start_merge(device_path)
        s = get_merge_status()
        if s.get("active"):
            print(f"Auto-merge started on {device_path}")
    except Exception as e:
        print(f"Auto-merge failed: {e}")


@app.get("/api/stream-data")
async def stream_data():
    """Get current streaming data (power, cadence, etc)."""
    return last_power_data


@app.get("/api/stream-log")
async def stream_log_endpoint():
    """Get recent streaming log entries."""
    return list(streaming_log)
