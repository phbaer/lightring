"""Home Assistant integration for WaterRower LightRing."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol

from .const import (
    ATTR_ADDRESS,
    ATTR_PIXELS,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_SMARTROW,
    DOMAIN,
    SERVICE_SET_PIXELS,
)

LIGHTRING_PLATFORMS: tuple[Platform, ...] = (Platform.LIGHT,)
SMARTROW_PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR, Platform.BUTTON)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services shared by all discovered LightRings."""
    hass.data.setdefault(DOMAIN, {})

    async def async_set_pixels(service) -> None:
        address = service.data[ATTR_ADDRESS].upper()
        for entity in hass.data[DOMAIN].values():
            if entity.address.upper() == address:
                await entity.async_set_pixels(service.data[ATTR_PIXELS])
                return
        raise HomeAssistantError(
            f"No configured WaterRower LightRing has address {address}"
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PIXELS,
        async_set_pixels,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ADDRESS): str,
                vol.Required(ATTR_PIXELS): list,
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a LightRing or SmartRow from a config entry."""
    platforms = (
        SMARTROW_PLATFORMS
        if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_SMARTROW
        else LIGHTRING_PLATFORMS
    )
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a LightRing or SmartRow config entry."""
    platforms = (
        SMARTROW_PLATFORMS
        if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_SMARTROW
        else LIGHTRING_PLATFORMS
    )
    return await hass.config_entries.async_unload_platforms(entry, platforms)
