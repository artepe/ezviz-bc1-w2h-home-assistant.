"""Small ingress-only camera manager. No credentials are sent to the browser."""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from camera_config import Camera, next_port, parse_cameras, validate_name, validate_serial
from supervisor_client import SettingsError, SupervisorClient

STATIC = Path(__file__).with_name("static")
INGRESS_HOST = "172.30.32.2"
INGRESS_PORT = 8788
MAX_BODY = 32 * 1024


class CameraService:
    def __init__(self, client: SupervisorClient, runtime):
        self.client = client
        self.runtime = runtime

    def change(self, operation: str, payload: dict, port: int | None = None) -> None:
        with self.client.lock:
            cameras = list(parse_cameras(self.client.raw_options()))
            if operation == "add":
                name = validate_name(payload.get("name"))
                serial = self.full_serial(payload)
                cameras.append(Camera(name, serial, next_port(cameras)))
            else:
                current = next((camera for camera in cameras if camera.port == port), None)
                if current is None:
                    raise ValueError("Camera not found. Refresh this page.")
                cameras.remove(current)
                if operation == "edit":
                    cameras.append(Camera(validate_name(payload.get("name")), self.full_serial(payload), current.port))
            self.client.save_cameras(tuple(sorted(cameras, key=lambda camera: camera.port)))
        self.runtime.reload.set()

    @staticmethod
    def full_serial(payload: dict) -> str:
        serial = validate_serial(payload.get("serial"))
        hub = payload.get("hub_serial", "")
        if not isinstance(hub, str):
            raise ValueError("Enter a valid W2H base station serial.")
        if "-" not in serial and hub.strip():
            serial = f"{validate_serial(hub)}-{serial}"
        return validate_serial(serial)

    def test(self, port: int) -> dict[str, object]:
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        camera = next((camera for camera in cameras if camera.port == port), None)
        if camera is None:
            raise ValueError("Camera not found. Refresh this page.")
        try:
            with socket.create_connection(("127.0.0.1", camera.port), timeout=1):
                pass
        except OSError:
            return {"ok": False, "message": f"The local camera proxy is not listening on port {camera.port}. Wait for startup and check the app log."}

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        request = Request(f"http://127.0.0.1:{camera.port}/{camera.serial}.ts")
        try:
            with build_opener(NoRedirect).open(request, timeout=15) as response:
                packet = response.read(188)
                if response.status == 200 and len(packet) == 188 and packet[0] == 0x47:
                    return {"ok": True, "message": "Video transport data received. Open the go2rtc player to check the picture."}
                return {"ok": False, "message": "The proxy answered but did not return a complete MPEG-TS packet. Check the camera in the EZVIZ app."}
        except HTTPError as error:
            error.close()
            return {"ok": False, "message": f"The camera proxy returned HTTP {error.code}. Check the full camera serial and its access in the EZVIZ app."}
        except (OSError, URLError):
            return {"ok": False, "message": "No video data arrived within 15 seconds. Check the camera and its EZVIZ cloud connection, then try again."}


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, client, runtime, allowed_hosts=(INGRESS_HOST,)):
        self.service = CameraService(client, runtime)
        self.runtime = runtime
        self.allowed_hosts = frozenset(allowed_hosts)
        self.csrf = secrets.token_hex(32)
        super().__init__(address, CameraHandler)


class CameraHandler(BaseHTTPRequestHandler):
    server: CameraServer

    def log_message(self, *_args):
        # HTTP URLs and form bodies never belong in the app log.
        pass

    def permitted(self) -> bool:
        if self.client_address[0] not in self.server.allowed_hosts:
            self.respond(403, {"error": "Open this app through Home Assistant ingress."})
            return False
        return True

    def respond(self, status: int, body: dict | str | bytes, content_type="application/json; charset=utf-8") -> None:
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.permitted():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            prefix = self.headers.get("X-Ingress-Path", "").rstrip("/")
            if not re.fullmatch(r"/[-A-Za-z0-9_/]*", prefix) or prefix.startswith("//"):
                prefix = ""
            page = (STATIC / "index.html").read_text(encoding="utf-8")
            page = page.replace("__CSRF__", self.server.csrf).replace("__BASE__", html.escape(prefix + "/", quote=True))
            self.respond(200, page, "text/html; charset=utf-8")
        elif path in ("/app.js", "/app.css"):
            self.respond(200, (STATIC / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
        elif path == "/api/state":
            self.respond(200, {"version": os.environ.get("APP_VERSION", "development"), **self.server.runtime.snapshot()})
        elif path == "/health":
            self.respond(200, {"ok": True})
        else:
            self.respond(404, {"error": "Not found."})

    def do_POST(self):
        self.mutate("add")

    def do_PATCH(self):
        self.mutate("edit")

    def do_DELETE(self):
        self.mutate("remove")

    def mutate(self, operation):
        if not self.permitted():
            return
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf):
            self.respond(403, {"error": "This page expired. Refresh it and try again."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.respond(415, {"error": "Use a JSON request."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.respond(413, {"error": "Invalid request size."})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Invalid form data.")
        except (ValueError, UnicodeError):
            self.respond(400, {"error": "Invalid form data."})
            return
        path = urlsplit(self.path).path
        match = re.fullmatch(r"/api/cameras/(\d+)(/test)?", path)
        try:
            if operation == "add" and path == "/api/cameras":
                self.server.service.change("add", payload)
            elif match and operation == "add" and match.group(2):
                self.respond(200, self.server.service.test(int(match.group(1))))
                return
            elif match and not match.group(2) and operation in ("edit", "remove"):
                self.server.service.change(operation, payload, int(match.group(1)))
            else:
                self.respond(404, {"error": "Not found."})
                return
        except (ValueError, SettingsError) as error:
            self.respond(400 if isinstance(error, ValueError) else 503, {"error": str(error)})
            return
        except Exception:
            self.respond(500, {"error": "The operation could not be confirmed. Refresh the page and check the app log."})
            return
        self.respond(200, {"ok": True, "message": "Saved in Home Assistant and verified. Applying camera settings."})


def start_server(client, runtime):
    server = CameraServer(("0.0.0.0", INGRESS_PORT), client, runtime)
    threading.Thread(target=server.serve_forever, daemon=True, name="camera-manager").start()
    return server
