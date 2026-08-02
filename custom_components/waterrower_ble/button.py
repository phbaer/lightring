"""SmartRow workout controls."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER, SMARTROW_DEVICE_NAME, SMARTROW_MODEL

DESCRIPTION = ButtonEntityDescription(
    key="stop_session", name="Stop and reset workout", icon="mdi:stop-circle-outline"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SmartRow's explicit stop/reset control."""
    async_add_entities([SmartRowStopSessionButton(hass, entry)])


class SmartRowStopSessionButton(ButtonEntity):
    """Send the observed SmartRow stop/reset command."""

    entity_description = DESCRIPTION

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_stop_session"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=SMARTROW_MODEL,
            name=SMARTROW_DEVICE_NAME,
        )

    async def async_press(self) -> None:
        """Stop and reset the active workout on the next BLE interval."""
        capture = self._hass.data[DOMAIN].get(self._entry.entry_id)
        if capture is not None:
            capture.async_stop_session()
