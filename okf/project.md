---
type: Project Reference
title: WaterRower Local BLE integration
description: A local Bluetooth and Home Assistant HACS integration for WaterRower LightRing BF and SmartRow devices.
tags: [waterrower, lightring, bluetooth, home-assistant, hacs, local-control]
status: active
generated: { by: codex/gpt-5, at: 2026-08-02T00:00:00+02:00 }
sources:
  - id: repository
    resource: /
    title: Repository implementation and tests
  - id: ha-bluetooth-api
    resource: https://developers.home-assistant.io/docs/core/bluetooth/api/
    title: Home Assistant Bluetooth API
---

# Purpose

This repository controls WaterRower LightRing BF and SmartRow devices locally
over Bluetooth Low Energy (BLE). It provides:

* A Linux command-line controller, `lightringctl`, for solid RGB colours.
* A Home Assistant custom integration distributed as a HACS release archive.
* Automatic discovery through Home Assistant's Bluetooth infrastructure,
  including ESPHome Bluetooth proxies.
* One Home Assistant RGB light entity for every configured LightRing.
* SmartRow telemetry sensors and a session reset control.
* Device-side native effects plus a service for static, independently-addressable
  LED frames.

# Architecture

```text
Home Assistant light entity or service
                 |
                 v
WaterRower Local BLE integration
                 |
                 v
Home Assistant Bluetooth API -> local adapter or ESPHome Bluetooth proxy
                 |
                 v
LightRing BF BLE GATT characteristic
```

The integration chooses a connectable BLE device using Home Assistant's
Bluetooth API. It does not require the HA host itself to have a Bluetooth
adapter.

# Repository map

| Path | Responsibility |
| --- | --- |
| `custom_components/waterrower_ble/` | Home Assistant integration |
| `custom_components/waterrower_ble/light.py` | RGB entity and BLE writes |
| `custom_components/waterrower_ble/effects.py` | Dependency-free effect registry and frame/timeline builders |
| `custom_components/waterrower_ble/protocol.py` | Dependency-free command encoding |
| `custom_components/waterrower_ble/services.yaml` | Per-LED service declaration |
| `lightringctl` | Local standalone controller |
| `scripts/package.py` | HACS ZIP builder |
| `tests/` | Protocol and packaging unit tests |
| `.github/workflows/` and `.forgejo/workflows/` | CI package pipelines |

# Home Assistant interface

Each configured device exposes an RGB light with brightness support. The
effects list is supplied by the dependency-free `effects.py` registry. Effects
are uploaded once and then render on the LightRing itself; they do not keep a
BLE connection open while animating. Adding an effect requires only a frame and
timeline definition with a unique animation ID.

The `waterrower_ble.set_pixels` service takes a Bluetooth address and up
to 52 RGB triplets. Entries are sent in physical ring order; missing entries are
zero-filled (off). See [the protocol reference](protocol.md) for the command
format and the orientation limitation.

# Security boundary

The tested LightRing accepts control writes without pairing, bonding, or
authenticated encryption. This integration is therefore a local controller,
not a security control: a nearby attacker may still issue the same GATT writes.
Keep the device unpowered when unused and request authenticated encrypted BLE
writes in a vendor firmware update.

# Build and release

Run the tests and build a HACS archive with:

```sh
uv sync
uv run python -m unittest discover -s tests -v
uv run python scripts/package.py --output dist
```

The archive root must retain `custom_components/waterrower_ble/` and
include `hacs.json`. The optional CI archive is named
`waterrower_local_ble.zip`; HACS installs the tagged repository source
directly. The project pins Python 3.14 in `.python-version` and
declares the same supported range in `pyproject.toml`. GitHub Actions and
Forgejo Actions run these same checks and upload the generated ZIP.

# Interoperability and provenance

This repository is an independent interoperability implementation. No vendor
application source, APK/DEX/JAR files, decompiled output, copied classes,
assets, or proprietary documentation are distributed here. Protocol claims
are recorded as observations, tests, or hypotheses; this reference is not a
vendor specification. See [the provenance record](provenance.md) for the
research boundary and contribution requirements.
