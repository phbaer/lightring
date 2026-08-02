"""Wire protocol helpers for WaterRower LightRing."""

from __future__ import annotations

from dataclasses import dataclass

COMMAND_SOLID_COLOR = 0x00
COMMAND_PIXEL_FRAME = 0x02
COMMAND_START_FRAME = 0x03
COMMAND_TIMELINE_FIRST_HALF = 0x05
COMMAND_TIMELINE_SECOND_HALF = 0x0D
LED_COUNT = 52
TIMELINE_HALF_LENGTH = LED_COUNT // 2


@dataclass(frozen=True)
class TimelineFrame:
    """One device-side LightRing animation timeline record.

    ``frame_index`` selects a previously uploaded ``0x02`` frame.  The ring
    applies the per-record rotation and channel gains while it plays it.
    """

    duration_ms: int
    frame_index: int
    rotation_offset: int
    red_gain: int = 255
    green_gain: int = 255
    blue_gain: int = 255


def solid_color_command(red: int, green: int, blue: int) -> bytes:
    """Encode an RGB colour as the LightRing's solid-colour command.

    The LightRing wire order is command, green, red, blue.
    """
    for component in (red, green, blue):
        if not 0 <= component <= 255:
            raise ValueError("RGB components must be in the range 0 through 255")
    return bytes((COMMAND_SOLID_COLOR, green, red, blue))


def pixel_frame_command(slot: int, pixels: list[tuple[int, int, int]]) -> bytes:
    """Encode one 52-pixel frame for a LightRing animation slot.

    Pixels are RGB tuples in the ring's physical LED order. The device stores
    them on the wire as green, red, blue and zero-fills unused positions.
    """
    if not 0 <= slot <= 0xFFFF:
        raise ValueError("slot must be in the range 0 through 65535")
    if len(pixels) > LED_COUNT:
        raise ValueError(f"a LightRing has at most {LED_COUNT} pixels")

    command = bytearray((COMMAND_PIXEL_FRAME, slot & 0xFF, slot >> 8))
    for red, green, blue in pixels:
        command.extend(solid_color_command(red, green, blue)[1:])
    command.extend((0, 0, 0) * (LED_COUNT - len(pixels)))
    return bytes(command)


def start_frame_command(slot: int, mode_flag: int = 0, duration_ms: int = 0) -> bytes:
    """Start a frame or a device-side animation using the vendor format.

    The app sends a one-byte mode flag. Its full meaning is not yet known;
    ``0`` is the value used by the static-frame and native animation paths.
    """
    if not 0 <= slot <= 0xFF:
        raise ValueError("startable slot must be in the range 0 through 255")
    if not 0 <= mode_flag <= 0xFF:
        raise ValueError("mode_flag must be in the range 0 through 255")
    if not 0 <= duration_ms <= 0xFFFF:
        raise ValueError("duration_ms must be in the range 0 through 65535")
    return bytes(
        (
            COMMAND_START_FRAME,
            slot,
            mode_flag,
            duration_ms & 0xFF,
            duration_ms >> 8,
        )
    )


def timeline_commands(animation_id: int, frames: list[TimelineFrame]) -> tuple[bytes, bytes]:
    """Encode the observed 52-record native animation timeline.

    The protocol splits a complete timeline into two fixed 26-record packets:
    command ``0x05`` followed by ``0x0D``.  This is intentionally strict so a
    partially formed timeline is never written to a device.
    """
    if not 0 <= animation_id <= 0xFF:
        raise ValueError("animation_id must be in the range 0 through 255")
    if len(frames) != LED_COUNT:
        raise ValueError(f"a LightRing timeline must contain exactly {LED_COUNT} records")

    first = _timeline_command(COMMAND_TIMELINE_FIRST_HALF, animation_id, frames[:TIMELINE_HALF_LENGTH])
    second = _timeline_command(COMMAND_TIMELINE_SECOND_HALF, animation_id, frames[TIMELINE_HALF_LENGTH:])
    return first, second


def _timeline_command(command_id: int, animation_id: int, frames: list[TimelineFrame]) -> bytes:
    """Encode one 26-record half of a device-side animation timeline."""
    if len(frames) != TIMELINE_HALF_LENGTH:
        raise ValueError(f"a timeline packet must contain {TIMELINE_HALF_LENGTH} records")

    command = bytearray((command_id,))
    for frame in frames:
        _validate_timeline_frame(frame)
        command.extend((frame.duration_ms & 0xFF, frame.duration_ms >> 8))
        command.extend((frame.frame_index & 0xFF, frame.frame_index >> 8))
        command.extend(
            (
                frame.rotation_offset,
                frame.green_gain,
                frame.red_gain,
                frame.blue_gain,
            )
        )
    command.append(animation_id)
    return bytes(command)


def _validate_timeline_frame(frame: TimelineFrame) -> None:
    """Validate values before they are encoded into a BLE timeline packet."""
    if not 0 <= frame.duration_ms <= 0xFFFF:
        raise ValueError("timeline duration_ms must be in the range 0 through 65535")
    if not 0 <= frame.frame_index <= 0xFFFF:
        raise ValueError("timeline frame_index must be in the range 0 through 65535")
    for name, value in (
        ("rotation_offset", frame.rotation_offset),
        ("red_gain", frame.red_gain),
        ("green_gain", frame.green_gain),
        ("blue_gain", frame.blue_gain),
    ):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"timeline {name} must be in the range 0 through 255")
