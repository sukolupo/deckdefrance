import threading
import evdev
from evdev import InputDevice, ecodes
from .mapper import _EMIT_EVTS, device, _BUTTON_CODES

# Mapping from evdev event codes to our emit targets
_EVDEV_TO_TARGET = {
    ecodes.ABS_X: "left_stick_x",
    ecodes.ABS_Y: "left_stick_y",
    ecodes.ABS_RX: "right_stick_x",
    ecodes.ABS_RY: "right_stick_y",
    ecodes.ABS_Z: "left_trigger",
    ecodes.ABS_RZ: "right_trigger",
}

# Button codes (evdev BTN_* → our _BUTTON_CODES keys)
_EVDEV_BTN_TO_TARGET = {
    ecodes.BTN_SOUTH: "btn_a",
    ecodes.BTN_EAST: "btn_b",
    ecodes.BTN_NORTH: "btn_x",
    ecodes.BTN_WEST: "btn_y",
    ecodes.BTN_SELECT: "btn_select",
    ecodes.BTN_START: "btn_start",
    ecodes.BTN_MODE: "btn_mode",
}

# Known Steam controller vendor/product IDs
_STEAM_VENDORS = {0x28de}  # Valve
_STEAM_PRODUCTS = {0x11ff, 0x1205}  # Xbox 360 pad, Steam Controller
_TACX_VENDOR = 0x045e
_TACX_PRODUCT = 0x028e

# Passthrough state
_passthread: threading.Thread | None = None
_passthrough_active = False
_passthrough_source = ""
_passthrough_device_name = ""
_lock = threading.Lock()


def find_steam_controller() -> tuple[str, str] | None:
    """Find the Steam Deck virtual Xbox 360 controller event device.
    Prefers the standard Xbox 360 pad (product 0x11ff) over the raw Steam Controller.
    """
    found = []
    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            if dev.info.vendor in _STEAM_VENDORS and dev.info.product in _STEAM_PRODUCTS:
                found.append((path, dev.name, dev.info.product))
        except (PermissionError, OSError):
            continue
    found.sort(key=lambda x: 0 if x[2] == 0x11ff else 1)
    return (found[0][0], found[0][1]) if found else None


def list_controller_devices() -> list[dict]:
    """List all joystick/gamepad evdev devices usable as passthrough sources."""
    results = []
    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            if dev.info.vendor == _TACX_VENDOR and dev.info.product == _TACX_PRODUCT:
                continue
            caps = dev.capabilities()
            abs_codes = [c for c, _ in caps.get(ecodes.EV_ABS, [])]
            if ecodes.ABS_X in abs_codes or ecodes.ABS_Y in abs_codes:
                results.append({
                    "path": path,
                    "name": dev.name,
                    "vendor": f"0x{dev.info.vendor:04x}",
                    "product": f"0x{dev.info.product:04x}",
                    "phys": dev.phys,
                })
        except (PermissionError, OSError):
            continue
    return results


def _scale_stick(value: int, src_min: int, src_max: int) -> int:
    """Convert stick value from src range to 0-65535."""
    if src_max <= src_min:
        return 32768
    normalized = (value - src_min) / (src_max - src_min)
    return int(normalized * 65535)


def _scale_trigger(value: int, src_max: int) -> int:
    """Convert trigger value from 0-src_max to 0-255."""
    if src_max == 0:
        return 0
    return int((value / src_max) * 255)


def _forward_event(event, abs_info: dict):
    """Forward a single evdev event to our uinput device."""
    global device

    if event.type == ecodes.EV_ABS:
        target = _EVDEV_TO_TARGET.get(event.code)
        if not target:
            return

        info = abs_info.get(event.code, {"min": 0, "max": 255})
        src_min, src_max = info["min"], info["max"]

        if target in ("left_stick_x", "left_stick_y", "right_stick_x", "right_stick_y"):
            scaled = _scale_stick(event.value, src_min, src_max)
            device.emit(_EMIT_EVTS[target], scaled)

        elif target in ("left_trigger", "right_trigger"):
            scaled = _scale_trigger(event.value, src_max)
            device.emit(_EMIT_EVTS[target], scaled)

    elif event.type == ecodes.EV_KEY:
        btn_key = _EVDEV_BTN_TO_TARGET.get(event.code)
        if btn_key:
            device.emit(_BUTTON_CODES[btn_key], event.value)


def _open_source(path: str):
    """Open an evdev source device and cache its axis info."""
    source = InputDevice(path)
    abs_info = {}
    caps = source.capabilities()
    for abs_code, absinfo in caps.get(ecodes.EV_ABS, []):
        abs_info[abs_code] = {"min": absinfo.min, "max": absinfo.max}
    return source, abs_info


def _run_passthrough(source_path: str):
    """Thread: read events from source evdev device, emit to our uinput device.
    Automatically reconnects if the source device disappears (e.g. mode switch)."""
    global _passthrough_active, _passthrough_source, _passthrough_device_name, device

    with _lock:
        _passthrough_active = True
        _passthrough_source = source_path

    abs_info = {}
    source = None

    while True:
        with _lock:
            if not _passthrough_active:
                break

        # (Re)connect if needed
        if source is None:
            try:
                source, abs_info = _open_source(source_path)
                _passthrough_device_name = source.name
            except (FileNotFoundError, PermissionError, OSError):
                # Device not available yet — retry with auto-detect
                source_path = None
                found = find_steam_controller()
                if found:
                    source_path, dev_name = found
                    with _lock:
                        _passthrough_source = source_path
                    continue
                threading.Event().wait(1.0)
                continue

        # Read pending events
        try:
            for event in source.read():
                _forward_event(event, abs_info)
        except BlockingIOError:
            threading.Event().wait(0.001)
        except OSError:
            # Device disconnected — close and reconnect next iteration
            try:
                source.close()
            except Exception:
                pass
            source = None
            source_path = None
            threading.Event().wait(0.5)

    if source:
        try:
            source.close()
        except Exception:
            pass

    with _lock:
        _passthrough_active = False


def start_passthrough(source_path: str | None = None) -> dict:
    """Start the passthrough in a background thread."""
    global _passthread

    with _lock:
        if _passthrough_active:
            return {"status": "already_active", "source": _passthrough_source}

    if not source_path:
        found = find_steam_controller()
        if not found:
            return {"status": "error", "message": "No Steam Deck controller found"}
        source_path, dev_name = found

    _passthread = threading.Thread(
        target=_run_passthrough,
        args=(source_path,),
        daemon=True,
    )
    _passthread.start()
    return {"status": "started", "source": source_path}


def stop_passthrough() -> dict:
    """Stop the passthrough thread."""
    global _passthread, _passthrough_active

    with _lock:
        if not _passthrough_active:
            return {"status": "idle"}
        _passthrough_active = False

    if _passthread and _passthread.is_alive():
        _passthread.join(timeout=2.0)
    _passthread = None
    return {"status": "stopped"}


def get_passthrough_status() -> dict:
    """Get current passthrough status."""
    with _lock:
        return {
            "active": _passthrough_active,
            "source": _passthrough_source if _passthrough_active else None,
            "device_name": _passthrough_device_name if _passthrough_active else None,
        }
