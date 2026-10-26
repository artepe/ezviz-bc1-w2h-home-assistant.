"""Two BC1 stream entities connected to a LAN-only, experimental VTM proxy."""

from __future__ import annotations

from urllib.parse import quote

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PORT_1,
    CONF_PORT_2,
    CONF_SERIAL_1,
    CONF_SERIAL_2,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add camera entities without changing existing EZVIZ entities."""
    host = entry.data[CONF_HOST]
    async_add_entities(
        [
            EZVIZBC1LabCamera(host, entry.data[CONF_PORT_1], entry.data[CONF_SERIAL_1], 1),
            EZVIZBC1LabCamera(host, entry.data[CONF_PORT_2], entry.data[CONF_SERIAL_2], 2),
        ]
    )


class EZVIZBC1LabCamera(Camera):
    """HLS/WebRTC-compatible entry point for the external MPEG-TS proxy."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "EZVIZ"
    _attr_model = "BC1 (experimental VTM)"

    def __init__(self, host: str, port: int, serial: str, number: int) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._serial = serial
        self._number = number
        self._attr_name = f"EZVIZ BC1 Lab Camera {number}"
        self._attr_unique_id = f"{DOMAIN}_{serial}_camera"
        # Avoid extra wakeups of battery-powered cameras just for card thumbnails.
        self.use_stream_for_stills = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "manufacturer": "EZVIZ",
            "model": "BC1 (experimental)",
            "name": f"EZVIZ BC1 Lab {number}",
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Non-secret diagnostics only (no tokens or decrypt keys)."""
        return {
            "proxy_host": self._host,
            "proxy_port": self._port,
            "camera_serial": self._serial,
            "mode": "Experimental EZVIZ cloud VTM via MPEG-TS",
        }

    async def stream_source(self) -> str | None:
        """Return on-demand video URL consumed by the HA stream integration."""
        return f"http://{self._host}:{self._port}/{quote(self._serial, safe='')}.ts"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Avoid opening the battery-camera live connection for thumbnails."""
        return None
