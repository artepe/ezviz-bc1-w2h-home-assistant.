"""Bounded, transient EZVIZ VTM packet metadata probe.

Only fixed-shape metadata reaches stdout. Camera media bodies are never saved
or returned, and upstream exceptions (which may embed cloud URLs/tokens) are
silenced. This file is only invoked by the authenticated camera manager.
"""

from __future__ import annotations

import argparse
import socket
from contextlib import suppress
import json
from pathlib import Path
import sys
import time


STAGES = frozenset({"TOKEN_READ", "CLIENT_INIT", "CLOUD_LOOKUP", "VTM_HANDSHAKE", "MEDIA_READ"})
CODES = frozenset({
    "SESSION_MISSING", "TOKEN_MISSING", "TOKEN_UNREADABLE", "TOKEN_INVALID",
    "TIMEOUT", "CONNECTION_FAILED", "CLOUD_HTTP_ERROR", "CLOUD_AUTH_REJECTED",
    "VTM_UNREACHABLE", "UPSTREAM_DEVICE_ERROR", "UPSTREAM_MEDIA_ERROR",
    "UPSTREAM_PARSE_ERROR", "UNEXPECTED_ERROR",
})


def classify_error(exc: Exception) -> tuple[str, int | None]:
    """Map Python exceptions to safe fixed codes, never pass their messages on."""
    kind = type(exc).__name__
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    http_status = status if type(status) is int and 100 <= status <= 599 else None
    if http_status in (401, 403):
        return "CLOUD_AUTH_REJECTED", http_status
    if http_status is not None:
        return "CLOUD_HTTP_ERROR", http_status
    if isinstance(exc, FileNotFoundError):
        return "TOKEN_MISSING", None
    if isinstance(exc, PermissionError):
        return "TOKEN_UNREADABLE", None
    if isinstance(exc, json.JSONDecodeError):
        return "TOKEN_INVALID", None
    if isinstance(exc, (socket.timeout, TimeoutError)) or kind in (
        "ConnectTimeout", "ReadTimeout", "Timeout", "EzvizNoMediaError",
        "_VtmReadDeadlineExpired",
    ):
        return "TIMEOUT", None
    if isinstance(exc, (ConnectionError, ConnectionRefusedError)) or kind in (
        "ConnectionError", "NewConnectionError", "ConnectionResetError",
    ):
        return "CONNECTION_FAILED", None
    if kind in ("DeviceException", "EzvizDeviceException"):
        return "VTM_UNREACHABLE", None
    if kind in ("PyEzvizError", "EzvizApiError"):
        return "UPSTREAM_DEVICE_ERROR", None
    if kind in ("EzvizUnsupportedMediaError", "UnsupportedRtpVideoCodecError"):
        return "UPSTREAM_MEDIA_ERROR", None
    if kind in ("ValueError", "KeyError", "TypeError"):
        return "UPSTREAM_PARSE_ERROR", None
    return "UNEXPECTED_ERROR", None


def report_error(stage: str, exc: Exception, events: list[dict] | None = None) -> dict:
    """Only immutable status metadata crosses the process boundary."""
    code, http_status = classify_error(exc)
    result: dict[str, object] = {
        "ok": False,
        "stage": stage if stage in STAGES else "UNKNOWN",
        "code": code,
    }
    if http_status is not None:
        result["http_status"] = http_status
    # Never add raw exceptions, response bodies, filenames, URLs, session IDs,
    # media bytes, access keys or token values.
    if events:
        result["events"] = events[:25]
    return result


class CloudPhaseError(Exception):
    """Private phase wrapper: never format/print its original exception."""

    def __init__(self, stage: str, error: Exception, events: list[dict] | None = None):
        self.stage = stage
        self.error = error
        self.events = events


def collect_packet_metadata(client, serial: str, *, max_packets: int = 24) -> list[dict]:
    """Start a real live VTM stream before classifying its packets."""
    from pyezvizapi.cloud_stream import open_cloud_stream
    from pyezvizapi.stream_transport import summarize_vtm_packet

    # The wrapper reports this phase separately from TCP/VTM negotiation.
    try:
        stream = open_cloud_stream(client, serial, timeout=10.0)
    except Exception as exc:
        raise CloudPhaseError("CLOUD_LOOKUP", exc) from None
    try:
        # The handshake itself consumes StreamInfoRsp packets; they are not
        # subsequently visible to iter_packets. Report only its safe status,
        # never the negotiated URL, session ID, public keys or stream tokens.
        try:
            negotiation = stream.start(deadline=time.monotonic() + 12.0)
        except Exception as exc:
            raise CloudPhaseError("VTM_HANDSHAKE", exc) from None
        result_code = getattr(negotiation, "result", None)
        if type(result_code) is not int or not -32768 <= result_code <= 32767:
            result_code = None
        items = [{
            "channel_name": "HANDSHAKE",
            "result_code": result_code,
            "has_stream_session": bool(getattr(negotiation, "streamssn", None)),
        }]
        # A BC1 may wake slowly. The previous 10-second packet wait could
        # return [] even though VTM handshake succeeded and a late keyframe
        # would appear afterward. Do not silently call that "camera offline".
        try:
            for index, packet in enumerate(stream.iter_packets(
                max_packets=max_packets,
                duration_seconds=28.0,
                duration_from_start=True,
                first_packet_timeout=25.0,
                stream_packet_timeout_seconds=20.0,
                include_control=True,
            )):
                # summarize_vtm_packet deliberately omits packet.body, stream URLs,
                # session tokens and decryption keys.
                items.append(summarize_vtm_packet(packet, index=index).as_dict())
        except Exception as exc:
            raise CloudPhaseError("MEDIA_READ", exc, items) from None
        return items
    finally:
        stream.close()


def execute(token_path: Path, serial: str) -> dict | list[dict]:
    """Return safe structured outcome for each source-bootstrap phase."""
    try:
        token = json.loads(token_path.read_text(encoding="utf-8"))
        if not isinstance(token, dict) or not token.get("session_id"):
            return {"ok": False, "stage": "TOKEN_READ", "code": "SESSION_MISSING"}
    except Exception as exc:
        return report_error("TOKEN_READ", exc)

    try:
        from pyezvizapi.client import EzvizClient
        client = EzvizClient(token=token)
    except Exception as exc:
        return report_error("CLIENT_INIT", exc)
    try:
        try:
            return collect_packet_metadata(client, serial)
        except CloudPhaseError as exc:
            return report_error(exc.stage, exc.error, exc.events)
        except Exception as exc:
            return report_error("MEDIA_READ", exc)
    finally:
        with suppress(Exception):
            client.close_session()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()

    # The command prints exactly one structured JSON result. A diagnostic
    # failure is not a subprocess crash; all raw exceptions stay private.
    result = execute(Path(args.token_file), args.serial)
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
