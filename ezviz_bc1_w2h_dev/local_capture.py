"""Run the pinned SDK with private static credentials and LAN egress only.

No token, CAS refresh, P2P registration, media-key lookup or fallback.
The real W2H authentication and channel mapping still require qualification.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import socket
import stat
import sys

from hybrid_proxy import local_ipv4


def read_credentials(path: Path, serial: str):
    try:
        if path.is_symlink():
            raise ValueError
        with path.open("rb") as source:
            import os
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError
            payload = source.read(65537)
        if len(payload) > 65536:
            raise ValueError
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError
        endpoint, cas = data["endpoint"], data["cas"]
        if not isinstance(endpoint, dict) or not isinstance(cas, dict):
            raise ValueError
        host = local_ipv4(endpoint["host"])
        channel = data["channel"]
        if (data["serial"] != serial or not host or type(channel) is not int
                or not 1 <= channel <= 256
                or endpoint.get("command_port", 9010) != 9010
                or endpoint.get("stream_port", 9020) != 9020
                or not all(isinstance(cas.get(k), str) and cas[k] for k in ("key", "operation_code"))):
            raise ValueError
        return host, channel
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("Local credentials missing or invalid; cloud access is disabled.") from None


def install_lan_guard(host):
    """Restrict Python socket traffic to this numeric hub address and SDK ports."""
    original_socket = socket.socket
    original_resolver = socket.getaddrinfo

    def allowed(address):
        if not isinstance(address, tuple) or len(address) < 2 or address[0] != host or address[1] not in (9010, 9020):
            raise OSError("Local-only network policy blocked the destination.")

    class LanSocket(original_socket):
        def connect(self, address):
            allowed(address)
            return super().connect(address)

        def connect_ex(self, address):
            allowed(address)
            return super().connect_ex(address)

        def sendto(self, data, *args):
            allowed(args[-1])
            return super().sendto(data, *args)

    def resolve(node, port, *args, **kwargs):
        allowed((node, port))
        return original_resolver(node, port, *args, **kwargs)

    socket.socket = LanSocket
    socket.getaddrinfo = resolve


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        return 2
    path, serial = Path(args[0]), args[1]
    try:
        host, channel = read_credentials(path, serial)
        install_lan_guard(host)
        # Prevent upstream debug log configuration from exposing authentication.
        logging.disable(logging.CRITICAL)
        from pyezvizapi.__main__ import main as sdk_main
        return sdk_main([
            "stream", "local-sdk-dump", "--credentials-file", str(path),
            "--serial", serial, "--host", host, "--channel", str(channel),
            "--command-port", "9010", "--stream-port", "9020",
            "--format", "mpegts", "--duration", "0", "--output", "-",
        ])
    except Exception:
        # Neither exception text nor source credentials belong in logs.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
