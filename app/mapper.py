from typing import Dict, Any, List

import asyncio
from bleak import BleakClient
from pycycling.cycling_power_service import CyclingPowerService
from evdev import UInput, ecodes

TACX_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"

# Button event codes
_BUTTON_CODES: Dict[str, int] = {
    "btn_a": ecodes.BTN_A,
    "btn_b": ecodes.BTN_B,
    "btn_x": ecodes.BTN_X,
    "btn_y": ecodes.BTN_Y,
    "btn_select": ecodes.BTN_SELECT,
    "btn_start": ecodes.BTN_START,
    "btn_mode": ecodes.BTN_MODE,
    "btn_lb": ecodes.BTN_TL,
    "btn_rb": ecodes.BTN_TR,
    "btn_l3": ecodes.BTN_THUMBL,
    "btn_r3": ecodes.BTN_THUMBR,
}

# Axis event codes
_AXIS_CODES: Dict[str, int] = {
    "left_stick_x":  ecodes.ABS_X,
    "left_stick_y":  ecodes.ABS_Y,
    "right_stick_x": ecodes.ABS_RX,
    "right_stick_y": ecodes.ABS_RY,
    "right_trigger": ecodes.ABS_RZ,
    "left_trigger":  ecodes.ABS_Z,
    "dpad_x": ecodes.ABS_HAT0X,
    "dpad_y": ecodes.ABS_HAT0Y,
}

# All targets (name -> event code)
_EMIT_EVTS: Dict[str, int] = {**_AXIS_CODES, **_BUTTON_CODES}

# evdev UInput capabilities
_CAP = {
    ecodes.EV_KEY: list(_BUTTON_CODES.values()),
    ecodes.EV_ABS: [
        (ecodes.ABS_X, (0, 0, 65535, 0, 0, 0)),
        (ecodes.ABS_Y, (0, 0, 65535, 0, 0, 0)),
        (ecodes.ABS_RX, (0, 0, 65535, 0, 0, 0)),
        (ecodes.ABS_RY, (0, 0, 65535, 0, 0, 0)),
        (ecodes.ABS_Z, (0, 0, 255, 0, 0, 0)),
        (ecodes.ABS_RZ, (0, 0, 255, 0, 0, 0)),
        (ecodes.ABS_HAT0X, (0, -1, 1, 0, 0, 0)),
        (ecodes.ABS_HAT0Y, (0, -1, 1, 0, 0, 0)),
    ],
}

# Create the shared virtual controller device
device = UInput(
    _CAP,
    name="Tacx Virtual Gamepad",
    vendor=0x045e,
    product=0x028e,
)

# Lookup: event code -> EV_KEY or EV_ABS
_CODE_TO_TYPE: Dict[int, int] = {}
for c in _BUTTON_CODES.values():
    _CODE_TO_TYPE[c] = ecodes.EV_KEY
for c in _AXIS_CODES.values():
    _CODE_TO_TYPE[c] = ecodes.EV_ABS

_BTN_CODES_SET = set(_BUTTON_CODES.values())


def emit(code: int, value: int):
    """Write an event to the shared virtual gamepad and sync."""
    ev_type = _CODE_TO_TYPE.get(code, ecodes.EV_ABS)
    device.write(ev_type, code, value)
    device.syn()


# Store last-committed button states so we only emit on change
_last_button_states: Dict[str, bool] = {}


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


_SOURCE_GETTERS = {
    "power": lambda p, c, r: p,
    "cadence": lambda p, c, r: c,
    "resistance": lambda p, c, r: r,
}

_TRIGGER_RANGE = 255
_STICK_RANGE = 65535
_STICK_CENTER = _STICK_RANGE // 2


def _scale(value: float, src_max: float, tgt_max: int) -> int:
    clamped = max(0.0, min(value, src_max))
    if src_max == 0:
        return 0
    return int((clamped / src_max) * tgt_max)


def _scale_stick_y(value: float, src_max: float) -> int:
    clamped = max(0.0, min(value, src_max))
    if src_max == 0:
        return _STICK_CENTER
    offset = int((clamped / src_max) * _STICK_CENTER)
    return _STICK_CENTER - offset


def apply_mappings(mappings: List[Dict[str, Any]], watts: float, cadence: float, resistance: float, max_watts: float):
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
                emit(_BUTTON_CODES[target], 1 if pressed else 0)
                _last_button_states[target] = pressed
        elif target in _EMIT_EVTS:
            src_max = max_watts if source == "power" else (200 if source == "cadence" else 10)
            if target in ("left_stick_y", "right_stick_y"):
                scaled = _scale_stick_y(value, src_max)
            elif target in ("left_stick_x", "right_stick_x"):
                scaled = _scale(value, src_max, _STICK_RANGE)
            else:
                scaled = _scale(value, src_max, _TRIGGER_RANGE)
            emit(_EMIT_EVTS[target], scaled)


def power_data_handler(data):
    watts = data.instantaneous_power
    print(f"Tacx Power: {watts}W")

    max_target_watts = 300
    trigger_value = int((min(watts, max_target_watts) / max_target_watts) * 255)
    emit(ecodes.ABS_Z, trigger_value)


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
