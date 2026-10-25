"""Bounded, transient EZVIZ VTM packet metadata probe.

Only fixed-shape metadata reaches stdout. Camera media bodies are never saved
or returned, and upstream exceptions (which may embed cloud URLs/tokens) are
silenced. This file is only invoked by the authenticated camera manager.
"""

from __future__ import annotations

import argparse
from contextlib import suppress
import json
from pathlib import Path
import sys
import time


def collect_packet_metadata(client, serial: str, *, max_packets: int = 24) -> list[dict]:
    """Start a real live VTM stream before classifying its packets."""
    from pyezvizapi.cloud_stream import open_cloud_stream
    from pyezvizapi.stream_transport import summarize_vtm_packet

    stream = open_cloud_stream(client, serial, timeout=10.0)
    try:
        stream.start(deadline=time.monotonic() + 10.0)
        items = []
        for index, packet in enumerate(stream.iter_packets(
            max_packets=max_packets,
            duration_seconds=12.0,
            duration_from_start=True,
            first_packet_timeout=10.0,
            stream_packet_timeout_seconds=10.0,
            include_control=True,
        )):
            # summarize_vtm_packet deliberately omits packet.body, stream URLs,
            # session tokens and decryption keys.
            items.append(summarize_vtm_packet(packet, index=index).as_dict())
        return items
    finally:
        stream.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()

    try:
        from pyezvizapi.client import EzvizClient
        token = json.loads(Path(args.token_file).read_text(encoding="utf-8"))
        if not isinstance(token, dict) or not token.get("session_id"):
            return 2
        client = EzvizClient(token=token)
        try:
            items = collect_packet_metadata(client, args.serial)
        finally:
            with suppress(Exception):
                client.close_session()
        sys.stdout.write(json.dumps(items, separators=(",", ":")) + "\n")
        return 0
    except Exception:
        # Never print a cloud exception: messages can contain secret signed URLs.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
