---
type: Provenance Record
title: WaterRower Local BLE interoperability provenance
description: Research boundary and contribution rules for the independent protocol implementation.
tags: [provenance, interoperability, copyright, clean-room]
status: active
generated: { by: codex/gpt-5, at: 2026-08-02T00:00:00+02:00 }
sources:
  - id: repository
    resource: /
    title: Checked-in implementation, tests, and documentation
---

# Scope

This repository implements local interoperability with owner-controlled
WaterRower LightRing BF and SmartRow devices. It is not a copy, port, or
distribution of a vendor application.

# Materials in the repository

The repository contains Python, shell, YAML, JSON, Markdown, and unit-test
code written for this project. It contains no APK, DEX, JAR, decompiler
output, vendor application source, copied application classes, application
assets, or proprietary documentation. Build archives, caches, and bytecode are
excluded from version control.

# Research boundary

Protocol statements are categorized as:

* **Observed**: a byte sequence, identifier, or response seen on an
  owner-controlled device and reproduced by a test or documented experiment.
* **Implemented**: an encoder/decoder in this repository that has unit-test
  coverage but may still need hardware validation.
* **Hypothesis**: an interpretation whose device behavior is not yet confirmed.

The official application may have been consulted historically as a behavioral
reference during interoperability research. That fact is recorded rather than
hidden; no application material is reproduced here. Future contributors must
use their own observations or lawfully available documentation and must not
copy expression from the application.

# Legal boundary

This record supports provenance and engineering hygiene; it is not a legal
opinion and does not guarantee that a particular use is lawful in every
jurisdiction. Maintainers should obtain jurisdiction-specific advice before
redistributing protocol documentation or shipping this integration.
