"""User-configurable pairing of BC1 cameras to a local VTM stream proxy."""

from __future__ import annotations

from ipaddress import ip_address
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import (
    CONF_PORT_1,
    CONF_PORT_2,
    CONF_SERIAL_1,
    CONF_SERIAL_2,
    DOMAIN,
)

_SERIAL_RE = re.compile(r"^[A-Za-z0-9_-]{5,80}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,252}$")


class EZVIZBC1LabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up independent cameras; EZVIZ passwords stay on the Mac proxy."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            first = str(user_input[CONF_SERIAL_1]).strip().upper()
            second = str(user_input[CONF_SERIAL_2]).strip().upper()
            port1 = int(user_input[CONF_PORT_1])
            port2 = int(user_input[CONF_PORT_2])

            # Allow a simple IP or resolvable DNS hostname, not a URL/path.
            try:
                ip_address(host)
            except ValueError:
                if not _HOST_RE.fullmatch(host) or ".." in host:
                    errors[CONF_HOST] = "invalid_host"

            if not _SERIAL_RE.fullmatch(first) or not _SERIAL_RE.fullmatch(second):
                errors["base"] = "invalid_serial"
            elif first == second:
                errors["base"] = "same_serial"
            if not 1 <= port1 <= 65535 or not 1 <= port2 <= 65535:
                errors["base"] = "invalid_port"
            elif port1 == port2:
                errors["base"] = "same_port"

            if not errors:
                await self.async_set_unique_id(f"{DOMAIN}_{host.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"EZVIZ BC1 Lab ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_SERIAL_1: first,
                        CONF_SERIAL_2: second,
                        CONF_PORT_1: port1,
                        CONF_PORT_2: port2,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.10.245"): str,
                vol.Required(CONF_SERIAL_1): str,
                vol.Required(CONF_PORT_1, default=8558): vol.Coerce(int),
                vol.Required(CONF_SERIAL_2): str,
                vol.Required(CONF_PORT_2, default=8559): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
