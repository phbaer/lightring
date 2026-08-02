"""Tests for the dependency-free LightRing wire protocol."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = ROOT / "custom_components" / "waterrower_ble"
PACKAGE_NAME = "lightring_test_component"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(COMPONENT_PATH)]
sys.modules[PACKAGE_NAME] = package


def _load_module(module: str):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE_NAME}.{module}", COMPONENT_PATH / f"{module}.py"
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


protocol = _load_module("protocol")
effects = _load_module("effects")


class SolidColorCommandTest(unittest.TestCase):
    """Validate the documented command byte order."""

    def test_encodes_rgb_in_lightring_wire_order(self) -> None:
        """The device expects green before red."""
        self.assertEqual(protocol.solid_color_command(255, 0, 0), b"\x00\x00\xff\x00")
        self.assertEqual(protocol.solid_color_command(1, 2, 3), b"\x00\x02\x01\x03")

    def test_rejects_out_of_range_components(self) -> None:
        """Invalid component values must never form a BLE command."""
        for values in ((-1, 0, 0), (0, 256, 0), (0, 0, 999)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                protocol.solid_color_command(*values)


class PixelFrameCommandTest(unittest.TestCase):
    """Validate the independently-addressable LED frame commands."""

    def test_encodes_52_pixels_and_zero_pads_unused_leds(self) -> None:
        """Frames must preserve RGB input order while using the G/R/B wire order."""
        command = protocol.pixel_frame_command(0x1234, [(255, 0, 0), (0, 255, 3)])

        self.assertEqual(len(command), 3 + 3 * protocol.LED_COUNT)
        self.assertEqual(command[:9], b"\x02\x34\x12\x00\xff\x00\xff\x00\x03")
        self.assertEqual(command[9:], bytes(3 * (protocol.LED_COUNT - 2)))

    def test_rejects_more_than_the_ring_led_count(self) -> None:
        """An oversized frame must never be sent to the ring."""
        pixels = [(0, 0, 0)] * (protocol.LED_COUNT + 1)
        with self.assertRaises(ValueError):
            protocol.pixel_frame_command(0, pixels)

    def test_encodes_vendor_start_command(self) -> None:
        """The uploaded frame is selected with a one-byte slot command."""
        self.assertEqual(
            protocol.start_frame_command(7, mode_flag=1, duration_ms=500),
            b"\x03\x07\x01\xf4\x01",
        )


class TimelineCommandTest(unittest.TestCase):
    """Validate the observed device-side animation timeline encoder."""

    def test_encodes_two_fixed_26_record_timeline_packets(self) -> None:
        """A complete animation is written as 0x05 then 0x0D."""
        frames = [
            protocol.TimelineFrame(40, frame_index=0x1234, rotation_offset=index)
            for index in range(protocol.LED_COUNT)
        ]

        first, second = protocol.timeline_commands(7, frames)

        self.assertEqual(len(first), 1 + 26 * 8 + 1)
        self.assertEqual(len(second), 1 + 26 * 8 + 1)
        self.assertEqual(first[:9], b"\x05\x28\x00\x34\x12\x00\xff\xff\xff")
        self.assertEqual(second[:9], b"\x0d\x28\x00\x34\x12\x1a\xff\xff\xff")
        self.assertEqual(first[-1], 7)
        self.assertEqual(second[-1], 7)

    def test_rejects_incomplete_or_invalid_timeline(self) -> None:
        """Never send partial or out-of-range native animation data."""
        frame = protocol.TimelineFrame(40, frame_index=0, rotation_offset=0)
        with self.assertRaises(ValueError):
            protocol.timeline_commands(1, [frame] * 51)
        with self.assertRaises(ValueError):
            protocol.timeline_commands(1, [protocol.TimelineFrame(40, 0, 256)] * 52)


class NativeEffectTest(unittest.TestCase):
    """Validate the extensible dependency-free native effect registry."""

    def test_every_registered_effect_has_a_safe_complete_timeline(self) -> None:
        """Effect definitions must always be directly writable to the ring."""
        self.assertEqual(
            effects.effect_names(),
            ("Rainbow", "Chase", "Breathe", "Water Reflections", "Aurora"),
        )
        for name in effects.effect_names():
            with self.subTest(name=name):
                effect = effects.build_effect(name)
                self.assertEqual(len(effect.pixels), protocol.LED_COUNT)
                self.assertEqual(len(effect.timeline), protocol.LED_COUNT)
                self.assertTrue(1 <= effect.animation_id <= 255)
                self.assertTrue(
                    all(0 <= component <= 255 for pixel in effect.pixels for component in pixel)
                )
                self.assertTrue(
                    all(
                        0 <= frame.duration_ms <= 65535
                        and 0 <= frame.frame_index <= 65535
                        and 0 <= frame.rotation_offset <= 255
                        and 0 <= frame.red_gain <= 255
                        and 0 <= frame.green_gain <= 255
                        and 0 <= frame.blue_gain <= 255
                        for frame in effect.timeline
                    )
                )

    def test_colour_effects_honor_the_current_rgb_and_brightness(self) -> None:
        """Chase and Breathe use the light entity's selected colour."""
        expected = (50, 25, 12)
        chase = effects.build_effect("Chase", (200, 100, 50), 64)
        breathe = effects.build_effect("Breathe", (200, 100, 50), 64)
        self.assertEqual(chase.pixels[:3], (expected, expected, expected))
        self.assertEqual(chase.pixels[3], (0, 0, 0))
        self.assertEqual(breathe.pixels, (expected,) * protocol.LED_COUNT)

    def test_rejects_unknown_effect_and_invalid_colour(self) -> None:
        """An invalid external definition request cannot produce BLE data."""
        with self.assertRaises(ValueError):
            effects.build_effect("Unknown")
        with self.assertRaises(ValueError):
            effects.build_effect("Chase", (0, 0, 256))
