"""Camera configuration shared by the launcher and the ingress camera manager."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

FIRST_PORT = 8558
MAX_CAMERAS = 16
LAST_PORT = FIRST_PORT + MAX_CAMERAS - 1
SERIAL = re.compile(r"[A-Za-z0-9-]{5,128}")


@dataclass(frozen=True)
class Camera:
    name: str
    serial: str
    port: int

    @property
    def index(self) -> int:
        return self.port - FIRST_PORT + 1

    @property
    def stream(self) -> str:
        return "ezviz_bc1" if self.index == 1 else f"ezviz_bc1_{self.index}"

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "serial": self.serial, "port": self.port}

    def snippets(self) -> dict[str, str]:
        source = f"ffmpeg:http://127.0.0.1:{self.port}/{self.serial}.ts#video=copy"
        return {
            "go2rtc": f"streams:\n  {self.stream}:\n    - {source}\n",
            "lovelace": (
                "type: custom:webrtc-camera\n"
                f"url: {self.stream}\nmode: mse\nmedia: video\nui: true\n"
                f"title: {json.dumps(self.name, ensure_ascii=True)}\n"
            ),
        }


def validate_serial(value: object) -> str:
    if not isinstance(value, str) or not SERIAL.fullmatch(value.strip()):
        raise ValueError("Enter a valid camera serial, normally HUB_SERIAL-CAMERA_SERIAL.")
    return value.strip()


def validate_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a camera name.")
    name = value.strip()
    if not name or len(name) > 80 or any(ord(char) < 32 for char in name):
        raise ValueError("Camera names must contain 1 to 80 printable characters.")
    return name


def validate_port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not FIRST_PORT <= value <= LAST_PORT:
        raise ValueError(f"Camera ports must be between {FIRST_PORT} and {LAST_PORT}.")
    return value


def next_port(cameras: list[Camera] | tuple[Camera, ...]) -> int:
    used = {camera.port for camera in cameras}
    for port in range(FIRST_PORT, LAST_PORT + 1):
        if port not in used:
            return port
    raise ValueError(f"This app supports up to {MAX_CAMERAS} cameras.")


def parse_cameras(raw: dict[str, object]) -> tuple[Camera, ...]:
    """Merge old scalar options with new entries without moving existing ports."""
    cameras: list[Camera] = []
    for index, key in enumerate(("camera_serial", "camera_serial_2"), start=1):
        value = raw.get(key)
        if value is None or value == "" or (isinstance(value, str) and not value.strip()):
            continue
        cameras.append(Camera(f"Camera {index}", validate_serial(value), FIRST_PORT + index - 1))

    entries = raw.get("cameras", [])
    if not isinstance(entries, list):
        raise ValueError("The cameras option must be a list.")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each camera must have a name, serial and port.")
        serial = validate_serial(entry.get("serial"))
        port = validate_port(entry["port"]) if "port" in entry else next_port(cameras)
        cameras.append(Camera(validate_name(entry.get("name", f"Camera {port - FIRST_PORT + 1}")), serial, port))

    if len(cameras) > MAX_CAMERAS:
        raise ValueError(f"This app supports up to {MAX_CAMERAS} cameras.")
    if len({camera.serial for camera in cameras}) != len(cameras):
        raise ValueError("Each camera must have a different serial.")
    if len({camera.port for camera in cameras}) != len(cameras):
        raise ValueError("Each camera must have a different port.")
    return tuple(sorted(cameras, key=lambda camera: camera.port))


def with_cameras(raw: dict[str, object], cameras: list[Camera] | tuple[Camera, ...]) -> dict[str, object]:
    """Migrate camera fields only; keep account settings and secret references."""
    updated = dict(raw)
    updated.update(camera_serial="", camera_serial_2="", cameras=[camera.as_dict() for camera in cameras])
    parse_cameras(updated)
    return updated
