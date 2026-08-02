"""Small, dependency-free helpers for the SmartRow text protocol."""

from __future__ import annotations


def key_for_challenge(message: str) -> str | None:
    """Return the observed key-lock response for a validated challenge."""
    challenge = message.strip()
    if len(challenge) < 16:
        return None

    subject, checksum = challenge[:14], challenge[14:]
    expected_checksum = f"{sum(ord(char) for char in subject):02X}"[-2:]
    if checksum != expected_checksum:
        return None

    try:
        value = int(challenge[10:14], 16)
    except ValueError:
        return None
    return f"{value * 17923 // 256:06X}"[2:].lower()


def decode_frame(frame: str) -> dict[str, float | int] | None:
    """Decode the metrics carried by one validated 16-character frame."""
    if len(frame) != 16 or not frame[0] in "abcdefxyzK":
        return None
    if f"{sum(map(ord, frame[:14])):02X}"[-2:] != frame[14:]:
        return None
    payload = frame[6:14]
    number = lambda start, end: int(payload[start:end].strip() or "0")
    if frame[0] == "a":
        return {"elapsed_time": number(0, 1) * 3600 + number(1, 3) * 60 + number(3, 5)}
    if frame[0] == "b":
        return {"work_per_stroke": number(0, 5) / 10, "stroke_time": number(5, 8) / 100}
    if frame[0] == "c":
        return {"power": number(0, 3), "average_power": number(3, 8) / 10}
    if frame[0] == "d":
        return {"stroke_rate": number(0, 3) / 10, "stroke_count": number(3, 7)}
    if frame[0] == "e":
        return {"split_time": number(0, 1) * 60 + number(1, 3), "average_split_time": number(3, 4) * 60 + number(4, 6)}
    return None


def decode_curve_frame(frame: str) -> tuple[str, list[int]] | None:
    """Decode one of the three eight-point SmartRow force-curve fragments."""
    if len(frame) != 16 or frame[0] not in "xyz":
        return None
    if f"{sum(map(ord, frame[:14])):02X}"[-2:] != frame[14:]:
        return None
    return frame[0], [(ord(point) - 33) * 16 for point in frame[6:14]]
