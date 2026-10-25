"""EZVIZ BC1/W2H proxy launcher for Home Assistant OS.

Each configured camera has its own supervised proxy and private token file.
Raw upstream output is hidden because cloud URLs can contain session tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from camera_config import Camera, parse_cameras
from supervisor_client import SettingsError, SupervisorClient

OPTIONS = Path("/data/options.json")
TOKEN = Path("/data/ezviz_token.json")
CLI = "/opt/ezviz-venv/bin/pyezvizapi"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8558
STOPPING = False
LOGIN_PROCESS: subprocess.Popen[bytes] | None = None


@dataclass
class ProxyWorker:
    index: int
    serial: str
    port: int
    token: Path
    process: subprocess.Popen[bytes] | None = None
    retry_at: float = 0.0
    name: str = ""


WORKERS: list[ProxyWorker] = []


def summarize_cloud_trace(output: bytes) -> dict[str, object]:
    """Aggregate allowlisted VTM transport metadata; no packet bodies or tokens."""
    try:
        events = json.loads(output)
    except (ValueError, UnicodeDecodeError):
        return {"ok": False, "message": "Cloud trace output was not valid JSON. No private output was shown."}
    if not isinstance(events, list) or len(events) > 32:
        return {"ok": False, "message": "Cloud trace returned an unexpected number of events."}
    counts = {key: 0 for key in ("RTP", "MPEG_PS", "MPEG_TS", "UNKNOWN")}
    encrypted = 0
    streams = 0
    for event in events:
        if not isinstance(event, dict):
            return {"ok": False, "message": "Cloud trace returned invalid packet metadata."}
        if event.get("channel_name") != "STREAM":
            continue
        streams += 1
        transport = event.get("transport")
        counts[transport if isinstance(transport, str) and transport in counts else "UNKNOWN"] += 1
        if event.get("encrypted") is True:
            encrypted += 1
    if not streams:
        return {"ok": False, "message": f"Cloud trace: {len(events)} control packets, but no video-channel packets. The EZVIZ VTM stream did not deliver video data during the bounded probe."}
    return {"ok": True, "message": (
        f"Cloud media diagnosis: {streams} video-channel packets; "
        f"RTP={counts['RTP']}, MPEG_PS={counts['MPEG_PS']}, "
        f"MPEG_TS={counts['MPEG_TS']}, UNKNOWN={counts['UNKNOWN']}; "
        f"encrypted={encrypted}. These are source packet types, not decoded video frames. "
        "No video bytes, URLs, credentials or tokens were saved or returned."
    )}


def log(message: str) -> None:
    print(f"[BC1/W2H] {message}", flush=True)


def signal_process_group(process: subprocess.Popen[bytes], signum: int) -> None:
    """Signal the owned CLI process and its FFmpeg children."""
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def stop(_signum: int, _frame: object) -> None:
    global STOPPING
    STOPPING = True
    if LOGIN_PROCESS is not None:
        signal_process_group(LOGIN_PROCESS, signal.SIGTERM)
    for worker in WORKERS:
        if worker.process is not None:
            signal_process_group(worker.process, signal.SIGTERM)


def parse_options(
    raw: dict[str, object],
) -> tuple[tuple[str, ...], str, str, bool, int]:
    cameras = parse_cameras(raw)

    username = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    force_relogin = raw.get("force_relogin", False) is True
    delay_value = raw.get("restart_delay", 30)
    if isinstance(delay_value, bool) or not isinstance(delay_value, int):
        raise ValueError("restart_delay must be an integer")
    delay = delay_value
    if not 10 <= delay <= 300:
        raise ValueError("restart_delay must be between 10 and 300 seconds")
    return tuple(camera.serial for camera in cameras), username, password, force_relogin, delay


def login(username: str, password: str) -> bool:
    """Save the initial account session privately, without printing secrets."""
    global LOGIN_PROCESS
    if not username or not password:
        log("No saved token. Enter username and password in add-on Configuration.")
        return False

    cmd = [
        CLI, "--token-file", str(TOKEN),
        "-u", username, "-p", password,
        "--save-token", "devices", "status",
    ]
    log("Authenticating with EZVIZ; credentials and upstream logs hidden.")
    try:
        LOGIN_PROCESS = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if STOPPING:
            signal_process_group(LOGIN_PROCESS, signal.SIGTERM)
        try:
            returncode = LOGIN_PROCESS.wait(timeout=120)
        except subprocess.TimeoutExpired:
            signal_process_group(LOGIN_PROCESS, signal.SIGKILL)
            LOGIN_PROCESS.wait()
            log("Login timed out: check the EZVIZ cloud connection and DNS.")
            return False
    except OSError:
        log("Could not start pyEzvizApi.")
        return False
    finally:
        LOGIN_PROCESS = None

    if STOPPING:
        return False
    if returncode != 0 or not TOKEN.is_file() or TOKEN.stat().st_size == 0:
        log("EZVIZ login failed. Check account, region, password or MFA.")
        return False

    TOKEN.chmod(0o600)
    log("EZVIZ token saved in private add-on storage (/data).")
    return True


def prepare_workers(serials: tuple[str, ...], cameras: tuple[Camera, ...] | None = None) -> list[ProxyWorker]:
    """Retain each camera's private session and stable loopback port."""
    TOKEN.chmod(0o600)
    workers: list[ProxyWorker] = []
    configured = cameras or tuple(Camera(f"Camera {offset + 1}", serial, LISTEN_PORT + offset) for offset, serial in enumerate(serials))
    for camera in configured:
        token = TOKEN if camera.index == 1 else TOKEN.with_name(f"ezviz_token_camera_{camera.index}.json")
        if not token.is_file() or token.stat().st_size == 0:
            # Reject a partial upstream token write rather than cloning it.
            contents = TOKEN.read_bytes()
            json.loads(contents)
            temporary = token.with_suffix(".tmp")
            temporary.write_bytes(contents)
            temporary.chmod(0o600)
            temporary.replace(token)
        else:
            token.chmod(0o600)
        workers.append(
            ProxyWorker(index=camera.index, serial=camera.serial, port=camera.port, token=token, name=camera.name)
        )
    return workers


def start_worker(worker: ProxyWorker, retry: int, now: float) -> None:
    cmd = [
        CLI, "--token-file", str(worker.token), "--save-token",
        "stream", "proxy",
        "--serial", worker.serial,
        "--listen-host", LISTEN_HOST,
        "--listen-port", str(worker.port),
    ]
    try:
        worker.process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        worker.process = None
        worker.retry_at = now + retry
        log(f"Camera {worker.index}: cannot start proxy; retrying in {retry}s.")
        return
    log(
        f"Camera {worker.index}: proxy process started on "
        f"{LISTEN_HOST}:{worker.port}. Open its go2rtc stream to test video."
    )


def poll_workers(workers: list[ProxyWorker], retry: int, now: float) -> None:
    """Restart only the worker that failed, after its own retry delay."""
    for worker in workers:
        if STOPPING:
            return
        if worker.process is not None:
            status = worker.process.poll()
            if status is None:
                continue
            signal_process_group(worker.process, signal.SIGKILL)
            worker.process = None
            worker.retry_at = now + retry
            log(
                f"Camera {worker.index}: proxy stopped (exit status {status}); "
                f"retrying in {retry}s. Upstream error details hidden."
            )
        if now >= worker.retry_at:
            start_worker(worker, retry, now)


def shutdown_workers(workers: list[ProxyWorker]) -> None:
    """Stop all owned process groups with a shared five-second deadline."""
    for worker in workers:
        if worker.process is not None:
            signal_process_group(worker.process, signal.SIGTERM)
    deadline = time.monotonic() + 5
    for worker in workers:
        process = worker.process
        if process is None:
            continue
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            log(f"Camera {worker.index}: forcing proxy shutdown.")
        finally:
            signal_process_group(process, signal.SIGKILL)
            process.wait()
            worker.process = None


class Runtime:
    """Reconcile saved cameras without restarting an unaffected camera."""

    def __init__(self):
        self.lock = threading.RLock()
        self.reload = threading.Event()
        self.cameras: tuple[Camera, ...] = ()
        self.message = "Loading camera settings."
        self.last_force = False
        self.login_retry_at = 0.0
        self.refresh_pending = False
        self.last_refresh_requested = float("-inf")
        self.last_proxy_restart: dict[int, float] = {}
        self.cloud_trace_lock = threading.Lock()
        self.last_cloud_trace: dict[int, float] = {}

    def trace_cloud(self, port: int) -> dict[str, object]:
        """User-initiated, bounded upstream VTM metadata probe for one camera."""
        now = time.monotonic()
        with self.lock:
            worker = next((w for w in WORKERS if w.port == port and w.process is not None and w.process.poll() is None), None)
            if worker is None:
                return {"ok": False, "message": "The selected camera proxy is not running. Check its app log."}
            if now - self.last_cloud_trace.get(port, float("-inf")) < 90:
                return {"ok": False, "message": "The cloud trace is limited to once per 90 seconds for each camera."}
            if not self.cloud_trace_lock.acquire(blocking=False):
                return {"ok": False, "message": "Another camera cloud trace is already in progress."}
            self.last_cloud_trace[port] = now
            serial, token = worker.serial, worker.token
        try:
            completed = subprocess.run(
                ["/opt/ezviz-venv/bin/python", "/app/cloud_inspect.py",
                 "--token-file", str(token), "--serial", serial],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=45,
                check=False,
            )
            if completed.returncode != 0:
                return {"ok": False, "message": "Cloud trace failed before usable VTM packet metadata was returned. Check the EZVIZ cloud connection."}
            return summarize_cloud_trace(completed.stdout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": "Cloud trace timed out after 45 seconds. The camera may be asleep or the cloud session is not delivering packets."}
        except OSError:
            return {"ok": False, "message": "Could not start the private cloud trace command in the EZVIZ app container."}
        finally:
            self.cloud_trace_lock.release()

    def restart_camera(self, port: int) -> bool:
        """Restart one stuck local proxy after connectivity returns.

        Explicitly user-initiated: probing every sleeping battery camera in the
        background would consume power and can hammer the EZVIZ cloud. Do not
        delete tokens or affect other camera processes. Limit to one retry per
        camera per minute to avoid concurrent or repeated stream restarts.
        """
        now = time.monotonic()
        with self.lock:
            worker = next((entry for entry in WORKERS if entry.port == port), None)
            if worker is None:
                return False
            if now - self.last_proxy_restart.get(port, float("-inf")) < 60:
                return False
            self.last_proxy_restart[port] = now
            if worker.process is not None:
                shutdown_workers([worker])
            worker.retry_at = 0.0
            self.reload.set()
            log(f"Camera {worker.index}: local proxy restart requested after connectivity loss.")
            return True

    def request_session_refresh(self) -> bool:
        """Coalesce stale-session recovery and rate-limit it to once per five minutes.

        Called by the camera manager only after a known authentication/session
        failure, never for generic timeouts or sleeping battery cameras.
        """
        now = time.monotonic()
        with self.lock:
            if self.refresh_pending or now - self.last_refresh_requested < 300:
                return False
            self.last_refresh_requested = now
            self.refresh_pending = True
            self.reload.set()
            return True

    def apply(self, raw: dict[str, object], now: float) -> None:
        global WORKERS
        try:
            serials, username, password, force_relogin, retry = parse_options(raw)
            cameras = parse_cameras(raw)
        except (ValueError, TypeError):
            with self.lock:
                self.message = "Invalid camera settings. Check names, serials, duplicate ports and restart_delay."
            return

        with self.lock:
            self.cameras = cameras
            desired = {camera.port: camera for camera in cameras}
            removed = [worker for worker in WORKERS if worker.port not in desired or desired[worker.port].serial != worker.serial]
            force_requested = force_relogin and not self.last_force
            refresh_requested = self.refresh_pending
            self.refresh_pending = False
            if force_requested or refresh_requested:
                removed = list(WORKERS)
            self.last_force = force_relogin
        # Don't hold the UI lock while waiting for subprocesses or cloud login.
        shutdown_workers(removed)
        with self.lock:
            WORKERS = [worker for worker in WORKERS if worker not in removed]
            poll_workers(WORKERS, retry, now)
        if force_requested or refresh_requested:
            self.clear_tokens()
            if refresh_requested:
                log("EZVIZ cloud session rejected; refreshing saved session and camera proxies.")

        if not cameras:
            with self.lock:
                self.message = "Ready. Select Add new camera to get started."
            return

        if not TOKEN.is_file() or TOKEN.stat().st_size == 0:
            if now < self.login_retry_at:
                return
            self.login_retry_at = now + retry
            with self.lock:
                self.message = "Signing in to EZVIZ." if username and password else "Enter your EZVIZ username and password in the app Configuration tab."
            if not login(username, password):
                with self.lock:
                    self.message = "EZVIZ sign-in is unavailable. Check the account settings, internet connection and app log."
                return
        if STOPPING:
            return

        try:
            with self.lock:
                existing = {worker.port: worker for worker in WORKERS}
            new_cameras = tuple(camera for camera in cameras if camera.port not in existing)
            added = prepare_workers(tuple(camera.serial for camera in new_cameras), new_cameras) if new_cameras else []
        except (OSError, ValueError):
            with self.lock:
                self.message = "Preparing the camera sessions. Retrying shortly."
            return
        with self.lock:
            WORKERS.extend(added)
            for worker in WORKERS:
                worker.name = desired[worker.port].name
            poll_workers(WORKERS, retry, now)
            self.message = "Settings loaded. Proxy ready means the local service is listening; test each camera for video."

    @staticmethod
    def clear_tokens() -> None:
        for token in (TOKEN, *TOKEN.parent.glob("ezviz_token_camera_*.json")):
            token.unlink(missing_ok=True)
        log("Saved camera sessions cleared for a new login.")

    def snapshot(self) -> dict[str, object]:
        import socket

        with self.lock:
            cameras = self.cameras
            message = self.message
            processes = {worker.port: worker.process is not None and worker.process.poll() is None for worker in WORKERS}
        states = []
        for camera in cameras:
            running = processes.get(camera.port, False)
            listening = False
            if running:
                try:
                    with socket.create_connection((LISTEN_HOST, camera.port), timeout=0.15):
                        listening = True
                except OSError:
                    pass
            states.append({**camera.as_dict(), "stream": camera.stream,
                           "status": "ready" if listening else "starting" if running else "waiting",
                           **camera.snippets()})
        return {"message": message, "cameras": states}


def main() -> int:
    from web import start_server

    os.umask(0o077)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    client = SupervisorClient()
    runtime = Runtime()
    try:
        raw = json.loads(OPTIONS.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    try:
        server = start_server(client, runtime)
    except OSError:
        log("Cannot open the camera manager ingress port. Check for a port conflict on 8788.")
        return 5
    log("Camera manager ready through Home Assistant ingress. Open Web UI to add a camera.")
    next_reload = 0.0
    supervisor_error: str | None = None
    last_supervisor_warning = float("-inf")
    try:
        while not STOPPING:
            now = time.monotonic()
            if runtime.reload.is_set() or now >= next_reload:
                runtime.reload.clear()
                next_reload = now + 15
                try:
                    raw = client.effective_options()
                except SettingsError as error:
                    # SettingsError contains controlled messages, never upstream
                    # response bodies, account options or token values.
                    reason = str(error)
                    if reason != supervisor_error or now - last_supervisor_warning >= 300:
                        log(f"Supervisor settings unavailable: {reason} Retaining the last loaded configuration.")
                        last_supervisor_warning = now
                    supervisor_error = reason
                else:
                    if supervisor_error is not None:
                        log("Supervisor settings connection restored.")
                    supervisor_error = None
            runtime.apply(raw, now)
            runtime.reload.wait(timeout=1)
    finally:
        server.shutdown()
        server.server_close()
        shutdown_workers(WORKERS)
    log("Add-on stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
