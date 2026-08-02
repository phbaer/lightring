"""SmartRow telemetry capture through Home Assistant Bluetooth."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ADDRESS,
    DOMAIN,
    MANUFACTURER,
    SMARTROW_COMMAND_CHARACTERISTIC_UUID,
    SMARTROW_CONFIG_REQUEST_COMMAND,
    SMARTROW_DEVICE_NAME,
    SMARTROW_HEARTBEAT_COMMAND,
    SMARTROW_HEARTBEAT_INTERVAL_SECONDS,
    SMARTROW_MODEL,
    SMARTROW_KEYLOCK_REQUEST_COMMAND,
    SMARTROW_REMOTE_REQUEST_COMMAND,
    SMARTROW_SERVICE_UUID,
    SMARTROW_START_SESSION_COMMAND,
    SMARTROW_TELEMETRY_CHARACTERISTIC_UUID,
)
from .smartrow_protocol import decode_curve_frame, decode_frame, key_for_challenge

_LOGGER = logging.getLogger(__name__)

DESCRIPTION = SensorEntityDescription(
    key="smartrow_telemetry_capture",
    name="Telemetry capture",
    icon="mdi:bluetooth-transfer",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the temporary SmartRow capture sensor."""
    capture = SmartRowTelemetryCapture(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = capture
    async_add_entities([
        capture,
        *[SmartRowMetricSensor(capture, entry, description) for description in METRICS],
        SmartRowForceCurveSensor(capture, entry),
    ])


METRICS = (
    SensorEntityDescription(key="power", name="Power", native_unit_of_measurement="W", device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="average_power", name="Average power", native_unit_of_measurement="W", device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="stroke_rate", name="Stroke rate", native_unit_of_measurement="spm", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="stroke_count", name="Stroke count", state_class=SensorStateClass.TOTAL_INCREASING),
    SensorEntityDescription(key="work_per_stroke", name="Work per stroke", native_unit_of_measurement="J", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="stroke_time", name="Stroke time", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="split_time", name="Split time", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="average_split_time", name="Average split time", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="elapsed_time", name="Elapsed time", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
)


class SmartRowTelemetryCapture(SensorEntity):
    """Capture SmartRow telemetry using the observed device heartbeat."""

    entity_description = DESCRIPTION
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{self._address}_telemetry_capture"
        self._attr_native_value = "waiting"
        self._attr_extra_state_attributes = {
            "last_packet": None,
            "last_text": None,
            "last_notification": None,
            "packet_count": 0,
        }
        self._receive_buffer = bytearray()
        self._command_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._keylock_response: str | None = None
        self._metrics: dict[str, float | int] = {}
        self._curve_segments: dict[str, list[int]] = {}
        self._force_curve: list[int] = []
        self._listeners: list[callable] = []
        self._capture_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._initialised_event = asyncio.Event()
        self._device_available = asyncio.Event()
        self._current_ble_device = None
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=SMARTROW_MODEL,
            name=SMARTROW_DEVICE_NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Begin the telemetry subscription."""
        self._capture_task = self._hass.async_create_background_task(
            self._async_capture(), "SmartRow telemetry capture"
        )
        self.async_on_remove(
            bluetooth.async_register_callback(
                self._hass,
                self._async_bluetooth_callback,
                {"local_name": SMARTROW_DEVICE_NAME, "connectable": True},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )
        self.async_on_remove(self._stop_capture)
        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._stop_capture)

    def _stop_capture(self, _: Event | None = None) -> None:
        """Stop a running subscription when the entry is unloaded."""
        self._stop_event.set()
        if self._capture_task is not None:
            self._capture_task.cancel()

    def async_stop_session(self) -> None:
        """Queue the observed stop/reset command for the active session."""
        self._command_queue.put_nowait(SMARTROW_START_SESSION_COMMAND)

    async def _async_capture(self) -> None:
        """Retry a proxy subscription while SmartRow is available."""
        while not self._stop_event.is_set():
            client = None
            try:
                ble_device = self._get_current_ble_device()
                if ble_device is None:
                    await self._wait_for_device()
                    continue
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    ble_device.address,
                    max_attempts=3,
                )
                await client.start_notify(
                    SMARTROW_TELEMETRY_CHARACTERISTIC_UUID, self._notification_handler
                )
                await self._async_start_session(client)
                _LOGGER.info("Listening for SmartRow telemetry through Home Assistant Bluetooth")
                self._attr_native_value = "listening"
                self.async_write_ha_state()
                await self._async_send_heartbeats(client)
            except (BleakError, asyncio.TimeoutError):
                _LOGGER.debug("SmartRow telemetry capture is waiting to reconnect", exc_info=True)
                self._attr_native_value = "unavailable"
                self.async_write_ha_state()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=10)
                except TimeoutError:
                    pass
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except BleakError:
                        _LOGGER.debug("Unable to disconnect SmartRow capture", exc_info=True)

    async def _async_send_heartbeats(self, client: BleakClientWithServiceCache) -> None:
        """Keep SmartRow telemetry enabled with periodic heartbeats."""
        while not self._stop_event.is_set():
            await self._async_write_command(client, SMARTROW_HEARTBEAT_COMMAND)
            while not self._command_queue.empty():
                await self._async_write_command(client, self._command_queue.get_nowait())
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=SMARTROW_HEARTBEAT_INTERVAL_SECONDS
                )
            except TimeoutError:
                pass

    async def _async_write_command(
        self, client: BleakClientWithServiceCache, command: bytes
    ) -> None:
        """Write one ASCII command to SmartRow without a GATT response."""
        await client.write_gatt_char(
            SMARTROW_COMMAND_CHARACTERISTIC_UUID, command, response=False
        )

    async def _async_start_session(self, client: BleakClientWithServiceCache) -> None:
        """Start a new SmartRow session after the heartbeat acknowledgement.

        ``\rV@\r`` is the observed session-start/reset command. It is
        intentionally sent once per new BLE connection, not per heartbeat.
        """
        self._initialised_event.clear()
        await self._async_write_command(client, SMARTROW_HEARTBEAT_COMMAND)
        try:
            await asyncio.wait_for(self._initialised_event.wait(), timeout=3)
        except TimeoutError:
            _LOGGER.warning("SmartRow did not acknowledge its telemetry heartbeat")
            return
        await self._async_write_command(client, SMARTROW_START_SESSION_COMMAND)
        _LOGGER.info("Started SmartRow telemetry session")

    def _async_bluetooth_callback(
        self, discovery_info: BluetoothServiceInfoBleak, _: bluetooth.BluetoothChange
    ) -> None:
        """Keep the latest proxy-advertised device despite address rotation."""
        if SMARTROW_SERVICE_UUID not in discovery_info.service_uuids:
            return
        self._address = discovery_info.address
        self._current_ble_device = discovery_info.device
        self._device_available.set()
        _LOGGER.info("Resolved SmartRow's current BLE address: %s", self._address)

    async def _wait_for_device(self) -> None:
        """Wait briefly for the proxy callback instead of missing a short advert."""
        self._attr_native_value = "waiting"
        self.async_write_ha_state()
        try:
            await asyncio.wait_for(self._device_available.wait(), timeout=10)
        except TimeoutError:
            return
        self._device_available.clear()

    def _get_current_ble_device(self):
        """Resolve SmartRow again when its rotating address has changed."""
        if self._current_ble_device is not None:
            return self._current_ble_device
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is not None:
            return ble_device

        for discovery_info in bluetooth.async_discovered_service_info(
            self._hass, connectable=True
        ):
            if (
                discovery_info.name == SMARTROW_DEVICE_NAME
                and SMARTROW_SERVICE_UUID in discovery_info.service_uuids
            ):
                self._address = discovery_info.address
                self._current_ble_device = discovery_info.device
                _LOGGER.info("Resolved SmartRow's current BLE address: %s", self._address)
                return discovery_info.device
        return None

    def _notification_handler(self, _: int, data: bytearray) -> None:
        """Reassemble CR-delimited SmartRow frames from BLE fragments."""
        raw_data = bytes(data)
        attributes = dict(self._attr_extra_state_attributes)
        attributes["last_notification"] = raw_data.hex()
        self._receive_buffer.extend(raw_data)
        if len(self._receive_buffer) > 128:
            _LOGGER.warning("Discarding an unterminated SmartRow telemetry frame")
            self._receive_buffer.clear()

        while b"\r" in self._receive_buffer:
            frame, _, remainder = self._receive_buffer.partition(b"\r")
            self._receive_buffer = bytearray(remainder)
            if not frame:
                self._initialised_event.set()
                continue

            packet = frame.hex()
            text = frame.decode("ascii", errors="replace")
            self._queue_protocol_response(text)
            metrics = decode_frame(text)
            if metrics is not None:
                self._metrics.update(metrics)
                for listener in self._listeners:
                    listener()
            curve_fragment = decode_curve_frame(text)
            if curve_fragment is not None:
                segment, points = curve_fragment
                self._curve_segments[segment] = points
                if all(key in self._curve_segments for key in "xyz"):
                    self._force_curve = [
                        *self._curve_segments["x"],
                        *self._curve_segments["y"],
                        *self._curve_segments["z"],
                    ]
                    for listener in self._listeners:
                        listener()
            attributes["last_packet"] = packet
            attributes["last_text"] = text
            attributes["packet_count"] += 1
            _LOGGER.info("SmartRow telemetry frame from %s: %s", self._address, packet)

        self._attr_extra_state_attributes = attributes
        self._attr_native_value = "receiving"
        self.async_write_ha_state()

    def _queue_protocol_response(self, frame: str) -> None:
        """Continue the v3 telemetry handshake from complete text frames."""
        if frame.startswith("SmartRow 'V3."):
            self._command_queue.put_nowait(SMARTROW_CONFIG_REQUEST_COMMAND)
            self._command_queue.put_nowait(SMARTROW_REMOTE_REQUEST_COMMAND)
        elif "E>" in frame:
            self._command_queue.put_nowait(SMARTROW_KEYLOCK_REQUEST_COMMAND)
        elif frame.startswith("KEYLOCK"):
            key = key_for_challenge(frame)
            if key is not None:
                self._keylock_response = key
                self._command_queue.put_nowait(f"\r{key}\r".encode())
            else:
                _LOGGER.warning("SmartRow sent an invalid key-lock challenge")
        elif self._keylock_response is not None and frame == self._keylock_response:
            self._keylock_response = None
            self._command_queue.put_nowait(SMARTROW_START_SESSION_COMMAND)


class SmartRowMetricSensor(SensorEntity):
    """Expose one metric decoded by the SmartRow telemetry capture."""

    _attr_should_poll = False

    def __init__(self, capture: SmartRowTelemetryCapture, entry: ConfigEntry, description: SensorEntityDescription) -> None:
        self.entity_description = description
        self._capture = capture
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
        self._attr_device_info = capture._attr_device_info

    @property
    def native_value(self):
        return self._capture._metrics.get(self.entity_description.key)

    async def async_added_to_hass(self) -> None:
        self._capture._listeners.append(self.async_write_ha_state)
        self.async_on_remove(lambda: self._capture._listeners.remove(self.async_write_ha_state))


class SmartRowForceCurveSensor(SensorEntity):
    """Expose the latest 24-point SmartRow stroke-force curve."""

    _attr_should_poll = False
    _attr_name = "Stroke force curve"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, capture: SmartRowTelemetryCapture, entry: ConfigEntry) -> None:
        self._capture = capture
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_stroke_force_curve"
        self._attr_device_info = capture._attr_device_info

    @property
    def native_value(self) -> int | None:
        return max(self._capture._force_curve, default=None)

    @property
    def extra_state_attributes(self) -> dict[str, list[int] | int]:
        points = self._capture._force_curve
        return {"points": points, "sample_count": len(points)}

    async def async_added_to_hass(self) -> None:
        self._capture._listeners.append(self.async_write_ha_state)
        self.async_on_remove(lambda: self._capture._listeners.remove(self.async_write_ha_state))
