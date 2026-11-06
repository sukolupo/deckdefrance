import asyncio
from typing import List, Dict, Any
from bleak import BleakScanner
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from .obc import OBC_SERVICE_UUID, OBC_MDNS_SERVICE_TYPE


def _get_device_rssi(device: Any) -> int | None:
    """Return RSSI value if available."""
    if hasattr(device, "rssi"):
        return getattr(device, "rssi")
    if hasattr(device, "metadata") and isinstance(device.metadata, dict):
        return device.metadata.get("rssi")
    return None


async def discover_trainers(timeout: int = 5) -> List[Dict[str, Any]]:
    """
    Scan for trainers using Bluetooth Low Energy (BLE).
    
    Args:
        timeout: Scan duration in seconds (default: 5)
    
    Returns:
        List of discovered trainers with their MAC addresses and names
    """
    devices = []
    
    try:
        discovered = await BleakScanner.discover(timeout=timeout)

        # Filter for trainer devices
        for device in discovered:
            device_name = device.name or "Unknown"
            if "trainer" in device_name.lower():
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
    Scan for all Bluetooth devices.
    
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


async def _discover_obc_ble(timeout: int) -> List[Dict[str, Any]]:
    """BLE devices advertising the OpenBikeControl service UUID."""
    devices = []
    discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for device, adv in discovered.values():
        if OBC_SERVICE_UUID not in [uuid.lower() for uuid in adv.service_uuids]:
            continue
        devices.append({
            "transport": "ble",
            "address": device.address,
            "name": adv.local_name or device.name or "Unknown",
            "rssi": adv.rssi,
        })
    return devices


async def _discover_obc_mdns(timeout: int) -> List[Dict[str, Any]]:
    """Network devices advertising the OpenBikeControl mDNS service."""
    devices = []
    names: List[str] = []

    def on_change(zeroconf, service_type, name, state_change):
        if name not in names:
            names.append(name)

    aiozc = AsyncZeroconf(ip_version=IPVersion.V4Only)
    try:
        browser = AsyncServiceBrowser(aiozc.zeroconf, [OBC_MDNS_SERVICE_TYPE], handlers=[on_change])
        await asyncio.sleep(timeout)
        await browser.async_cancel()
        for name in names:
            info = AsyncServiceInfo(OBC_MDNS_SERVICE_TYPE, name)
            if not await info.async_request(aiozc.zeroconf, 3000):
                continue
            addresses = info.parsed_addresses(IPVersion.V4Only)
            if not addresses or not info.port:
                continue
            props = {k.decode(): (v or b"").decode(errors="replace") for k, v in info.properties.items()}
            devices.append({
                "transport": "tcp",
                "address": f"{addresses[0]}:{info.port}",
                "name": props.get("name") or name.removesuffix("." + OBC_MDNS_SERVICE_TYPE),
                "rssi": None,
            })
    finally:
        await aiozc.async_close()
    return devices


async def discover_obc_devices(timeout: int = 5) -> List[Dict[str, Any]]:
    """
    Scan for OpenBikeControl devices over BLE and mDNS at the same time.

    Args:
        timeout: Scan duration in seconds (default: 5)

    Returns:
        List of discovered OBC devices with transport, address and name
    """
    results = await asyncio.gather(
        _discover_obc_ble(timeout),
        _discover_obc_mdns(timeout),
        return_exceptions=True,
    )
    devices = []
    errors = []
    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
        else:
            devices.extend(result)
    if errors and not devices:
        raise RuntimeError(f"OpenBikeControl discovery failed: {'; '.join(errors)}")

    devices.sort(key=lambda x: x.get("rssi") if x.get("rssi") is not None else -999, reverse=True)
    return devices
