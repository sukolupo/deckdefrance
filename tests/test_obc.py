"""Tests for the OpenBikeControl button mapping.

evdev/uinput only exist on Linux, so a stub stands in for them here — the tests
check which gamepad events would be written, not the uinput device itself.

Run: python -m unittest discover tests
"""

import sys
import types
import unittest

_codes = {
    "BTN_A": 304, "BTN_B": 305, "BTN_X": 307, "BTN_Y": 308,
    "BTN_TL": 310, "BTN_TR": 311, "BTN_SELECT": 314, "BTN_START": 315,
    "BTN_MODE": 316, "BTN_THUMBL": 317, "BTN_THUMBR": 318,
    "ABS_X": 0, "ABS_Y": 1, "ABS_Z": 2, "ABS_RX": 3, "ABS_RY": 4, "ABS_RZ": 5,
    "ABS_HAT0X": 16, "ABS_HAT0Y": 17, "EV_KEY": 1, "EV_ABS": 3,
}
if "evdev" not in sys.modules:
    evdev_stub = types.ModuleType("evdev")
    evdev_stub.ecodes = types.SimpleNamespace(**_codes)
    evdev_stub.UInput = lambda *args, **kwargs: types.SimpleNamespace(write=lambda *a: None, syn=lambda: None)
    evdev_stub.InputDevice = object
    sys.modules["evdev"] = evdev_stub

from evdev import ecodes  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402
from app.obc import (  # noqa: E402
    ObcButtonMapper,
    encode_app_info,
    parse_button_state,
    split_tcp_messages,
    supported_button_ids,
)

SHIFT_UP, SHIFT_DOWN = 0x01, 0x02
NAV_UP, NAV_LEFT, SELECT, BACK = 0x10, 0x12, 0x14, 0x15
STEER_LEFT, STEER_RIGHT, BRAKE, ANGLE = 0x18, 0x19, 0x1A, 0x1B
INC_DIFF, DEC_DIFF = 0x30, 0x31


def msg(*pairs):
    data = bytearray([0x01])
    for button_id, state in pairs:
        data.extend([button_id, state])
    return bytes(data)


class MapperTestCase(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.mapper = ObcButtonMapper(DEFAULT_CONFIG["obc_mappings"], write=lambda c, v: self.events.append((c, v)))

    def send(self, *pairs):
        self.events.clear()
        self.mapper.handle_message(msg(*pairs))
        return list(self.events)


class TestCombinedPress(MapperTestCase):
    def test_shift_difficulty_select_fires_shift_only(self):
        self.assertEqual(self.send((SHIFT_UP, 1), (INC_DIFF, 1), (SELECT, 1)), [(ecodes.BTN_TR, 1)])
        self.assertEqual(self.send((SHIFT_UP, 0), (INC_DIFF, 0), (SELECT, 0)), [(ecodes.BTN_TR, 0)])

    def test_order_in_message_does_not_matter(self):
        self.assertEqual(self.send((SELECT, 1), (INC_DIFF, 1), (SHIFT_UP, 1)), [(ecodes.BTN_TR, 1)])

    def test_difficulty_beats_navigation_and_select(self):
        self.assertEqual(self.send((NAV_UP, 1), (SELECT, 1), (DEC_DIFF, 1)), [(ecodes.BTN_TL, 1)])

    def test_navigation_beats_select(self):
        self.assertEqual(self.send((SELECT, 1), (NAV_LEFT, 1)), [(ecodes.ABS_HAT0X, -1)])
        self.assertEqual(self.send((SELECT, 0), (NAV_LEFT, 0)), [(ecodes.ABS_HAT0X, 0)])

    def test_select_alone(self):
        self.assertEqual(self.send((SELECT, 1)), [(ecodes.BTN_A, 1)])
        self.assertEqual(self.send((SELECT, 0)), [(ecodes.BTN_A, 0)])

    def test_unmapped_ids_are_ignored(self):
        mapper = ObcButtonMapper([{"source": "select", "target": "btn_a"}], write=lambda c, v: self.events.append((c, v)))
        mapper.handle_message(msg((SHIFT_UP, 1), (SELECT, 1)))
        self.assertEqual(self.events, [(ecodes.BTN_A, 1)])

    def test_partial_release_keeps_winner_held(self):
        self.send((SHIFT_UP, 1), (SELECT, 1))
        self.assertEqual(self.send((SELECT, 0)), [])
        self.assertEqual(self.send((SHIFT_UP, 0)), [(ecodes.BTN_TR, 0)])

    def test_second_button_while_first_held(self):
        self.send((SHIFT_UP, 1), (INC_DIFF, 1))
        self.assertEqual(self.send((SHIFT_UP, 1), (INC_DIFF, 1), (BACK, 1)), [(ecodes.BTN_B, 1)])

    def test_repeated_pressed_state_does_not_repeat(self):
        self.send((SHIFT_DOWN, 1))
        self.assertEqual(self.send((SHIFT_DOWN, 1)), [])

    def test_release_without_press_is_ignored(self):
        self.assertEqual(self.send((SHIFT_UP, 0), (SELECT, 0)), [])

    def test_release_all_on_disconnect(self):
        self.send((SHIFT_UP, 1), (SELECT, 1))
        self.events.clear()
        self.mapper.release_all()
        self.assertIn((ecodes.BTN_TR, 0), self.events)
        self.assertNotIn((ecodes.BTN_A, 0), self.events)


class TestSteering(MapperTestCase):
    def test_steer_buttons_deflect_left_stick(self):
        self.assertEqual(self.send((STEER_LEFT, 1)), [(ecodes.ABS_X, 0)])
        self.assertEqual(self.send((STEER_LEFT, 0)), [(ecodes.ABS_X, 32767)])
        self.assertEqual(self.send((STEER_RIGHT, 1)), [(ecodes.ABS_X, 65535)])

    def test_steering_angle_is_proportional(self):
        self.assertEqual(self.send((ANGLE, 0x80)), [(ecodes.ABS_X, 32767)])
        # 0x94 = +10°, 30° full lock -> one third right
        self.assertEqual(self.send((ANGLE, 0x94)), [(ecodes.ABS_X, 43690)])
        # 0x02 = -63°, clamped
        self.assertEqual(self.send((ANGLE, 0x02)), [(ecodes.ABS_X, 0)])

    def test_steer_buttons_ignored_while_angle_available(self):
        self.assertEqual(self.send((ANGLE, 0x94), (STEER_RIGHT, 1)), [(ecodes.ABS_X, 43690)])
        self.assertEqual(self.send((ANGLE, 0x80), (STEER_RIGHT, 0)), [(ecodes.ABS_X, 32767)])

    def test_angle_unavailable_recenters_and_falls_back_to_buttons(self):
        self.send((ANGLE, 0x94))
        self.assertEqual(self.send((ANGLE, 0x00)), [(ecodes.ABS_X, 32767)])
        self.assertEqual(self.send((STEER_LEFT, 1)), [(ecodes.ABS_X, 0)])

    def test_angle_reserved_values_are_noop(self):
        self.assertEqual(self.send((ANGLE, 0x01)), [])
        self.assertEqual(self.send((ANGLE, 0xFF)), [])

    def test_angle_does_not_block_a_button_press(self):
        self.assertEqual(self.send((ANGLE, 0x80), (SHIFT_UP, 1)), [(ecodes.ABS_X, 32767), (ecodes.BTN_TR, 1)])


class TestBrake(MapperTestCase):
    def test_brake_maps_to_left_trigger(self):
        self.assertEqual(self.send((BRAKE, 0x01)), [(ecodes.ABS_Z, 255)])
        self.assertEqual(self.send((BRAKE, 0x33)), [(ecodes.ABS_Z, 127)])  # 50%
        self.assertEqual(self.send((BRAKE, 0xC9)), [(ecodes.ABS_Z, 255)])  # 200% clamped
        self.assertEqual(self.send((BRAKE, 0x00)), [(ecodes.ABS_Z, 0)])


class TestProtocol(unittest.TestCase):
    def test_parse_button_state(self):
        self.assertEqual(parse_button_state(bytes([0x01, 0x01, 0x01, 0x30, 0x01, 0x14, 0x01])),
                         [(0x01, 1), (0x30, 1), (0x14, 1)])
        self.assertEqual(parse_button_state(bytes([0x01, 0x01])), [])
        self.assertEqual(parse_button_state(bytes([0x02, 0x50, 0x01])), [])

    def test_split_tcp_messages(self):
        self.assertEqual(split_tcp_messages(bytes([0x02, 0x50, 0x01, 0x01, 0x01, 0x01])),
                         [bytes([0x02, 0x50, 0x01]), bytes([0x01, 0x01, 0x01])])
        self.assertEqual(split_tcp_messages(bytes([0x03, 0x01, 0x00, 0x00, 0x01, 0x14, 0x00])),
                         [bytes([0x01, 0x14, 0x00])])

    def test_app_info_format(self):
        data = encode_app_info("0.1.0", [0x01, 0x02])
        self.assertEqual(data, bytes([0x04, 0x01, 12]) + b"deckdefrance" + bytes([5]) + b"0.1.0" + bytes([2, 0x01, 0x02]))

    def test_supported_buttons_from_default_mappings(self):
        ids = supported_button_ids(DEFAULT_CONFIG["obc_mappings"])
        self.assertEqual(ids, [0x01, 0x02, 0x30, 0x31, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15,
                               0x16, 0x40, 0x18, 0x19, 0x1B, 0x1A])


if __name__ == "__main__":
    unittest.main()
