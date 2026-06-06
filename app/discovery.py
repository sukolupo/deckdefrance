import asyncio
from typing import List, Dict, Any
from bleak import BleakScanner


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
        scanner = BleakScanner()
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
        
        # Get discovered devices
        discovered = scanner.discovered_devices
        
        # Filter for Tacx devices
        for device in discovered:
            device_name = device.name or "Unknown"
            # Look for Tacx-related names
            if "tacx" in device_name.lower() or "trainer" in device_name.lower():
                devices.append({
                    "mac_address": device.address,
                    "name": device_name,
                    "rssi": device.rssi,  # Signal strength
                })
        
        # Sort by signal strength (strongest first)
        devices.sort(key=lambda x: x.get("rssi", 0), reverse=True)
        
    except Exception as e:
        print(f"Error discovering Tacx trainers: {e}")
    
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
        scanner = BleakScanner()
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
        
        # Get all discovered devices
        discovered = scanner.discovered_devices
        
        for device in discovered:
            device_name = device.name or "Unknown"
            devices.append({
                "mac_address": device.address,
                "name": device_name,
                "rssi": device.rssi,
            })
        
        # Sort by signal strength (strongest first)
        devices.sort(key=lambda x: x.get("rssi", 0), reverse=True)
        
    except Exception as e:
        print(f"Error discovering devices: {e}")
    
    return devices
