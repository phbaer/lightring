"""Light platform for WaterRower LightRing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ADDRESS,
    CONTROL_CHARACTERISTIC_UUID,
    DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .effects import NATIVE_FRAME_ID, build_effect, effect_names
from .protocol import pixel_frame_command, solid_color_command, start_frame_command, timeline_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LightRing entities."""
    entity = WaterRowerLightRing(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = entity
    entry.async_on_unload(lambda: hass.data[DOMAIN].pop(entry.entry_id, None))
    async_add_entities([entity])


class WaterRowerLightRing(LightEntity):
    """An RGB light backed by one WaterRower LightRing."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(effect_names())

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the LightRing entity."""
        self._hass = hass
        self._address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = self._address
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=DEVICE_NAME,
        )
        self._is_on = False
        self._rgb_color: tuple[int, int, int] | None = None
        self._brightness: int | None = None
        self._effect = EFFECT_OFF
        self._write_lock = asyncio.Lock()

    @property
    def address(self) -> str:
        """Return the Bluetooth address used by the config entry."""
        return self._address

    @property
    def effect(self) -> str:
        """Return the active device-side effect."""
        return self._effect

    @property
    def is_on(self) -> bool:
        """Return whether the entity's last requested state is on."""
        return self._is_on

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        return ColorMode.RGB

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the last requested RGB value."""
        return self._rgb_color

    @property
    def brightness(self) -> int | None:
        """Return the last requested brightness."""
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LightRing, optionally setting its RGB colour."""
        if (effect := kwargs.get(ATTR_EFFECT)) and effect != EFFECT_OFF:
            await self.async_set_effect(effect)
            return
        rgb_color = kwargs.get(ATTR_RGB_COLOR, self._rgb_color or (255, 255, 255))
        brightness = kwargs.get(
            ATTR_BRIGHTNESS,
            self._brightness if self._brightness is not None else 255,
        )
        scaled_rgb = tuple(component * brightness // 255 for component in rgb_color)
        await self._async_write_color(*scaled_rgb)
        self._rgb_color = rgb_color
        self._brightness = brightness
        self._effect = EFFECT_OFF
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LightRing."""
        await self._async_write_color(0, 0, 0)
        self._is_on = False
        self._effect = EFFECT_OFF
        self.async_write_ha_state()

    async def async_set_effect(self, effect: str) -> None:
        """Build, upload, and start a registered device-side effect."""
        try:
            native_effect = build_effect(
                effect,
                self._rgb_color or (255, 255, 255),
                self._brightness if self._brightness is not None else 255,
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        first_timeline, second_timeline = timeline_commands(
            native_effect.animation_id, list(native_effect.timeline)
        )
        await self._async_write_commands(
            pixel_frame_command(NATIVE_FRAME_ID, list(native_effect.pixels)),
            first_timeline,
            second_timeline,
            start_frame_command(native_effect.animation_id),
        )
        self._effect = effect
        self._is_on = True
        self.async_write_ha_state()

    async def async_set_pixels(self, pixels: list[list[int]]) -> None:
        """Set up to 52 LEDs independently, in physical ring order."""
        try:
            rgb_pixels = [tuple(pixel) for pixel in pixels]
            command = pixel_frame_command(0, rgb_pixels)
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("pixels must contain at most 52 RGB triplets") from err
        await self._async_write_commands(command, start_frame_command(0))
        self._effect = EFFECT_OFF
        self._is_on = any(any(pixel) for pixel in rgb_pixels)
        self.async_write_ha_state()

    async def _async_write_color(self, red: int, green: int, blue: int) -> None:
        """Connect through HA's nearest capable Bluetooth adapter and write a colour."""
        await self._async_write_commands(solid_color_command(red, green, blue))

    async def _async_write_commands(self, *commands: bytes) -> None:
        """Write protocol commands atomically through a connectable HA adapter."""
        try:
            async with self._write_lock:
                ble_device = self._get_ble_device()
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self._address,
                    max_attempts=1,
                )
                try:
                    for command in commands:
                        await client.write_gatt_char(
                            CONTROL_CHARACTERISTIC_UUID, command, response=True
                        )
                finally:
                    await self._async_disconnect(client)
        except BleakError as err:
            _LOGGER.debug("Unable to write LightRing at %s", self._address, exc_info=True)
            raise HomeAssistantError(f"Unable to control {DEVICE_NAME}") from err

    async def _async_disconnect(self, client: BleakClientWithServiceCache) -> None:
        """Disconnect a client without hiding the result of a successful write."""
        try:
            await client.disconnect()
        except BleakError:
            _LOGGER.debug(
                "Unable to cleanly disconnect LightRing at %s",
                self._address,
                exc_info=True,
            )

    def _get_ble_device(self):
        """Get a device routed through Home Assistant's Bluetooth infrastructure."""
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise HomeAssistantError(
                f"No connectable Bluetooth proxy can currently reach {DEVICE_NAME}"
            )
        return ble_device
