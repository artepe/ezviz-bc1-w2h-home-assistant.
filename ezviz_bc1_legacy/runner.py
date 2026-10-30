"""Isolated legacy EZVIZ BC1/W2H cloud proxy, recovered from first working release.

Upstream pyEzvizApi traces may include session tokens embedded in cloud URLs.
We suppress upstream stdout/stderr and log only generic process events.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

OPTIONS = Path("/data/options.json")
TOKEN = Path("/data/ezviz_token.json")
CLI = "/opt/ezviz-venv/bin/pyezvizapi"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8668
STOPPING = False
CURRENT: subprocess.Popen[bytes] | None = None


def log(message: str) -> None:
    print(f"[BC1/W2H] {message}", flush=True)


def stop(_signum: int, _frame: object) -> None:
    """Handle shutdown from Home Assistant Supervisor."""
    global STOPPING
    STOPPING = True
    if CURRENT is not None and CURRENT.poll() is None:
        CURRENT.terminate()


def parse_options(raw: dict[str, object]) -> tuple[str, str, str, bool, int]:
    serial = str(raw.get("camera_serial") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{5,128}", serial):
        raise ValueError(
            "Set camera_serial to the BC1 subcamera serial from 'devices status' "
            "(often HUB_SERIAL-CAMERA_SERIAL)."
        )
    username = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    force_relogin = raw.get("force_relogin", False) is True
    delay = int(raw.get("restart_delay", 30))
    if not 10 <= delay <= 300:
        raise ValueError("restart_delay must be between 10 and 300 seconds")
    return serial, username, password, force_relogin, delay


def login(username: str, password: str) -> bool:
    """Save first EZVIZ session token privately in /data.

    Credentials are passed to a short-lived CLI process and may be visible
    within the container's process namespace during authentication.
    """
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
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log("Login timed out: check the EZVIZ cloud connection and DNS.")
        return False
    except OSError:
        log("Could not start pyEzvizApi.")
        return False

    if result.returncode != 0 or not TOKEN.is_file() or TOKEN.stat().st_size == 0:
        log("EZVIZ login failed. Check account, region, password or MFA.")
        return False

    TOKEN.chmod(0o600)
    log("EZVIZ token saved in private add-on storage (/data).")
    return True


def pause(seconds: int) -> None:
    for _ in range(seconds):
        if STOPPING:
            break
        time.sleep(1)


def main() -> int:
    global CURRENT
    os.umask(0o077)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        raw = json.loads(OPTIONS.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Options must be a JSON object.")
        serial, username, password, force_relogin, retry = parse_options(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        log(f"Configuration error: {exc}")
        return 2

    if force_relogin and TOKEN.exists():
        TOKEN.unlink()
        log("Previously saved token cleared because force_relogin=true.")

    if not TOKEN.is_file() or TOKEN.stat().st_size == 0:
        if not login(username, password):
            return 3

    log("Starting cloud-based BC1 proxy bound to 127.0.0.1:8558 (local only).")
    log("Update the existing go2rtc source to the local proxy URL.")

    cmd = [
        CLI, "--token-file", str(TOKEN), "--save-token",
        "stream", "proxy",
        "--serial", serial,
        "--listen-host", LISTEN_HOST,
        "--listen-port", str(LISTEN_PORT),
    ]
    while not STOPPING:
        try:
            CURRENT = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            log("Cannot start pyEzvizApi proxy process.")
            return 4

        log("Proxy process started. Open go2rtc stream to test video.")
        while not STOPPING and CURRENT.poll() is None:
            time.sleep(1)

        if STOPPING:
            if CURRENT.poll() is None:
                CURRENT.terminate()
            try:
                CURRENT.wait(timeout=5)
            except subprocess.TimeoutExpired:
                CURRENT.kill()
                CURRENT.wait(timeout=5)
            break

        log(
            f"Proxy stopped (exit status {CURRENT.returncode}). "
            f"Retrying in {retry}s; upstream error details hidden to prevent token leaks."
        )
        pause(retry)

    log("Add-on stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
