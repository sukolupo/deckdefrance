"""OpenBikeControl controller input for the shared trainer virtual gamepad.

Connects to an OpenBikeControl (OBC) device over Bluetooth LE or over the
network (mDNS + TCP) and maps its button IDs onto the shared virtual gamepad,
so handlebar controllers work alongside the trainer mappings and merged
controllers.

Protocol: https://github.com/OpenBikeControl/openbikecontrol-protocol
"""

import asyncio
from typing import Any, Callable, Dict, List, Tuple

from bleak import BleakClient
from evdev import ecodes
from .mapper import emit, _BUTTON_CODES, _AXIS_CODES, _STICK_CENTER, _STICK_RANGE, _TRIGGER_RANGE

OBC_SERVICE_UUID = "d273f680-d548-419d-b9d1-fa0472345229"
OBC_BUTTON_STATE_UUID = "d273f681-d548-419d-b9d1-fa0472345229"
OBC_APP_INFO_UUID = "d273f683-d548-419d-b9d1-fa0472345229"
OBC_MDNS_SERVICE_TYPE = "_openbikecontrol._tcp.local."

OBC_APP_ID = "deckdefrance"

_MSG_BUTTON_STATE = 0x01
_MSG_DEVICE_STATUS = 0x02
_MSG_HAPTIC_FEEDBACK = 0x03
_MSG_APP_INFO = 0x04

# OBC button ID per mapping source name (see PROTOCOL.md → Button Mapping)
OBC_BUTTONS: Dict[str, int] = {
    "shift_up": 0x01,
    "shift_down": 0x02,
    "nav_up": 0x10,
    "nav_down": 0x11,
    "nav_left": 0x12,
    "nav_right": 0x13,
    "select": 0x14,
    "back": 0x15,
    "menu": 0x16,
    "home": 0x17,
    "steer_left": 0x18,
    "steer_right": 0x19,
    "brake": 0x1A,
    "steering_angle": 0x1B,
    "emote": 0x20,
    "increase_difficulty": 0x30,
    "decrease_difficulty": 0x31,
    "camera_view": 0x40,
    "power_up_1": 0x50,
    "power_up_2": 0x51,
    "power_up_3": 0x52,
}

# Sources that report an analog value instead of a press — applied on every update
_ANALOG_SOURCES = {"steering_angle", "brake"}

# Digital sources that push an axis target to its minimum instead of its maximum
_NEGATIVE_SOURCES = {"steer_left", "nav_left", "nav_up"}

# D-pad targets (name -> (axis code, value when pressed))
_DPAD_TARGETS: Dict[str, Tuple[int, int]] = {
    "dpad_up": (ecodes.ABS_HAT0Y, -1),
    "dpad_down": (ecodes.ABS_HAT0Y, 1),
    "dpad_left": (ecodes.ABS_HAT0X, -1),
    "dpad_right": (ecodes.ABS_HAT0X, 1),
}

_STEER_BUTTONS = {OBC_BUTTONS["steer_left"], OBC_BUTTONS["steer_right"]}
_SELECT_BUTTONS = {OBC_BUTTONS["select"], OBC_BUTTONS["back"]}


def _press_priority(button_id: int) -> int:
    """Lower wins. One physical press can send several OBC IDs at once (e.g.
    Shift Up + Increase Difficulty + Select); only the most specific one fires."""
    if 0x01 <= button_id <= 0x0F:
        return 0  # gear shifting
    if 0x30 <= button_id <= 0x3F:
        return 1  # training controls (difficulty)
    if button_id in _SELECT_BUTTONS:
        return 4  # select / back
    if 0x10 <= button_id <= 0x1F:
        return 2  # navigation / steering
    return 3


def _axis_value(code: int, fraction: float) -> int:
    """Scale -1..1 (sticks) or 0..1 (triggers) to our device's axis range."""
    if code in (ecodes.ABS_Z, ecodes.ABS_RZ):
        return int(max(0.0, min(1.0, fraction)) * _TRIGGER_RANGE)
    return int((max(-1.0, min(1.0, fraction)) + 1.0) / 2.0 * _STICK_RANGE)


def _axis_rest(code: int) -> int:
    return 0 if code in (ecodes.ABS_Z, ecodes.ABS_RZ) else _STICK_CENTER


def parse_button_state(data: bytes) -> List[Tuple[int, int]]:
    """[0x01, id1, state1, id2, state2, ...] -> [(id, state), ...]"""
    if len(data) < 3 or data[0] != _MSG_BUTTON_STATE:
        return []
    return [(data[i], data[i + 1]) for i in range(1, len(data) - 1, 2)]


def split_tcp_messages(data: bytes) -> List[bytes]:
    """Split a TCP read into OBC messages. Button state messages have no length
    field, so they run to the end of the read (as in the protocol's examples)."""
    messages = []
    i = 0
    while i < len(data):
        msg_type = data[i]
        if msg_type == _MSG_DEVICE_STATUS:
            messages.append(data[i:i + 3])
            i += 3
        elif msg_type == _MSG_HAPTIC_FEEDBACK:
            i += 4
        elif msg_type == _MSG_BUTTON_STATE:
            messages.append(data[i:])
            break
        else:
            break
    return messages


def encode_app_info(app_version: str, button_ids: List[int]) -> bytes:
    """App Information message, sent right after connecting."""
    app_id = OBC_APP_ID.encode("utf-8")[:32]
    version = app_version.encode("utf-8")[:32]
    data = bytearray([_MSG_APP_INFO, 0x01, len(app_id)])
    data.extend(app_id)
    data.append(len(version))
    data.extend(version)
    data.append(len(button_ids))
    data.extend(button_ids)
    return bytes(data)


def supported_button_ids(mappings: List[Dict[str, Any]]) -> List[int]:
    """OBC button IDs we act on, for the App Information message."""
    ids = []
    for mapping in mappings:
        button_id = OBC_BUTTONS.get(mapping.get("source", ""))
        if button_id is not None and mapping.get("target") and button_id not in ids:
            ids.append(button_id)
    return ids


class ObcButtonMapper:
    """Turns OBC button state messages into virtual gamepad events."""

    def __init__(self, mappings: List[Dict[str, Any]], write: Callable[[int, int], None] = emit):
        self._write = write
        self._digital: Dict[int, Tuple[str, str]] = {}
        self._analog: Dict[int, Dict[str, Any]] = {}
        for mapping in mappings:
            source = mapping.get("source", "")
            target = mapping.get("target", "")
            button_id = OBC_BUTTONS.get(source)
            if button_id is None or not self._known_target(target):
                continue
            if source in _ANALOG_SOURCES:
                # Analog sources drive an axis (stick, trigger or d-pad axis)
                if target in _AXIS_CODES:
                    self._analog[button_id] = mapping
            else:
                self._digital[button_id] = (source, target)
        self._pressed: set[int] = set()
        self._held: Dict[int, Tuple[str, str]] = {}
        self._angle_available = False

    def _steering_from_angle(self) -> bool:
        return self._angle_available and OBC_BUTTONS["steering_angle"] in self._analog

    @staticmethod
    def _known_target(target: str) -> bool:
        return target in _BUTTON_CODES or target in _AXIS_CODES or target in _DPAD_TARGETS

    def handle_message(self, data: bytes) -> None:
        self.handle_buttons(parse_button_state(data))

    def handle_buttons(self, buttons: List[Tuple[int, int]]) -> None:
        for button_id, state in buttons:
            if button_id in self._analog:
                self._apply_analog(button_id, state)

        newly_pressed = []
        for button_id, state in buttons:
            if button_id in self._analog:
                continue
            if state != 0x00:
                # Steer Left/Right presses are ignored while the device reports a steering angle
                if button_id in _STEER_BUTTONS and self._steering_from_angle():
                    continue
                if button_id not in self._pressed:
                    self._pressed.add(button_id)
                    if button_id in self._digital:
                        newly_pressed.append(button_id)
            else:
                self._pressed.discard(button_id)
                held = self._held.pop(button_id, None)
                if held:
                    self._apply_digital(held[0], held[1], False)

        if newly_pressed:
            winner = min(newly_pressed, key=_press_priority)
            source, target = self._digital[winner]
            self._held[winner] = (source, target)
            self._apply_digital(source, target, True)

    def release_all(self) -> None:
        """Release everything we hold — called on disconnect."""
        for source, target in self._held.values():
            self._apply_digital(source, target, False)
        self._held.clear()
        self._pressed.clear()
        for button_id in self._analog:
            self._apply_analog(button_id, 0x00)

    def _apply_digital(self, source: str, target: str, pressed: bool) -> None:
        if target in _BUTTON_CODES:
            self._write(_BUTTON_CODES[target], 1 if pressed else 0)
        elif target in _DPAD_TARGETS:
            code, value = _DPAD_TARGETS[target]
            self._write(code, value if pressed else 0)
        elif target in _AXIS_CODES:
            code = _AXIS_CODES[target]
            if not pressed:
                self._write(code, _axis_rest(code))
            elif code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
                self._write(code, -1 if source in _NEGATIVE_SOURCES else 1)
            else:
                self._write(code, _axis_value(code, -1.0 if source in _NEGATIVE_SOURCES else 1.0))

    def _apply_analog(self, button_id: int, state: int) -> None:
        mapping = self._analog[button_id]
        target = mapping["target"]
        if button_id == OBC_BUTTONS["steering_angle"]:
            if state in (0x01, 0xFF):
                return  # reserved, no-op
            if state == 0x00:
                # Angle unavailable — fall back to Steer Left/Right buttons
                self._angle_available = False
                fraction = 0.0
            else:
                self._angle_available = True
                max_angle = float(mapping.get("max_angle", 30))
                fraction = ((state - 0x80) * 0.5) / max_angle if max_angle > 0 else 0.0
        else:
            # Brake: 0x00 released, 0x01 full, 0x02-0xC9 = value - 1 percent
            percent = 0 if state == 0x00 else 100 if state == 0x01 else min(state - 1, 100)
            fraction = percent / 100.0

        code = _AXIS_CODES[target]
        if code in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
            self._write(code, 0 if abs(fraction) < 0.5 else (1 if fraction > 0 else -1))
        else:
            self._write(code, _axis_value(code, fraction))


# Connection state
_obc_task: asyncio.Task | None = None
_obc_active = False
_obc_connected = False
_obc_message = ""
_obc_transport = ""
_obc_address = ""


async def _run_ble(address: str, mapper: ObcButtonMapper, app_info: bytes):
    global _obc_connected, _obc_message

    disconnected = asyncio.Event()
    async with BleakClient(address, timeout=20.0, disconnected_callback=lambda _: disconnected.set()) as client:
        await client.start_notify(OBC_BUTTON_STATE_UUID, lambda _, data: mapper.handle_message(bytes(data)))
        try:
            await client.write_gatt_char(OBC_APP_INFO_UUID, app_info, response=False)
        except Exception as e:
            print(f"OBC app info write failed (optional characteristic): {e}")
        _obc_connected = True
        _obc_message = f"Connected to {address}"
        print(f"OBC connected to {address} (BLE)")
        while _obc_active and not disconnected.is_set():
            await asyncio.sleep(0.5)
        if _obc_active:
            raise ConnectionError("BLE link lost")


async def _run_tcp(address: str, mapper: ObcButtonMapper, app_info: bytes):
    global _obc_connected, _obc_message

    host, _, port = address.rpartition(":")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=10.0)
    try:
        writer.write(app_info)
        await writer.drain()
        _obc_connected = True
        _obc_message = f"Connected to {address}"
        print(f"OBC connected to {address} (TCP)")
        while _obc_active:
            data = await reader.read(256)
            if not data:
                raise ConnectionError("TCP connection closed")
            for message in split_tcp_messages(data):
                if message[0] == _MSG_BUTTON_STATE:
                    mapper.handle_message(message)
    finally:
        writer.close()


async def _run_obc(transport: str, address: str, mappings: List[Dict[str, Any]], app_version: str):
    """Connect to an OBC device and keep reconnecting until stopped."""
    global _obc_active, _obc_connected, _obc_message

    mapper = ObcButtonMapper(mappings)
    app_info = encode_app_info(app_version, supported_button_ids(mappings))
    run = _run_tcp if transport == "tcp" else _run_ble

    max_retries = 10
    retry_count = 0
    while _obc_active and retry_count < max_retries:
        try:
            await run(address, mapper, app_info)
            retry_count = 0
        except asyncio.CancelledError:
            break
        except Exception as e:
            retry_count += 1
            print(f"OBC error (retry {retry_count}/{max_retries}): {e}")
            _obc_message = f"Error: {e} (retry {retry_count}/{max_retries})"
        finally:
            _obc_connected = False
            mapper.release_all()
        if _obc_active and retry_count < max_retries:
            await asyncio.sleep(3)

    if retry_count >= max_retries:
        _obc_message = "Stopped — max retries reached"
    _obc_active = False


async def start_obc(transport: str, address: str, mappings: List[Dict[str, Any]], app_version: str) -> dict:
    """Start the OBC connection background task."""
    global _obc_task, _obc_active, _obc_message, _obc_transport, _obc_address

    if _obc_active:
        return {"status": "already_active", "transport": _obc_transport, "address": _obc_address}

    _obc_active = True
    _obc_message = "Connecting..."
    _obc_transport = transport
    _obc_address = address
    _obc_task = asyncio.create_task(_run_obc(transport, address, mappings, app_version))
    return {"status": "started", "transport": transport, "address": address}


async def stop_obc() -> dict:
    """Stop the OBC connection background task."""
    global _obc_task, _obc_active, _obc_message

    if not _obc_active:
        return {"status": "idle"}

    _obc_active = False
    if _obc_task:
        _obc_task.cancel()
        try:
            await _obc_task
        except asyncio.CancelledError:
            pass
        _obc_task = None
    _obc_message = ""
    return {"status": "stopped"}


def get_obc_status() -> dict:
    """Get current OBC connection status."""
    return {
        "active": _obc_active,
        "connected": _obc_connected,
        "message": _obc_message,
        "transport": _obc_transport if _obc_active else None,
        "address": _obc_address if _obc_active else None,
    }
