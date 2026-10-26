"""EZVIZ BC1 experiment: use an independently running VTM MPEG-TS proxy."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create two camera entities and their network-proxy diagnostics."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the integration without changing other EZVIZ installations."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
