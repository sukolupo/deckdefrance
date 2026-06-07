from typing import Dict, Any, List

import asyncio
from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
import uinput

TACX_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"  # Change to your Tacx MAC

# uinput event codes are (type, code) tuples, e.g. (3, 2) for ABS_Z
# For device creation, axes need a range tuple appended: (type, code, min, max, fuzz, flat)
# For emit(), only the base (type, code) is used.

_AXIS_DESCRIPTORS: Dict[str, tuple] = {
    "left_stick_x":  uinput.ABS_X + (0, 255, 0, 0),
    "left_stick_y":  uinput.ABS_Y + (0, 255, 0, 0),
    "right_stick_x": uinput.ABS_RX + (0, 255, 0, 0),
    "right_stick_y": uinput.ABS_RY + (0, 255, 0, 0),
    "right_trigger": uinput.ABS_Z + (0, 255, 0, 0),
    "left_trigger":  uinput.ABS_RZ + (0, 255, 0, 0),
}

_BUTTON_CODES: Dict[str, tuple] = {
    "btn_a": uinput.BTN_A,
    "btn_b": uinput.BTN_B,
    "btn_x": uinput.BTN_X,
    "btn_y": uinput.BTN_Y,
}

# All targets (name -> base type+code tuple for emitting)
_EMIT_EVTS: Dict[str, tuple] = {
    "left_stick_x":  uinput.ABS_X,
    "left_stick_y":  uinput.ABS_Y,
    "right_stick_x": uinput.ABS_RX,
    "right_stick_y": uinput.ABS_RY,
    "right_trigger": uinput.ABS_Z,
    "left_trigger":  uinput.ABS_RZ,
    **_BUTTON_CODES,
}

events = list(_AXIS_DESCRIPTORS.values()) + list(_BUTTON_CODES.values())

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


def _scale(value: float, src_max: float, tgt_min: int, tgt_max: int) -> int:
    """Scale a source value (0–src_max) to a target range (tgt_min–tgt_max)."""
    clamped = max(0.0, min(value, src_max))
    if src_max == 0:
        return tgt_min
    return int(tgt_min + (clamped / src_max) * (tgt_max - tgt_min))


def _scale_centered(value: float, src_max: float, center: int = 128, max_offset: int = 128) -> int:
    """Scale source value so 0→center and src_max→center-offset.
    
    For Y-axes: 0W = stick at rest (center), full power = stick pushed up.
    """
    clamped = max(0.0, min(value, src_max))
    if src_max == 0:
        return center
    offset = int((clamped / src_max) * max_offset)
    return center - offset


def apply_mappings(mappings: List[Dict[str, Any]], watts: float, cadence: float, resistance: float, max_watts: float):
    """Apply a list of mapping rules to the uinput device.
    
    Each mapping: { "source": "power"|"cadence"|"resistance", "target": "<target_name>" }
    Optional: "threshold" for buttons.
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

        if target in _BUTTON_CODES:
            threshold = mapping.get("threshold", 150)
            pressed = value > threshold
            prev = _last_button_states.get(target, False)
            if pressed != prev:
                device.emit(_BUTTON_CODES[target], 1 if pressed else 0)
                _last_button_states[target] = pressed
        elif target in _EMIT_EVTS:
            src_max = max_watts if source == "power" else (200 if source == "cadence" else 10)
            if target in ("left_stick_y", "right_stick_y"):
                # Y-axes: center at 128, push up as power increases
                scaled = _scale_centered(value, src_max, 128, 128)
            else:
                # Other axes: 0→255 linear
                scaled = _scale(value, src_max, 0, 255)
            device.emit(_EMIT_EVTS[target], scaled)


def power_data_handler(data):
    watts = data.instantaneous_power
    print(f"Tacx Power: {watts}W")

    max_target_watts = 300
    trigger_value = int((min(watts, max_target_watts) / max_target_watts) * 255)
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
