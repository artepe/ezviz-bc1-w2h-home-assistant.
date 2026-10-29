"""Optional EZVIZ BC1 hybrid HTTP MPEG-TS endpoint.

Cloud proxy on 8558+ remains untouched. New endpoint 8658 tries the
experimental local SDK once per viewer, then falls back to the existing
cloud proxy. The LAN SDK still needs EZVIZ CAS authorization; this is
not an independently verified offline W2H client.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

PORT = 8658
CLI = "/opt/ezviz-venv/bin/pyezvizapi"
PROBE_SECONDS = 32
LAN_COOLDOWN = 300


def local_ipv4(value: object) -> str:
    """Accept only private IPv4 addresses for a LAN service."""
    if not isinstance(value, str) or not value:
        return ""
    try:
        address = ipaddress.IPv4Address(value.strip())
    except ipaddress.AddressValueError:
        return ""
    return str(address) if address.is_private and not address.is_loopback and not address.is_link_local else ""


def lan_client_address(hub_ip: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((hub_ip, 9010))
        return str(sock.getsockname()[0])


def terminate(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def next_bytes(process: subprocess.Popen, deadline: float) -> bytes:
    """Read from the process pipe without waiting for a full buffer."""
    assert process.stdout is not None
    fd = process.stdout.fileno()
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], min(0.5, max(0.0, deadline - time.monotonic())))
        if ready:
            return os.read(fd, 8192)
        if process.poll() is not None:
            # A pipe may still contain the last bytes even after exit.
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                return b""
    return b""


class HybridService:
    """One shared local listening endpoint, one worker per HTTP view."""

    def __init__(self, get_workers):
        self.get_workers = get_workers
        self.lock = threading.RLock()
        self.mode = "auto"
        self.hub_ip = ""
        self.cas_serial = ""
        self.cooldowns: dict[str, float] = {}
        service = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "EZVIZ-Hybrid/0.1"
            def log_message(self, _format, *_args):
                # Do not log path/serial, URLs, tokens or upstream responses.
                return

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/status":
                    payload = json.dumps(service.status()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if not path.endswith(".ts") or "/" in path[1:]:
                    self.send_error(404)
                    return
                serial = unquote(path[1:-3])
                worker = next((w for w in service.get_workers() if w.serial == serial), None)
                if worker is None:
                    self.send_error(404)
                    return
                service.stream(self, worker)

        self.server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name="ezviz-hybrid", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def configure(self, options: dict):
        mode = options.get("hybrid_mode", "auto")
        if mode not in ("auto", "local", "cloud"):
            mode = "auto"
        hub = local_ipv4(options.get("lan_hub_ip", ""))
        cas = options.get("lan_cas_serial", "")
        cas = cas.strip() if isinstance(cas, str) and cas.isalnum() and len(cas) <= 32 else ""
        with self.lock:
            self.mode, self.hub_ip, self.cas_serial = mode, hub, cas

    def status(self):
        with self.lock:
            mode, hub, cooldowns = self.mode, self.hub_ip, dict(self.cooldowns)
        workers = tuple(self.get_workers())
        now = time.monotonic()
        return {
            "mode": mode,
            "lan_configured": bool(hub),
            "cameras": [
                {"index": w.index, "lan_retry_seconds": max(0, int(cooldowns.get(w.serial, 0) - now))}
                for w in workers
            ],
            "note": "Proxy listening is not proof of live video. LAN needs CAS authorization.",
        }

    def mark_lan_failure(self, serial: str) -> None:
        with self.lock:
            self.cooldowns[serial] = time.monotonic() + LAN_COOLDOWN

    def local_command(self, worker, hub: str, cas_serial: str):
        if not Path(worker.token).is_file():
            return None
        client_ip = lan_client_address(hub)
        return [
            CLI, "--token-file", str(worker.token),
            "stream", "local-sdk-dump",
            "--host", hub, "--serial", worker.serial,
            "--command-port", "9010", "--stream-port", "9020",
            "--fetch-cas", "--cas-serial", cas_serial or worker.serial.split("-")[0],
            "--inner-address", client_ip, "--inner-port", "9020",
            "--format", "mpegts", "--duration", "0", "--output", "-",
        ]

    def open_local(self, worker, hub: str, cas_serial: str):
        try:
            cmd = self.local_command(worker, hub, cas_serial)
            if cmd is None:
                return None
            process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            first = next_bytes(process, time.monotonic() + PROBE_SECONDS)
            if not first or first[0] != 0x47:
                terminate(process)
                self.mark_lan_failure(worker.serial)
                return None
            return process, first
        except (OSError, ValueError, subprocess.SubprocessError):
            self.mark_lan_failure(worker.serial)
            return None

    def open_cloud(self, worker):
        url = "http://127.0.0.1:" + str(worker.port) + "/" + worker.serial + ".ts"
        try:
            response = urlopen(url, timeout=35)
            first = response.read(188)
            if not first or first[0] != 0x47:
                response.close()
                return None
            return response, first
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            return None

    def stream(self, handler: BaseHTTPRequestHandler, worker):
        with self.lock:
            mode, hub, cas = self.mode, self.hub_ip, self.cas_serial
            cooldown = self.cooldowns.get(worker.serial, 0)
        transport = None
        first = b""
        kind = ""
        if mode in ("auto", "local") and hub and time.monotonic() >= cooldown:
            local = self.open_local(worker, hub, cas)
            if local is not None:
                transport, first = local
                kind = "local"
        if transport is None and mode in ("auto", "cloud"):
            cloud = self.open_cloud(worker)
            if cloud is not None:
                transport, first = cloud
                kind = "cloud"
        if transport is None:
            handler.send_response(503)
            handler.send_header("Content-Type", "text/plain; charset=utf-8")
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(b"No live video: LAN or EZVIZ cloud session unavailable.\n")
            return
        try:
            handler.send_response(200)
            handler.send_header("Content-Type", "video/mp2t")
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("X-EZVIZ-Source", kind)
            handler.end_headers()
            handler.wfile.write(first)
            if kind == "local":
                assert isinstance(transport, subprocess.Popen)
                assert transport.stdout is not None
                while True:
                    chunk = next_bytes(transport, time.monotonic() + 60)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
            else:
                while True:
                    chunk = transport.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError, TimeoutError):
            pass
        finally:
            if kind == "local":
                terminate(transport)
            else:
                transport.close()
