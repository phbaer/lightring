"""Config flow for WaterRower Local BLE."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import (
    CONF_ADDRESS,
    CONF_DEVICE_TYPE,
    DEVICE_NAME,
    DEVICE_TYPE_LIGHTRING,
    DEVICE_TYPE_SMARTROW,
    DOMAIN,
    LOCAL_NAME,
    SMARTROW_DEVICE_NAME,
    SMARTROW_LOCAL_NAME,
)

DEVICE_TYPES = {
    LOCAL_NAME: (DEVICE_TYPE_LIGHTRING, DEVICE_NAME),
    SMARTROW_LOCAL_NAME: (DEVICE_TYPE_SMARTROW, SMARTROW_DEVICE_NAME),
}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Bluetooth discovery of supported WaterRower devices."""

    VERSION = 1

    _discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow setup from the Add Integration user interface."""
        await bluetooth.async_request_active_scan(self.hass)
        discovered = {
            info.address: info
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if info.name in DEVICE_TYPES and not self._is_configured(info)
        }

        if user_input is not None:
            discovery_info = discovered.get(user_input[CONF_ADDRESS])
            if discovery_info is not None:
                return await self._async_create_entry(discovery_info)
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(discovered),
                errors={"base": "device_not_found"},
            )

        if not discovered:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices"},
            )

        return self.async_show_form(
            step_id="user", data_schema=self._user_schema(discovered)
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a Bluetooth discovery."""
        if discovery_info.name not in DEVICE_TYPES:
            return self.async_abort(reason="not_supported")
        if self._is_configured(discovery_info):
            return self.async_abort(reason="already_configured")

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": DEVICE_TYPES[discovery_info.name][1],
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a Bluetooth-discovered WaterRower device."""
        if user_input is not None:
            assert self._discovery_info is not None
            return await self._async_create_entry(self._discovery_info)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": (
                    DEVICE_TYPES[self._discovery_info.name][1]
                    if self._discovery_info and self._discovery_info.name in DEVICE_TYPES
                    else DEVICE_NAME
                ),
            },
        )

    async def _async_create_entry(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Create a device-specific entry after it was selected or discovered."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DEVICE_TYPES[discovery_info.name][1],
            data={
                CONF_ADDRESS: discovery_info.address,
                CONF_DEVICE_TYPE: DEVICE_TYPES[discovery_info.name][0],
            },
        )

    def _is_configured(self, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Return whether discovery should be suppressed for this device.

        LightRing BF uses a stable address, so its address is the unique ID.
        SmartRow may rotate its address; after one SmartRow entry exists,
        suppress further SmartRow discovery instead of showing the same device
        again under a new address.
        """
        configured_entries = self._async_current_entries()
        if any(
            entry.data.get(CONF_ADDRESS) == discovery_info.address
            for entry in configured_entries
        ):
            return True
        return discovery_info.name == SMARTROW_LOCAL_NAME and any(
            entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_SMARTROW
            for entry in configured_entries
        )

    @staticmethod
    def _user_schema(
        discovered: dict[str, BluetoothServiceInfoBleak],
    ) -> vol.Schema:
        """Build the selector for currently reachable WaterRower devices."""
        return vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        address: f"{DEVICE_TYPES[info.name][1]} ({address})"
                        for address, info in discovered.items()
                    }
                )
            }
        )
