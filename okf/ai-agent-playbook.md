---
type: Playbook
title: AI agent instructions for the WaterRower Local BLE project
description: Provider-neutral rules for AI systems that inspect, modify, test, or release this repository.
tags: [ai-agent, contribution, testing, security, home-assistant]
status: active
generated: { by: codex/gpt-5, at: 2026-08-02T00:00:00+02:00 }
sources:
  - id: project-reference
    resource: /project.md
    title: WaterRower Local BLE project reference
  - id: protocol-reference
    resource: /protocol.md
    title: WaterRower LightRing protocol reference
  - id: provenance-record
    resource: /provenance.md
    title: Interoperability provenance record
---

# Intended readers

These instructions apply equally to ChatGPT, Codex, Claude, Gemini, Cursor,
Copilot, local models, and any future AI system. Read the linked project and
protocol references before changing code. The rules describe repository intent;
they do not grant permission to control hardware that the operator does not
own or administer.

# Operating rules

1. Preserve existing user changes. Inspect the working tree before edits and do
   not revert unrelated files.
2. Keep all control local. Do not add cloud dependencies, telemetry, tracking,
   or remote-control endpoints without explicit maintainer approval.
3. Treat BLE writes as physical-world actions. Do not transmit unverified or
   destructive protocol commands. Use only documented commands unless the
   owner explicitly authorizes a bounded research experiment.
4. Do not claim that this integration prevents hijacking. The firmware accepts
   unauthenticated writes; document that limitation wherever security is
   discussed.
5. Do not expose raw BLE commands as a broad unauthenticated network API.
   Home Assistant service access must remain subject to the operator's normal
   HA authorization controls.
6. Do not log addresses, credentials, pairing keys, or packet contents unless
   the owner explicitly asks for diagnostic logging. Never commit secrets.
7. Do not add vendor application binaries, decompiled output, copied source,
   copied assets, or internal application identifiers. Record protocol
   observations and implementation decisions instead.

# Implementation instructions

* Maintain the Home Assistant config flow and use
  `bluetooth.async_ble_device_from_address(..., connectable=True)` so a local
  adapter or Bluetooth proxy can serve each ring.
* Keep wire encoding in `protocol.py`, independent of Home Assistant imports.
  Test every command format there before connecting it to an entity or service.
* RGB input is standard `(red, green, blue)`; only the protocol layer converts
  it to the device's G/R/B order.
* A LightRing contains 52 independently-addressable LEDs. Per-pixel requests
  must validate the maximum count and zero-fill omitted LEDs.
* Effects must be cancellable, avoid concurrent writes, and release the BLE
  connection when stopped or when an error occurs.
* Any new Home Assistant service requires an entry in `services.yaml`, schema
  validation, clear error messages, and README/OKF documentation.
* Bump `manifest.json`'s version when a releasable feature or bug fix changes.

# Verification instructions

Before handing off a change, run:

```sh
uv sync
uv run python -m unittest discover -s tests -v
uv run python scripts/package.py --output dist
```

Confirm that the archive contains `hacs.json` and the complete
`custom_components/waterrower_ble/` directory. Keep both the GitHub and
Forgejo workflows behaviorally equivalent. The ZIP is an optional build
artifact; HACS installs the tagged repository source directly.

Use the Python version selected by `.python-version` and `pyproject.toml`; do
not substitute the system Python or an unpinned future minor release.

If Home Assistant is not installed in the development environment, state that
the result was syntax- and unit-tested but not loaded in a live HA runtime.
Do not pretend a unit test proves radio, proxy, or device behavior.

# Change documentation

For changes to the BLE contract, update [the protocol reference](protocol.md),
add protocol tests, and distinguish observed facts from hypotheses. For changes
to user-facing behavior, update [the project reference](project.md), the root
README, and this playbook if the working rules change.

# Handoff checklist

* State exactly which files changed and which tests passed.
* State whether the HACS archive was built and where it is located.
* Identify validation not performed, especially live BLE and Home Assistant
  runtime testing.
* Flag any security implication, new permission, external dependency, or
  required maintainer decision.
