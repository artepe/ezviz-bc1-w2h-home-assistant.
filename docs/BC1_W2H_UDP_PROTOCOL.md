# BC1 + W2H: local UDP P2P packet fingerprint (experimental)

This investigation is based on an authorized iPhone capture of the owner's EZVIZ BC1 cameras and W2H hub. **The capture and any credentials or media are intentionally NOT stored in this public repository.**

## Observed transport

- Phone `192.168.10.197:10148` ↔ W2H candidate `192.168.10.138:35938` over UDP (dynamic ports).
- The capture contains 3,104 local UDP datagrams and two decodable H.264/AAC MPEG-PS sessions. These are recorded media; an independent local live client has **not** been demonstrated.
- V3 control-plane packets begin with `0xE2`, have a 12-byte header and big-endian opcode at bytes 2..3. In this particular PCAP:

| Sender | Opcode | Count | Tentative meaning |
| --- | --- | ---: | --- |
| iPhone | `0x0C00` | 6 | hole-punch request |
| W2H | `0x0C00` | 1 | hole-punch request |
| iPhone | `0x0C01` | 28 | hole-punch response |
| W2H | `0x0C01` | 21 | hole-punch response |

The `0x80xx` control-like datagrams include `0x8006` SRT ACK2-style messages; payload-bearing UDP packets follow a proprietary transport wrapper and contain RTP type 96 with MPEG-PS media. Session-specific state, dynamically negotiated endpoints, acknowledgment and replay protections must be respected.

## Important external implementation

There is an **independent, openly published** reverse-engineered Go implementation of the same *Hikvision/EZVIZ P2P protocol family*:

- https://github.com/pedropaulovc/go2rtc/pull/2
- https://github.com/pedropaulovc/go2rtc/blob/feat/ezviz-p2p-transport/pkg/ezviz/PROTOCOL.md

It documents:
- V3 `0xE2` frames with `0x0C00` / `0x0C01` connection setup;
- proprietary SRT-style UDP transport and ACK handling;
- `0x0C02` PLAY_REQUEST, device/key discovery and cloud P2P bootstrap;
- video decoding proven on a **Hik-Connect NVR with HEVC**, not on BC1/W2H.

**Do not assume this fork works on BC1/W2H.** It currently advertises a known H.264 codec gap (https://github.com/pedropaulovc/go2rtc/issues/3). The tested user's BC1 stream is H.264, mostly carried as MPEG-PS, rather than the fork's NVR HEVC pathway. Also the fork uses cloud APIs to bootstrap key and endpoint information; working local iPhone transport does not establish that this fork can operate without EZVIZ cloud access.

## Existing add-on limitation

The experimental `ezviz_bc1_w2h` hybrid `8658` path uses `pyezvizapi stream local-sdk-dump` over *TCP* 9010/9020 with cloud CAS authorization. This is **not the same as the iPhone's successfully captured UDP P2P flow**. Previously observed CAS errors `1052170`, `1052175` and EZVIZ response `20002` do not get fixed merely by using hybrid auto-fallback. A go2rtc HTTP 500 with zero media bytes proves only that the input could not be opened, not which handshake failed.

## Next implementation milestones

1. **Offline protocol matching**: compare V3 headers, 0x0C00/0x0C01 sequence, 0x8006 acknowledgements, and media framing against the published Go code. Use packet metadata; never commit the original PCAP.
2. **Authenticated, on-demand UDP local client**: implement the valid device/session setup, ACKs, start/stop and H.264/MPEG-PS extraction; do not replay old captured packets or hardcode saved session secrets.
3. **Bench test against one BC1 on LAN**: verify fresh live images with the phone's EZVIZ app *not* viewing simultaneously, and distinguish cloud-bootstrap dependency.
4. **Proxy + go2rtc**: only after verification produce a long-lived MPEG-TS or RTSP endpoint, with independent cloud fallback and safe error statuses.
5. **Real offline test**: disconnect W2H from internet *only after* the authenticated LAN client has been proven to work; avoid unexpected impacts on camera recording and notifications.

No change to deployed camera streams or secret storage is part of this protocol-analysis step.

## Read-only analyzer

`tools/ezviz_udp_timeline.py` supports PCAPNG and only reports classification and timing. It does not replay traffic, interact with the camera, or publish packet bodies.
