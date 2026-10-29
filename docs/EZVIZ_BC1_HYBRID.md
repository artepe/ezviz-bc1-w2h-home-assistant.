# EZVIZ BC1 / W2H – LAN + Cloud Hybrid v0.2.13 (experimental)

This optional endpoint is **not a verified standalone LAN client for BC1/W2H**.
It adds reliable source selection around existing experimental protocols without
replacing the previous cloud-only camera URLs.

## How it works

| Source | How it is opened | Requirement |
| --- | --- | --- |
| Local | `pyezvizapi stream local-sdk-dump` to W2H TCP 9010/9020, remux MPEG-TS | Hub reachable on LAN; valid EZVIZ token and CAS local permission |
| Cloud | existing per-camera pyEzvizApi HTTP VTM proxy on `127.0.0.1:8558+` | EZVIZ cloud media stream available |
| Auto | Try local, then cloud on failure *before* any media is emitted | At least one source works |

The local SDK control path can require a cloud CAS authorization at the
beginning of a new session. It therefore does **not yet provide fully offline
video**. The iPhone PCAP shows that a direct local UDP media path exists for
BC1/W2H, but that UDP session's handshake and acknowledgements are not
implemented by this SDK adapter and may be different. CAS errors 1052170,
1052175 and cloud error 20002 have been observed on this user's cameras.
Those errors are **not fixed by adding an automatic fallback**. If both
sources fail, this endpoint gives 503 rather than pretending video works.

## Installation, keeping existing cameras intact

1. Wait until the GitHub Actions image build for **0.2.13** succeeds.
   In Home Assistant update the existing `EZVIZ BC1 / W2H Cloud Proxy`
   add-on **without uninstalling it**.
2. Under add-on Configuration -> YAML set these **additional** keys;
   keep your original cameras and account settings unchanged:

   ```yaml
   hybrid_mode: auto
   lan_hub_ip: 192.168.10.138
   lan_cas_serial: G23915155
   ```

   `hybrid_mode: cloud` forces the existing cloud source; `local` tests
   LAN only; `auto` tries local first. Set `lan_hub_ip: ""` to
   disable the LAN attempt without disabling the original proxy.
3. Restart the add-on. The new hybrid endpoint listens on
   **127.0.0.1:8658** in addition to the original 8558 and 8559 ports.
4. From the **Home Assistant OS Terminal** (not from your MacBook):

   ```bash
   curl -sS http://127.0.0.1:8658/status
   ```

   If your Terminal add-on is isolated in a network namespace, loopback
   may refer to the Terminal container instead; use the HA host IP or
   test through go2rtc instead.

5. To test video ON DEMAND use a *new* go2rtc alias, preserving your
   original `ezviz_bc1` and `ezviz_bc1_2`:

   ```yaml
   streams:
     ezviz_bc1_hybrid:
       - "ffmpeg:http://127.0.0.1:8658/G23915155-G28068598.ts#video=copy"
     ezviz_bc1_2_hybrid:
       - "ffmpeg:http://127.0.0.1:8658/G23915155-G28068570.ts#video=copy"
   ```

   Add these entries to the existing `streams:` mapping; do not create
   another top-level `streams:` key. Open the new streams in go2rtc UI.

6. In Lovelace, add a temporary experimental card:

   ```yaml
   type: custom:webrtc-camera
   url: ezviz_bc1_hybrid
   mode: mse
   media: video
   ui: true
   muted: true
   title: EZVIZ BC1 Hybrid TEST
   ```

If a stream starts, its HTTP response has `X-EZVIZ-Source: local` or
`X-EZVIZ-Source: cloud`. The `status` endpoint **does not verify
live playback**. In auto mode, a LAN failure waits five minutes before the
next LAN attempt to avoid hammering cloud CAS / waking battery cameras.
Each HTTP viewing session may start a fresh media connection: use go2rtc
to fan out multiple viewers. Fallback is attempted **only at connection
startup**; if a source fails mid-stream, go2rtc must reconnect.

## Important limitations and cloud diagnosis

- The current W2H LAN-first path is experimental: pyEzvizApi local-SDK
  support is verified for some EZVIZ devices, **not for BC1/W2H**.
- Local video observed in the iPhone PCAP was on dynamic UDP ports,
  distinct from the tested 9010/9020 TCP local SDK. A successful
  iPhone live view does not prove the SDK command works for W2H.
- If W2H does not connect to EZVIZ cloud, no HA software can make that
  offline W2H suddenly appear online in the official EZVIZ cloud service.
  Verify the hub's DNS, outbound network access, time and EZVIZ account.
  Do not forward ports 8558/8559/8658 to the internet.
- Use Nabu Casa Home Assistant Cloud or a VPN for remote access to HA
  once its LAN stream actually works. This does not require the EZVIZ
  cloud media relay, though LAN SDK authorization may still use CAS.
- Never publish `token.json`, login credentials, PCAP captures, keys or
  URLs containing session IDs.

## Rollback

Use the existing `ezviz_bc1` and `ezviz_bc1_2` go2rtc stream names
on ports 8558/8559. Optionally set `hybrid_mode: cloud` or leave the
new hybrid aliases unused. Original cloud proxies and camera entities
are never overwritten by this feature.
