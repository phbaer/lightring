# WaterRower Local BLE

Project and vendor-neutral AI-agent documentation is available as an
[Open Knowledge Format (OKF) bundle](okf/index.md).

## Development

This project is managed with [uv](https://docs.astral.sh/uv/) and pins the
current stable Python minor release, 3.14, in `.python-version`. uv downloads
the current compatible 3.14 patch release when it is not already available.

```sh
uv sync
uv run python -m unittest discover -s tests -v
uv run python scripts/package.py --output dist
```

## Home Assistant / HACS

This repository is a HACS custom integration. Add it as a custom repository of
type **Integration**, then install **WaterRower Local BLE** and restart Home
Assistant. Each `LightRing BF` discovered through Home Assistant's Bluetooth
integration (including ESPHome Bluetooth proxies) is offered for setup and
creates one RGB light entity.

To add a ring manually, choose **Add Integration**, select **WaterRower
LightRing**, then choose a currently reachable `LightRing BF`. The flow requests
an active scan from the configured Bluetooth adapters and proxies.

The integration connects through Home Assistant's nearest connectable Bluetooth
adapter when an entity is changed; it does not require the HA host itself to
have a Bluetooth radio.

### LED addressing

The LightRing supports 52 independently-addressable LEDs. The integration
offers device-side `Rainbow`, `Chase`, `Breathe`, `Water Reflections`, and
`Aurora` effects on every RGB light entity. Each uploads its frame and native
52-step timeline once; the ring then runs the animation locally, avoiding
proxy-link frame streaming and its flicker. `Chase` and `Breathe` use the
light's current RGB colour and brightness. It also exposes the
`waterrower_ble.set_pixels` action for static pixel frames:

```yaml
action: waterrower_ble.set_pixels
data:
  address: "D7:FC:EB:0B:B5:BF"
  pixels:
    - [255, 0, 0]
    - [0, 255, 0]
    - [0, 0, 255]
```

`pixels` is a list of RGB triplets in the physical ring order; it may contain
up to 52 entries. Unspecified LEDs are turned off. The first physical LED has
not yet been mapped to a visible reference point on the ring, so install a
single red pixel test frame to establish the orientation for your device.

The integration uses an independently implemented wire encoder. The observed
format is: `0x02` uploads a 52-pixel frame (G/R/B wire order), followed by
`0x03` to select and display that frame. The native timeline commands used by
the effects are documented with their evidence level in the
[protocol reference](okf/protocol.md). The timeline remains experimental until
confirmed against a physical LightRing by this project.

### Adding an effect

Native effect definitions live in
`custom_components/waterrower_ble/effects.py`, independently of Home
Assistant and BLE transport. Add a builder returning one 52-pixel frame and 52
`TimelineFrame` records, assign it a unique animation ID, and register it in
`EFFECT_BUILDERS`. The registry is unit-tested so every definition remains
within the device's byte and frame limits.

### SmartRow

SmartRow is discovered through the same Home Assistant Bluetooth proxies. It
provides power, average power, stroke rate/count, work per stroke, stroke time,
split times, elapsed time, and a `Stroke force curve` entity. The latter holds
the latest 24-point force profile in its `points` attribute; its state is the
profile peak.

For an app-like live chart, install **ApexCharts Card** from HACS →
**Dashboards**. Then add this Lovelace card (replace the entity ID if HA
assigned a suffix):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: SmartRow stroke force
chart_type: line
apex_config:
  xaxis:
    type: numeric
    title:
      text: Stroke position
  yaxis:
    title:
      text: Force profile
series:
  - entity: sensor.smartrow_stroke_force_curve
    name: Force
    data_generator: |
      return entity.attributes.points.map((point, index) => [index, point]);
```

### Release artifact

Both GitHub Actions and Forgejo Actions run the unit tests and create
`waterrower_local_ble.zip` is an optional local/CI archive. HACS installs the
tagged repository source directly; the archive contains the required
`custom_components/waterrower_ble/` path and is uploaded as the
`waterrower-local-ble-hacs` workflow artifact.

## Standalone local CLI

`./lightringctl` controls the WaterRower LightRing BF discovered on this host.
It uses the LightRing's unauthenticated BLE control characteristic:

```sh
./lightringctl red
./lightringctl rgb 255 128 0
./lightringctl off
```

The protocol command for a solid colour is `[00, green, red, blue]`, written
to `e54b0003-67f5-479e-8711-b3b99198ce6c`.

## Interoperability and provenance

This is an independent interoperability implementation. It contains no
vendor application source, binaries, decompiled output, copied classes,
assets, or proprietary documentation. Protocol claims are limited to
black-box BLE observations, byte-level tests, and behavior that can be
verified on owner-controlled hardware. Historical research may have used the
official application as a behavioral reference; that does not make this
repository a distribution of the application or a claim of clean-room legal
status. See the [provenance record](okf/provenance.md), and obtain legal advice
for a jurisdiction-specific copyright assessment.

## Security result

The LightRing accepts these control writes without pairing or bonding. This is
an authorization vulnerability: a nearby Bluetooth device can issue the same
commands. Keep the LightRing unpowered when unused and request a firmware
update from WaterRower that requires LE Secure Connections with authenticated,
encrypted writes. The local controller does not mitigate this firmware issue.
