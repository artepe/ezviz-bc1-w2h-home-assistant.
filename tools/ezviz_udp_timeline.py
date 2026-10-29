#!/usr/bin/env python3
"""Read-only fingerprint of EZVIZ BC1/W2H UDP P2P traffic in a PCAPNG file.

No network calls, credentials, packet payloads, or recordings are exported.
This is an experimental metadata analyzer, NOT a live camera client.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import ipaddress
import struct

def packets(path: Path):
    """Yield (src_ip, src_port, dst_ip, dst_port, UDP payload) from Ethernet PCAPNG."""
    with path.open("rb") as fp:
        endian = "<"
        links = []
        while True:
            header = fp.read(8)
            if not header:
                return
            if len(header) != 8:
                raise ValueError("Truncated PCAPNG header")
            if header[:4] == b"\x0a\x0d\x0d\x0a":
                bom = fp.read(4)
                if bom not in (b"\x4d\x3c\x2b\x1a", b"\x1a\x2b\x3c\x4d"):
                    raise ValueError("Invalid PCAPNG byte order marker")
                endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
                n = struct.unpack(endian + "I", header[4:])[0]
                if n < 28 or n > 100000000:
                    raise ValueError("Invalid section length")
                fp.seek(n - 12, 1)
                links = []
                continue
            n = struct.unpack(endian + "I", header[4:])[0]
            if n < 12 or n > 100000000:
                raise ValueError("Invalid block length")
            body = fp.read(n - 8)
            if len(body) != n - 8:
                raise ValueError("Truncated PCAPNG block")
            kind = struct.unpack(endian + "I", header[:4])[0]
            if kind == 1:
                links.append(struct.unpack_from(endian + "H", body)[0])
                continue
            if kind != 6 or len(body) < 24:
                continue
            interface, _, _, size, _ = struct.unpack_from(endian + "IIIII", body)
            if interface >= len(links) or links[interface] != 1:
                continue
            frame = body[20:20+size]
            if len(frame) < 42 or len(frame) != size:
                continue
            typ = int.from_bytes(frame[12:14], "big")
            pos = 14
            if typ == 0x8100 and len(frame) >= 46:
                typ = int.from_bytes(frame[16:18], "big")
                pos = 18
            if typ != 0x800:
                continue
            ip = frame[pos:]
            if not ip or ip[0] >> 4 != 4:
                continue
            ihl = (ip[0] & 15) * 4
            if ihl < 20 or len(ip) < ihl + 8 or ip[9] != 17:
                continue
            if int.from_bytes(ip[6:8], "big") & 0x3fff:
                continue
            udp = ip[ihl:]
            sport, dport, length, _ = struct.unpack_from("!HHHH", udp)
            if length < 8 or len(udp) < length:
                continue
            src = str(ipaddress.IPv4Address(ip[12:16]))
            dst = str(ipaddress.IPv4Address(ip[16:20]))
            yield src, sport, dst, dport, udp[8:length]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Private iPhone PCAPNG file")
    parser.add_argument("--hub", default="192.168.10.138")
    args = parser.parse_args()
    counts = Counter()
    opcodes = Counter()
    peers = Counter()
    for src, sport, dst, dport, payload in packets(args.capture):
        if args.hub not in (src, dst):
            continue
        direction = "hub->phone" if src == args.hub else "phone->hub"
        hubport = sport if src == args.hub else dport
        phoneport = dport if src == args.hub else sport
        peers[(direction, hubport, phoneport)] += 1
        counts[direction] += 1
        if len(payload) >= 12 and payload[0] >> 4 == 14:
            opcodes[(direction, "V3", f"0x{int.from_bytes(payload[2:4], 'big'):04x}")] += 1
        elif len(payload) >= 2 and payload[0] == 0x80:
            opcodes[(direction, "SRT/control-like", f"0x{int.from_bytes(payload[:2], 'big'):04x}")] += 1
        elif len(payload) >= 18 and payload[16] >> 6 == 2:
            opcodes[(direction, "RTP/media candidate", "wrapped")] += 1
        else:
            opcodes[(direction, "other", "unclassified")] += 1
    print("Local EZVIZ P2P packet metadata; no payloads or secrets printed")
    print(f"Total filtered datagrams: {sum(counts.values())}")
    print("UDP ports:")
    for (direction, hubport, peerport), n in peers.most_common(8):
        print(f"  {direction}: hub:{hubport} <-> client:{peerport}   {n}")
    print("Packet signatures:")
    for (direction, family, opcode), n in opcodes.most_common(24):
        print(f"  {direction:12s} {family:20s} {opcode:12s} {n}")
    print("No live streaming or cloud independence is implied by these observations.")

if __name__ == "__main__":
    main()
