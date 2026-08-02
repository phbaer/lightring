"""Tests for SmartRow's dependency-free protocol helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "waterrower_ble"
    / "smartrow_protocol.py"
)
SPEC = importlib.util.spec_from_file_location("smartrow_protocol", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
key_for_challenge = MODULE.key_for_challenge
decode_frame = MODULE.decode_frame
decode_curve_frame = MODULE.decode_curve_frame


class SmartRowProtocolTest(unittest.TestCase):
    """Check the observed SmartRow key-lock calculation."""

    def test_generates_response_for_valid_challenge(self) -> None:
        subject = "KEYLOCK000001A"
        challenge = subject + f"{sum(map(ord, subject)):02X}"[-2:]
        self.assertEqual(key_for_challenge(challenge), "071c")

    def test_rejects_invalid_challenge(self) -> None:
        self.assertIsNone(key_for_challenge("KEYLOCK00001A00"))
        self.assertIsNone(key_for_challenge("too short"))

    def test_decodes_power_frame(self) -> None:
        subject = "c@@@@@  0   00"
        frame = subject + f"{sum(map(ord, subject)):02X}"[-2:]
        self.assertEqual(decode_frame(frame), {"power": 0, "average_power": 0.0})

    def test_decodes_curve_fragment(self) -> None:
        subject = "x@@@@@!\"#$%&('"
        frame = subject + f"{sum(map(ord, subject)):02X}"[-2:]
        self.assertEqual(decode_curve_frame(frame), ("x", [0, 16, 32, 48, 64, 80, 112, 96]))
