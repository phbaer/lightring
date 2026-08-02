"""Declarative, dependency-free device-side LightRing effects."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
import math
from typing import Callable

from .protocol import LED_COUNT, TimelineFrame

NATIVE_FRAME_ID = 0


@dataclass(frozen=True)
class NativeEffect:
    """The single frame and 52 timeline records required by a native effect."""

    animation_id: int
    pixels: tuple[tuple[int, int, int], ...]
    timeline: tuple[TimelineFrame, ...]


EffectBuilder = Callable[[tuple[int, int, int], int], NativeEffect]


def effect_names() -> tuple[str, ...]:
    """Return effect names in the order presented by Home Assistant."""
    return tuple(EFFECT_BUILDERS)


def build_effect(
    name: str, rgb_color: tuple[int, int, int] = (255, 255, 255), brightness: int = 255
) -> NativeEffect:
    """Build a named native effect, validating caller-controlled colour values."""
    _validate_color(rgb_color, brightness)
    try:
        return EFFECT_BUILDERS[name](rgb_color, brightness)
    except KeyError as err:
        raise ValueError(f"Unsupported LightRing effect: {name}") from err


def _rainbow(_: tuple[int, int, int], __: int) -> NativeEffect:
    pixels = tuple(
        tuple(round(value * 255) for value in colorsys.hsv_to_rgb(index / LED_COUNT, 1, 1))
        for index in range(LED_COUNT)
    )
    return NativeEffect(1, pixels, _rotation_timeline(40))


def _chase(rgb_color: tuple[int, int, int], brightness: int) -> NativeEffect:
    color = _scaled_color(rgb_color, brightness)
    pixels = tuple(color if index < 3 else (0, 0, 0) for index in range(LED_COUNT))
    return NativeEffect(2, pixels, _rotation_timeline(40))


def _breathe(rgb_color: tuple[int, int, int], brightness: int) -> NativeEffect:
    color = _scaled_color(rgb_color, brightness)
    timeline = tuple(
        TimelineFrame(
            duration_ms=40,
            frame_index=NATIVE_FRAME_ID,
            rotation_offset=0,
            red_gain=_breathing_gain(index),
            green_gain=_breathing_gain(index),
            blue_gain=_breathing_gain(index),
        )
        for index in range(LED_COUNT)
    )
    return NativeEffect(3, (color,) * LED_COUNT, timeline)


def _water_reflections(_: tuple[int, int, int], __: int) -> NativeEffect:
    pixels = []
    timeline = []
    for index in range(LED_COUNT):
        phase = 2 * math.pi * index / LED_COUNT
        broad_wave = (math.sin(phase * 2) + 1) / 2
        ripple = (math.sin(phase * 7 + 0.8) + 1) / 2
        pixels.append(
            (
                round(3 + 12 * ripple),
                round(20 + 80 * broad_wave + 25 * ripple),
                round(55 + 115 * broad_wave + 45 * ripple),
            )
        )
        timeline.append(
            TimelineFrame(
                duration_ms=65,
                frame_index=NATIVE_FRAME_ID,
                rotation_offset=index,
                red_gain=_water_shimmer_gain(index, 0.0),
                green_gain=_water_shimmer_gain(index, 0.7),
                blue_gain=_water_shimmer_gain(index, 1.4),
            )
        )
    return NativeEffect(4, tuple(pixels), tuple(timeline))


def _aurora(_: tuple[int, int, int], __: int) -> NativeEffect:
    pixels = []
    timeline = []
    for index in range(LED_COUNT):
        phase = 2 * math.pi * index / LED_COUNT
        hue = 0.48 + 0.22 * math.sin(phase * 2.4 - 0.4)
        value = 0.24 + 0.76 * ((math.sin(phase * 3 - 0.7) + 1) / 2)
        pixels.append(
            tuple(round(component * 255) for component in colorsys.hsv_to_rgb(hue % 1, 0.78, value))
        )
        timeline.append(
            TimelineFrame(
                duration_ms=75,
                frame_index=NATIVE_FRAME_ID,
                rotation_offset=index,
                red_gain=_aurora_gain(index, 0.5),
                green_gain=_aurora_gain(index, 0.0),
                blue_gain=_aurora_gain(index, 1.0),
            )
        )
    return NativeEffect(5, tuple(pixels), tuple(timeline))


EFFECT_BUILDERS: dict[str, EffectBuilder] = {
    "Rainbow": _rainbow,
    "Chase": _chase,
    "Breathe": _breathe,
    "Water Reflections": _water_reflections,
    "Aurora": _aurora,
}


def _rotation_timeline(duration_ms: int) -> tuple[TimelineFrame, ...]:
    """Return one full rotation of the uploaded frame."""
    return tuple(
        TimelineFrame(duration_ms, NATIVE_FRAME_ID, rotation_offset=index)
        for index in range(LED_COUNT)
    )


def _scaled_color(rgb_color: tuple[int, int, int], brightness: int) -> tuple[int, int, int]:
    """Apply Home Assistant's 0--255 brightness to an RGB colour."""
    return tuple(component * brightness // 255 for component in rgb_color)


def _breathing_gain(index: int) -> int:
    phase = 2 * math.pi * index / LED_COUNT - math.pi / 2
    return round((math.sin(phase) + 1) * 127.5)


def _water_shimmer_gain(index: int, offset: float) -> int:
    phase = 2 * math.pi * index / LED_COUNT
    return round(170 + 85 * ((math.sin(phase * 3 + offset) + 1) / 2))


def _aurora_gain(index: int, offset: float) -> int:
    phase = 2 * math.pi * index / LED_COUNT
    return round(140 + 115 * ((math.sin(phase + offset) + 1) / 2))


def _validate_color(rgb_color: tuple[int, int, int], brightness: int) -> None:
    if len(rgb_color) != 3 or any(not 0 <= component <= 255 for component in rgb_color):
        raise ValueError("rgb_color must contain three components in the range 0 through 255")
    if not 0 <= brightness <= 255:
        raise ValueError("brightness must be in the range 0 through 255")
