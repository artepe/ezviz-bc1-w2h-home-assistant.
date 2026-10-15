"""Persist options through Supervisor and verify that it kept every camera."""

from __future__ import annotations

import json
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from camera_config import Camera, parse_cameras, with_cameras


class SettingsError(Exception):
    """A safe message that may be displayed without leaking API responses."""


class SupervisorClient:
    def __init__(self, token: str | None = None, base_url: str = "http://supervisor"):
        self.token = os.environ.get("SUPERVISOR_TOKEN", "") if token is None else token
        self.base_url = base_url.rstrip("/")
        self.lock = threading.RLock()

    def request(self, path: str, payload: dict[str, object] | None = None) -> dict:
        if not self.token:
            raise SettingsError("Supervisor token is missing from the app environment. Update and restart this app.")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}/addons/self/{path}", data=data,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="GET" if data is None else "POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            error.close()
            if error.code == 400:
                raise SettingsError("Supervisor rejected the options. Reload the app store and update EZVIZ Cameras to 0.2.0 or newer.") from None
            if error.code == 403:
                raise SettingsError("Supervisor denied settings access (HTTP 403). Restart this app and check the Supervisor log.") from None
            raise SettingsError(f"Supervisor could not save or load settings (HTTP {error.code}). Try again.") from None
        except (OSError, URLError, ValueError, TypeError):
            raise SettingsError("Cannot reach Supervisor. Settings have not been confirmed as saved.") from None
        if not isinstance(result, dict) or result.get("result") != "ok":
            raise SettingsError("Supervisor did not confirm the operation. Check the Supervisor log.")
        result_data = result.get("data") or {}
        if not isinstance(result_data, dict):
            raise SettingsError("Supervisor returned invalid settings.")
        return result_data

    def raw_options(self) -> dict[str, object]:
        """Info preserves !secret references; never return this to the browser."""
        options = self.request("info").get("options")
        if not isinstance(options, dict):
            raise SettingsError("Supervisor did not return the app options.")
        return options

    def effective_options(self) -> dict[str, object]:
        """The config endpoint resolves secret references for cloud login only."""
        return self.request("options/config")

    def save_cameras(self, cameras: list[Camera] | tuple[Camera, ...]) -> dict[str, object]:
        with self.lock:
            current = self.raw_options()
            updated = with_cameras(current, cameras)
            self.request("options", {"options": updated})
            try:
                persisted = self.raw_options()
                if parse_cameras(persisted) != parse_cameras(updated):
                    raise SettingsError("Camera settings did not survive the Supervisor save.")
            except (SettingsError, ValueError):
                # An old schema may silently strip unknown options. Restore the
                # previous configuration so the working camera is not lost.
                try:
                    self.request("options", {"options": current})
                    if parse_cameras(self.raw_options()) != parse_cameras(current):
                        raise SettingsError("Rollback verification failed.")
                except (SettingsError, ValueError):
                    raise SettingsError("Camera settings could not be verified or restored. Check the app Configuration tab before trying again.") from None
                raise SettingsError("Camera settings did not survive the Supervisor save. The previous settings were restored. Reload the app store and update this app before trying again.") from None
            return persisted
