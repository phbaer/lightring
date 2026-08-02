---
type: Protocol Reference
title: WaterRower LightRing BF BLE control protocol
description: Observed BLE service, writable characteristic, and command encoding for a LightRing BF device.
tags: [bluetooth-low-energy, gatt, protocol, interoperability, led]
status: partially-confirmed
generated: { by: codex/gpt-5, at: 2026-08-02T00:00:00+02:00 }
sources:
  - id: implementation
    resource: /custom_components/waterrower_ble/protocol.py
    title: Tested command encoder
  - id: provenance
    resource: /provenance.md
    title: Research and implementation provenance
---

# BLE identity

| Item | Value |
| --- | --- |
| Local name | `LightRing BF` |
| Service UUID | `e54b1234-67f5-479e-8711-b3b99198ce6c` |
| Control characteristic UUID | `e54b0003-67f5-479e-8711-b3b99198ce6c` |
| Characteristic capabilities | Read, write, notify, indicate |
| Link security observed | No pairing or bonding required for writes |

# Solid colour command

Command `0x00` sets the entire ring. Although the input is RGB, the device wire
order is green, red, blue:

```text
[0x00, green, red, blue]
```

For example, red is `00 00 FF 00`.

# Independently-addressable LEDs

An observed frame format uses command `0x02`, a little-endian 16-bit slot, then
exactly 52 triplets. Triplets use G/R/B order. Unused LEDs are padded with
zeroes.

```text
[0x02, slot_low, slot_high, G0, R0, B0, ... G51, R51, B51]
```

The resulting frame is 159 bytes. Command `0x03` selects and displays an
uploaded slot:

```text
[0x03, slot, mode_flag, duration_low, duration_high]
```

The integration uses slot 0, `mode_flag = 0`, and a duration of zero. The
frame encoder and its boundary checks are unit-tested in
`tests/test_protocol.py`.

# Native animation timeline (experimental)

The project implements an observed richer, device-side timeline for
`Rainbow`, `Chase`, `Breathe`, `Water Reflections`, and `Aurora`, so the ring
can animate locally rather than receiving full frames over the Bluetooth
proxy. The implementation does not copy application source, assets, internal
class names, or decompiled output.

* `0x05` carries the first 26 timeline records.
* `0x0D` carries the remaining 26 records.
* Each record is eight bytes:
  `[duration_low, duration_high, frame_low, frame_high, rotation_offset,
  green_gain, red_gain, blue_gain]`.
* The final byte identifies the animation slot.

Each record contains a frame index, duration, rotation offset, and per-channel
intensity factors. The device can therefore create a native animation from
uploaded RGB frames and a timed timeline, rather than continually receiving
new RGB frames. The `0x03` command also receives a mode flag and a duration;
its exact loop/start semantics remain unconfirmed.

The command layout is unit-tested, but its behavior has not yet been confirmed
on a physical LightRing from this integration. Treat this as experimental;
select a static RGB colour to replace the effect if it behaves unexpectedly.

# Physical order

The protocol proves that all 52 LEDs can be addressed separately. It does not,
by itself, identify which physical LED is index 0. To map a ring, submit a
frame with only one non-zero pixel, observe it, then repeat at known indexes.
Record the chosen orientation in an automation that constructs frames.

# Confidence and limitations

The UUIDs and commands above are interoperability observations, not a public
vendor specification. The solid-colour and frame commands are covered by
encoder tests; timeline semantics remain experimental. Treat commands beyond
`0x00`, `0x02`, `0x03`, `0x05`, and `0x0D` as unknown; do not send speculative
writes to production hardware. See [the provenance record](provenance.md) for
the boundary between protocol research and implementation material.
