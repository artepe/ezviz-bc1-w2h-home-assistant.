"""Run the pinned SDK with private static credentials and LAN egress only.

No token, CAS refresh, P2P registration, media-key lookup or fallback.
The real W2H authentication and channel mapping still require qualification.
"""
from __future__ import annotations

import json
import os
import logging
from pathlib import Path
import socket
import stat
import sys

from hybrid_proxy import local_ipv4
from local_diagnostics import LocalCredentialError


def read_credentials(path: Path, serial: str):
    try:
        if path.is_symlink():
            raise ValueError
        # Refuse symlink races and avoid blocking on a FIFO in the UI poll.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError
            payload = source.read(65537)
        if len(payload) > 65536:
            raise ValueError
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError
        endpoint, cas = data["endpoint"], data.get("cas", {})
        if not isinstance(endpoint, dict) or not isinstance(cas, dict):
            raise ValueError
        host = local_ipv4(endpoint["host"])
        channel = data.get("channel")
        if type(channel) is not int or not 1 <= channel <= 256:
            raise LocalCredentialError("CHANNEL_INVALID")
        if not all(isinstance(cas.get(k), str) and cas[k] for k in ("key", "operation_code")):
            raise LocalCredentialError("INVALID_CREDENTIALS")
        if (data["serial"] != serial or not host
                or endpoint.get("command_port", 9010) != 9010
                or endpoint.get("stream_port", 9020) != 9020):
            raise ValueError
        return host, channel
    except LocalCredentialError:
        raise
    except FileNotFoundError:
        raise LocalCredentialError("MISSING_CREDENTIALS") from None
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise LocalCredentialError("INVALID_CREDENTIALS") from None


_emitted_events = set()


def emit_event(event):
    import os
    from local_diagnostics import EVENTS
    if event in EVENTS and event not in _emitted_events and os.environ.get("LOCAL_DIAGNOSTIC_FD"):
        os.write(int(os.environ["LOCAL_DIAGNOSTIC_FD"]), (event + "\n").encode("ascii"))
        _emitted_events.add(event)


def observe_sdk(sdk_module):
    """Process-local hooks for the pinned SDK; return a restoration callback."""
    cls = sdk_module.EzvizLocalSdkClient
    send, read = cls.send_encrypted_command, cls.read_stream_frame_after_prefix
    def observed_send(self, command, *args, **kwargs):
        result = send(self, command, *args, **kwargs)
        response = result.response
        if command == 0x2011 and response.header.command == 0x2012:
            fields = sdk_module.parse_ezviz_local_sdk_xml_fields(response)
            session = fields.get("Session", "")
            if (fields.get("Result") == "0" and session.isascii()
                    and session.isdigit() and len(session) <= 10
                    and 0 < int(session) <= 0x7fffffff):
                emit_event("PREVIEW_ACCEPTED")
        if command == 0x3105 and response.header.command == 0x3106:
            emit_event("STREAM_SETUP")
        return result
    def observed_read(self, *args, **kwargs):
        result = read(self, *args, **kwargs)
        if result is not None:
            emit_event("MEDIA_FRAME")
        return result
    cls.send_encrypted_command, cls.read_stream_frame_after_prefix = observed_send, observed_read
    def restore():
        cls.send_encrypted_command, cls.read_stream_frame_after_prefix = send, read
    return restore


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
            try:
                result = super().connect(address)
            except OSError:
                emit_event("TCP_CONNECT_FAILED")
                raise
            emit_event("TCP_CONNECTED")
            return result

        def connect_ex(self, address):
            allowed(address)
            result = super().connect_ex(address)
            emit_event("TCP_CONNECTED" if result == 0 else "TCP_CONNECT_FAILED")
            return result

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
    if len(args) not in (2, 3):
        return 2
    duration = "0"
    if len(args) == 3:
        try:
            seconds = int(args[2])
        except ValueError:
            return 2
        if not 1 <= seconds <= 60:
            return 2
        duration = str(seconds) + "s"
    path, serial = Path(args[0]), args[1]
    try:
        host, channel = read_credentials(path, serial)
        install_lan_guard(host)
        # Prevent upstream debug log configuration from exposing authentication.
        logging.disable(logging.CRITICAL)
        from pyezvizapi.__main__ import main as sdk_main
        sdk = sys.modules["pyezvizapi.__main__"]
        from pyezvizapi import hcnetsdk
        restore_observer = observe_sdk(hcnetsdk)
        # The pinned CLI otherwise catches PyEzvizError and loses its stage.
        # Translate inside its handler; never emit exception text to stderr.
        original = sdk._handle_local_sdk_stream_dump
        def diagnosed(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except (OSError, TimeoutError):
                return 22
            except Exception as error:
                if str(error) == "EZVIZ local SDK AES key must be 16 bytes":
                    return 24
                if str(error).startswith("EZVIZ local preview response is missing Session"):
                    return 21
                return 23
        sdk._handle_local_sdk_stream_dump = diagnosed
        try:
            return sdk_main([
                "stream", "local-sdk-dump", "--credentials-file", str(path),
                "--serial", serial, "--host", host, "--channel", str(channel),
                "--command-port", "9010", "--stream-port", "9020",
                "--format", "mpegts", "--duration", duration, "--output", "-",
            ])
        finally:
            sdk._handle_local_sdk_stream_dump = original
            restore_observer()
    except Exception:
        # Neither exception text nor source credentials belong in logs.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
