"""EZVIZ BC1/W2H proxy launcher for Home Assistant OS.

Each configured camera has its own supervised proxy and private token file.
Raw upstream output is hidden because cloud URLs can contain session tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

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


WORKERS: list[ProxyWorker] = []


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
    serials: list[str] = []
    for key in ("camera_serial", "camera_serial_2"):
        serial = str(raw.get(key) or "").strip()
        if key == "camera_serial_2" and not serial:
            continue
        if not re.fullmatch(r"[A-Za-z0-9-]{5,128}", serial):
            raise ValueError(
                f"Set {key} to the full BC1 subcamera serial "
                "(often HUB_SERIAL-CAMERA_SERIAL)."
            )
        if serial in serials:
            raise ValueError("The two camera serials must be different.")
        serials.append(serial)

    username = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    force_relogin = raw.get("force_relogin", False) is True
    delay = int(raw.get("restart_delay", 30))
    if not 10 <= delay <= 300:
        raise ValueError("restart_delay must be between 10 and 300 seconds")
    return tuple(serials), username, password, force_relogin, delay


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


def prepare_workers(serials: tuple[str, ...]) -> list[ProxyWorker]:
    """Clone the initial session before workers can write their own tokens."""
    TOKEN.chmod(0o600)
    workers: list[ProxyWorker] = []
    for offset, serial in enumerate(serials):
        token = TOKEN if offset == 0 else TOKEN.with_name("ezviz_token_camera_2.json")
        if offset:
            shutil.copyfile(TOKEN, token)
            token.chmod(0o600)
        workers.append(
            ProxyWorker(index=offset + 1, serial=serial, port=LISTEN_PORT + offset, token=token)
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


def main() -> int:
    global WORKERS
    os.umask(0o077)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        raw = json.loads(OPTIONS.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Options must be a JSON object.")
        serials, username, password, force_relogin, retry = parse_options(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        log(f"Configuration error: {exc}")
        return 2

    if force_relogin and TOKEN.exists():
        TOKEN.unlink()
        log("Previously saved token cleared because force_relogin=true.")

    if not TOKEN.is_file() or TOKEN.stat().st_size == 0:
        if not login(username, password):
            return 0 if STOPPING else 3
    if STOPPING:
        return 0

    try:
        WORKERS = prepare_workers(serials)
    except OSError:
        log("Could not prepare private camera token files.")
        return 4

    log(f"Starting {len(WORKERS)} cloud proxy process(es), bound to loopback only.")
    try:
        while not STOPPING:
            poll_workers(WORKERS, retry, time.monotonic())
            if not STOPPING:
                time.sleep(1)
    finally:
        shutdown_workers(WORKERS)

    log("Add-on stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
