from typing import Dict, Any, List

import asyncio
from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
import uinput

TACX_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"  # Change to your Tacx MAC

# Available targets end users can map trainer metrics to
# Axes use range 0-255; joystick axes use center=128
TARGETS = {
    "left_stick_x":  uinput.ABS_X + (0, 255, 0, 0),
    "left_stick_y":  uinput.ABS_Y + (0, 255, 0, 0),
    "right_stick_x": uinput.ABS_RX + (0, 255, 0, 0),
    "right_stick_y": uinput.ABS_RY + (0, 255, 0, 0),
    "right_trigger": uinput.ABS_Z + (0, 255, 0, 0),
    "left_trigger":  uinput.ABS_RZ + (0, 255, 0, 0),
    "btn_a": uinput.BTN_A,
    "btn_b": uinput.BTN_B,
    "btn_x": uinput.BTN_X,
    "btn_y": uinput.BTN_Y,
}

events = list(TARGETS.values())

# Store last-committed button states so we only emit on change
_last_button_states: Dict[str, bool] = {}

# Create the virtual controller device named "Tacx Virtual Gamepad"
# Using Xbox 360 vendor/product IDs so Steam Input recognizes it as a gamepad
device = uinput.Device(
    events,
    name="Tacx Virtual Gamepad",
    vendor=0x045e,   # Microsoft
    product=0x028e,  # Xbox 360 Controller
    version=0x0110,
)


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


# Mapping from source names to value extractors
_SOURCE_GETTERS = {
    "power": lambda p, c, r: p,
    "cadence": lambda p, c, r: c,
    "resistance": lambda p, c, r: r,
}

# Mapping from target names to uinput event constants (axes need scaling info)
_TARGET_EVTS: Dict[str, Any] = {}
for name, evt in TARGETS.items():
    _TARGET_EVTS[name] = evt


def _scale(value: float, src_max: float, tgt_min: int, tgt_max: int) -> int:
    """Scale a source value (0–src_max) to a target range (tgt_min–tgt_max)."""
    clamped = max(0.0, min(value, src_max))
    if src_max == 0:
        return tgt_min
    return int(tgt_min + (clamped / src_max) * (tgt_max - tgt_min))


def apply_mappings(mappings: List[Dict[str, Any]], watts: float, cadence: float, resistance: float, max_watts: float):
    """Apply a list of mapping rules to the uinput device.
    
    Each mapping: { "source": "power"|"cadence"|"resistance", "target": "<target_name>" }
    Optional: "threshold" for buttons, "invert" for axes.
    """
    global _last_button_states

    for mapping in mappings:
        source = mapping.get("source")
        target = mapping.get("target")
        if not source or not target:
            continue

        getter = _SOURCE_GETTERS.get(source)
        if not getter:
            continue

        value = getter(watts, cadence, resistance)

        if target in ("btn_a", "btn_b", "btn_x", "btn_y"):
            # Button — emit press/release when crossing threshold
            threshold = mapping.get("threshold", 150)
            pressed = value > threshold
            prev = _last_button_states.get(target, False)
            if pressed != prev:
                evt = _TARGET_EVTS.get(target)
                if evt:
                    device.emit(evt, 1 if pressed else 0)
                _last_button_states[target] = pressed
        elif target in _TARGET_EVTS:
            # Axis — emit scaled value
            src_max = max_watts if source == "power" else (200 if source == "cadence" else 10)
            invert = mapping.get("invert", target in ("left_stick_y", "right_stick_y"))
            if invert:
                tgt_min, tgt_max = 255, 0
            else:
                tgt_min, tgt_max = 0, 255
            scaled = _scale(value, src_max, tgt_min, tgt_max)
            device.emit(_TARGET_EVTS[target], scaled)


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
        await trainer.enable_cycling_power_measurement_notifications()

        while True:
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(run())
