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

## 2026-10-29: refined PCAP diagnosis after HTTP 5XX

The owner tested `ezviz_bc1_2_hybrid` in go2rtc. go2rtc displayed a 5XX opening
`http://127.0.0.1:8658/G23915155-G28068570.ts`, showing that go2rtc
reached the hybrid endpoint but neither source supplied MPEG-TS data. This
does **not** establish a go2rtc configuration problem.

The original private PCAP was re-read offline (the file is NOT committed).
For the 3,104 datagrams between iPhone and W2H, the V3 opcodes **actually
present on this particular local link** are:

| Direction | V3 opcode | Count |
| --- | --- | ---: |
| iPhone → W2H | `0x0C00` | 6 |
| W2H → iPhone | `0x0C00` | 1 |
| iPhone → W2H | `0x0C01` | 28 |
| W2H → iPhone | `0x0C01` | 21 |

Crucially, the local link **does not contain a cleartext `0x0C02`
PLAY_REQUEST**. According to the external reference, a PLAY_REQUEST can be
carried in an encrypted P2P-server-relayed `0x0B04` message, or otherwise
occur outside this filtered UDP peer link. The absence of this message
means the capture on its own is **not enough to build an authenticated
standalone client**. Do not replay old captured encrypted/session packets.

The current hybrid plugin uses a distinct CAS-dependent TCP local SDK.
Its HTTP 503 is therefore expected when both local CAS permission and
cloud media delivery fail. The next implementation must solve P2P
bootstrap/session authentication and the SRT-style media transport; a
go2rtc reinstall or a new stream alias cannot fix it.

## Rechecked complete PCAP: the iPhone does use cloud P2P setup

The previous local-only analysis missed the control packets to **public
P2P servers**. Re-examining all UDP conversations in the original privately
stored PCAP shows the following **observed relative times**:

| Time | Destination / transport | Visible V3 opcode | Interpretation |
| ---: | --- | --- | --- |
| +15.494s | public server UDP 6404 | `0x0B02` | P2P_SETUP from iPhone |
| +15.567s | server response UDP 6404 | `0x0B03` | P2P server reply |
| +15.572s | W2H LAN UDP 35938 | `0x0C00` | Direct hole-punch setup |
| +15.604s | W2H reply UDP 35938 | `0x0C01` | Direct hole-punch response |
| +23.906s | public P2P servers UDP 6406 | `0x0B04` | TRANSFOR_DATA control relay, payload encrypted |
| +23.979s | server response UDP 6406 | `0x0B05` | Response to relayed control |
| +26.523s | W2H LAN UDP 35938 | media | First decodable H.264 MPEG-PS media |
| +34.627s | public P2P servers UDP 6000 | `0x0B04` | Additional relayed control for second view |
| +37.330s | W2H LAN UDP 35938 | media | Second decodable H.264 MPEG-PS media |

**Conclusion:** Video data was local, but the iPhone did contact external
P2P servers for connection setup and control. The device appearing "cloud
offline" in the app does NOT prove its P2P control service is unavailable.
The original capture does NOT demonstrate full internet-independent streaming.

The published fork already implements this same P2P control family, but
requires online account login/KMS key retrieval and is validated primarily
for NVR HEVC + G.711. The BC1 recording was H.264 + AAC in MPEG-PS, which
requires explicit model-specific framing/codec support. Its existing
`session.feed()` hardcodes H.265 for video. **A login or UDP setup success
does not mean the fork already decodes BC1 media**.

### Isolated next test (macOS)

A pinned, on-demand proof-of-concept launcher is in
[`tools/mac_ezviz_p2p_trial.sh`](../tools/mac_ezviz_p2p_trial.sh).
It clones a pinned third-party fork, compiles it locally, asks for EZVIZ
credentials privately on the Mac, and triggers **one** camera source.
It does not alter the Home Assistant installation. It checks where the
experiment fails (login, device data, P2P session, or codec). Passwords and
temporary process logs are deleted on exit. The test config binds the
private API to loopback only and is NOT intended as a production service.
Review the third-party source before using account credentials.

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
