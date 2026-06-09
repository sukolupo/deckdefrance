"""Merge an external Bluetooth controller with our Tacx virtual gamepad.

Reads events from a source evdev device (e.g. a paired Xbox/PS controller)
and forwards them to the shared Tacx virtual gamepad device, so the game
sees one combined controller with both Tacx mappings and external inputs.
"""

import asyncio
from evdev import InputDevice, ecodes
from .mapper import device

_TARGET_ABS_RANGES = {
    ecodes.ABS_X: (0, 65535),
    ecodes.ABS_Y: (0, 65535),
    ecodes.ABS_RX: (0, 65535),
    ecodes.ABS_RY: (0, 65535),
    ecodes.ABS_Z: (0, 255),
    ecodes.ABS_RZ: (0, 255),
    ecodes.ABS_HAT0X: (-1, 1),
    ecodes.ABS_HAT0Y: (-1, 1),
}

# Merge state
_merge_task: asyncio.Task | None = None
_merge_active = False
_merge_source = ""
_merge_device_name = ""


def _scale(value: int, src_min: int, src_max: int, tgt_min: int, tgt_max: int) -> int:
    """Scale a value from source range to target range."""
    src_range = src_max - src_min
    if src_range == 0:
        return tgt_min
    tgt_range = tgt_max - tgt_min
    return int((value - src_min) / src_range * tgt_range) + tgt_min


async def _run_merge(source_path: str):
    """Read events from source device and forward them to the shared virtual gamepad,
    scaling axis values to match our device's declared ranges."""
    global _merge_active, _merge_source, _merge_device_name

    try:
        source = InputDevice(source_path)
    except (FileNotFoundError, PermissionError, OSError):
        _merge_active = False
        _merge_source = ""
        _merge_device_name = ""
        return

    _merge_device_name = source.name
    _merge_source = source_path

    # Read source device's absinfo to know its axis ranges
    caps = source.capabilities()
    source_abs_ranges: dict[int, tuple[int, int]] = {}
    for code, info in caps.get(ecodes.EV_ABS, []):
        source_abs_ranges[code] = (info.min, info.max)

    try:
        async for event in source.async_read_loop():
            if not _merge_active:
                break
            if event.type == 0:
                continue
            if event.type == ecodes.EV_ABS:
                tgt_range = _TARGET_ABS_RANGES.get(event.code)
                src_range = source_abs_ranges.get(event.code)
                if tgt_range and src_range:
                    scaled = _scale(event.value, src_range[0], src_range[1], tgt_range[0], tgt_range[1])
                    device.write(event.type, event.code, scaled)
                else:
                    device.write(event.type, event.code, event.value)
            else:
                device.write(event.type, event.code, event.value)
            device.syn()
    except Exception:
        pass
    finally:
        source.close()
        _merge_active = False


async def start_merge(source_path: str) -> dict:
    """Start forwarding a source device's events to the shared virtual gamepad."""
    global _merge_task, _merge_active, _merge_source

    if _merge_active:
        return {"status": "already_active", "source": _merge_source}

    _merge_active = True
    _merge_task = asyncio.create_task(_run_merge(source_path))
    return {"status": "started", "source": source_path}


async def stop_merge() -> dict:
    """Stop the merge background task."""
    global _merge_task, _merge_active

    if not _merge_active:
        return {"status": "idle"}

    _merge_active = False
    if _merge_task:
        _merge_task.cancel()
        try:
            await _merge_task
        except asyncio.CancelledError:
            pass
        _merge_task = None
    return {"status": "stopped"}


def get_merge_status() -> dict:
    """Get current merge status."""
    return {
        "active": _merge_active,
        "source": _merge_source if _merge_active else None,
        "device_name": _merge_device_name if _merge_active else None,
    }
