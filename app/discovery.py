import asyncio
from typing import List, Dict, Any
from bleak import BleakScanner


def _get_device_rssi(device: Any) -> int | None:
    """Return RSSI value if available."""
    if hasattr(device, "rssi"):
        return getattr(device, "rssi")
    if hasattr(device, "metadata") and isinstance(device.metadata, dict):
        return device.metadata.get("rssi")
    return None


async def discover_tacx_trainers(timeout: int = 5) -> List[Dict[str, Any]]:
    """
    Scan for Tacx trainers using Bluetooth Low Energy (BLE).
    
    Args:
        timeout: Scan duration in seconds (default: 5)
    
    Returns:
        List of discovered Tacx trainers with their MAC addresses and names
    """
    devices = []
    
    try:
        discovered = await BleakScanner.discover(timeout=timeout)

        # Filter for Tacx devices
        for device in discovered:
            device_name = device.name or "Unknown"
            if "tacx" in device_name.lower() or "trainer" in device_name.lower():
                devices.append({
                    "mac_address": device.address,
                    "name": device_name,
                    "rssi": _get_device_rssi(device),
                })

        devices.sort(key=lambda x: x.get("rssi") if x.get("rssi") is not None else -999, reverse=True)

    except Exception as e:
        raise RuntimeError(f"Bluetooth discovery failed: {e}")

    return devices


async def discover_all_devices(timeout: int = 5) -> List[Dict[str, Any]]:
    """
    Scan for all Bluetooth devices (not just Tacx).
    
    Args:
        timeout: Scan duration in seconds (default: 5)
    
    Returns:
        List of all discovered Bluetooth devices
    """
    devices = []
    
    try:
        discovered = await BleakScanner.discover(timeout=timeout)

        for device in discovered:
            device_name = device.name or "Unknown"
            devices.append({
                "mac_address": device.address,
                "name": device_name,
                "rssi": _get_device_rssi(device),
            })

        devices.sort(key=lambda x: x.get("rssi") if x.get("rssi") is not None else -999, reverse=True)

    except Exception as e:
        raise RuntimeError(f"Bluetooth discovery failed: {e}")

    return devices
