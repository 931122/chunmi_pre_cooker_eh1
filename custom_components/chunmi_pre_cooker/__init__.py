"""Chunmi Electric Pressure Cooker integration."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import CONF_DID, CONF_HOST, CONF_TOKEN, DOMAIN, PRESET_COOK_MODES
from .coordinator import ChunmiCoordinator
from .device import ChunmiDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SELECT, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Chunmi cooker component."""
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_start_cooking(call: ServiceCall):
        """Handle start_cooking service call."""
        mode = call.data.get("mode")
        cook_code = call.data.get("cook_code")
        name = call.data.get("name") or mode or "烹饪"

        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            coord: ChunmiCoordinator = entry_data["coordinator"]
            if cook_code:
                await coord.device.async_start_cooking(name, cook_code, hass=hass)
                await coord.async_request_refresh()
            elif mode:
                await coord.async_start_cooking(mode)

    async def async_handle_cancel_cooking(call: ServiceCall):
        """Handle cancel_cooking service call."""
        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if not isinstance(entry_data, dict) or "coordinator" not in entry_data:
                continue
            coord: ChunmiCoordinator = entry_data["coordinator"]
            await coord.async_cancel_cooking()

    hass.services.async_register(DOMAIN, "start_cooking", async_handle_start_cooking)
    hass.services.async_register(DOMAIN, "cancel_cooking", async_handle_cancel_cooking)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chunmi cooker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    did = entry.data.get(CONF_DID, 0)

    device = ChunmiDevice(host=host, token=token, did=did)
    coordinator = ChunmiCoordinator(hass=hass, device=device)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
