"""Connectivity diagnostics for local MPEG-TS proxy ports (not camera state)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PORT_1,
    CONF_PORT_2,
    CONF_SERIAL_1,
    CONF_SERIAL_2,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    host = entry.data[CONF_HOST]
    async_add_entities(
        [
            EZVIZBC1ProxyReachability(host, entry.data[CONF_PORT_1], entry.data[CONF_SERIAL_1], 1),
            EZVIZBC1ProxyReachability(host, entry.data[CONF_PORT_2], entry.data[CONF_SERIAL_2], 2),
        ],
        update_before_add=True,
    )


class EZVIZBC1ProxyReachability(BinarySensorEntity):
    """True means the TCP proxy listens; does not mean the camera is online."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"
    _attr_should_poll = True

    def __init__(self, host: str, port: int, serial: str, number: int) -> None:
        self._host = host
        self._port = port
        self._attr_name = f"EZVIZ BC1 Lab Proxy {number} reachable"
        self._attr_unique_id = f"{DOMAIN}_{serial}_proxy_reachable"
        self._attr_is_on = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
        }

    async def async_update(self) -> None:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=3
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError):
            self._attr_is_on = False
        else:
            self._attr_is_on = True
