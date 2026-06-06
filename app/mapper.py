from typing import Dict, Any

import asyncio
from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
import uinput

TACX_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"  # Change to your Tacx MAC

# Define a standard Xbox controller layout for Linux uinput
# ABS_Z represents the Right Trigger on an Xbox pad
events = [
    uinput.BTN_JOYSTICK,
    uinput.BTN_A,
    uinput.BTN_B,
    uinput.BTN_X,
    uinput.BTN_Y,
    uinput.ABS_Z + (0, 255, 0, 0),  # Right Trigger: Min=0, Max=255
]

# Create the virtual controller device named "Tacx Virtual Gamepad"
device = uinput.Device(events, name="Tacx Virtual Gamepad")


def map_tacx_to_controller(trainer_power: float, cadence: float, resistance: float) -> Dict[str, Any]:
    """Convert TacX trainer metrics into a Tour de France controller mapping."""
    cycling_power = trainer_power
    gear = min(10, max(1, int(resistance * 2)))

    return {
        "cycling_power": cycling_power,
        "button_a": trainer_power > 250,
        "button_b": cadence > 95,
        "gear": gear,
        "mode": "race" if trainer_power > 150 else "cruise",
    }


def power_data_handler(data):
    watts = data.instantaneous_power
    print(f"Tacx Power: {watts}W")

    max_target_watts = 300
    trigger_value = int((min(watts, max_target_watts) / max_target_watts) * 255)

    # Send the analog trigger event as a proxy for cycling power
    device.emit(uinput.ABS_Z, trigger_value)


async def run():
    async with BleakClient(TACX_MAC_ADDRESS) as client:
        print("Virtual Gamepad Initialized. Connected to Tacx!")
        trainer = CyclingPowerService(client)
        trainer.set_cycling_power_measurement_handler(power_data_handler)
        await trainer.start_cycling_power_measurement()

        while True:
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(run())