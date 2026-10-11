# Verified: EZVIZ BC1 / W2H live video in Home Assistant on Raspberry Pi 5

**Date of real-hardware verification:** 2026-10-11  
**Result:** **PASS — live video visible in both go2rtc and the Home Assistant Lovelace WebRTC Camera card, with the cloud-video proxy hosted entirely on Raspberry Pi 5.**

This is an *unofficial, cloud-dependent, experimental proof of concept*, not a vendor-supported local RTSP integration. Long-term uptime, network outages and reboot recovery remain to be tested.

## Hardware and software used

| Component | Confirmed |
| --- | --- |
| Camera | **EZVIZ BC1 battery camera** |
| Hub | **EZVIZ W2H** base station |
| Home Assistant host | **Raspberry Pi 5**, Home Assistant OS, ARM64 (`aarch64`) |
| Video bridge | Repository add-on `ezviz_bc1_w2h`, **v0.1.2** |
| Cloud client | [RenierM26/pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) |
| Prebuilt image | `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2`, built in GitHub Actions |
| Stream proxy | HTTP MPEG-TS, bound to loopback `127.0.0.1:8558` |
| Media gateway | [go2rtc](https://github.com/AlexxIT/go2rtc) add-on, using host networking |
| Dashboard | HACS [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC), Lovelace custom card |
| Video | H.264 passthrough with `#video=copy`, no audio in the tested go2rtc source |
| Internet required | **Yes**: EZVIZ cloud/VTM stream |
| MacBook required for video | **No**: both the cloud proxy and go2rtc run on the Pi |

The first tested camera was verified end to end. This report does not claim that every firmware or EZVIZ region works.

## Verified media path

```text
EZVIZ BC1
   |
EZVIZ W2H
   |
EZVIZ cloud / VTM (internet connection required)
   |
Home Assistant OS add-on, Raspberry Pi 5
  pyEzvizApi -> HTTP MPEG-TS at 127.0.0.1:8558
   |
go2rtc on the same Pi (FFmpeg H.264 video copy)
   |
HACS WebRTC Camera -> Home Assistant Lovelace dashboard
```

### Tested go2rtc configuration

**Use your own BC1 subcamera device ID** (typically hub serial and camera serial separated by a hyphen). Never post the real device ID or session tokens in an issue.

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

The loopback URL works here because **both add-ons use `host_network: true`**. Do not substitute the Home Assistant web UI port `8123` or the old MacBook LAN IP. When integrating into an existing go2rtc configuration, merge under the *existing* `streams:` section rather than adding a duplicate key.

### Tested Lovelace example

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## 📹 EZVIZ BC1 / W2H
      **Livekamera – Raspberry Pi 5**
      Videovirta: EZVIZ Cloud → go2rtc → WebRTC
  - type: custom:webrtc-camera
    url: ezviz_bc1
    mode: mse
    media: video
    ui: true
    muted: true
    title: EZVIZ BC1 – LIVE
```

If your source name is `ezviz_bc1_pi` rather than `ezviz_bc1`, update the card URL accordingly.

## Validation checklist (2026-10-11)

- [x] Public GitHub add-on repository registered in Home Assistant app store.
- [x] Raspberry Pi 5 can install the prebuilt ARM64 image `v0.1.2` (local Docker builds failed previously).
- [x] Home Assistant starts the add-on.
- [x] Headless first-time EZVIZ account login succeeds.
- [x] EZVIZ session saved to private add-on `/data`.
- [x] Python EZVIZ stream proxy starts.
- [x] go2rtc reads the Pi-hosted MPEG-TS source and displays a live picture.
- [x] HACS WebRTC Camera Lovelace card displays the same Pi-hosted live camera.
- [x] MacBook video proxy is not required for these steps.
- [ ] Confirm restart-on-boot after complete Pi reboot.
- [ ] Measure multi-day cloud session stability and token expiry recovery.
- [ ] Verify second BC1, additional regions/firmware versions.
- [ ] Test audio/transcoding, motion/wake behavior and battery impact.

## Problems solved during bring-up

**Alpine APKINDEX unavailable during local Pi Docker builds:** Home Assistant's Docker build could not retrieve Alpine v3.22 package indices, even when a Terminal HTTP request worked. DNS changes and multiple APK mirrors did not solve it. The successful workaround was to **build and smoke-test an ARM64 Docker image in GitHub Actions**, publish it to GitHub Container Registry, and configure the HA add-on with `image: "ghcr.io/artepe/ezviz-bc1-w2h"`.

**go2rtc still tried to connect to the MacBook:** Even after the Pi proxy was started, an outdated go2rtc source used the MacBook's IP and returned `Connection refused`. Replacing the old source with `http://127.0.0.1:8558/...ts`, saving, restarting go2rtc where necessary, and selecting the correct stream resolved the issue.

**Audio header error:** A previous source ending in `#video=copy#audio=copy` reported `AAC with no global headers is currently not supported`. The working setup uses `#video=copy` only.

**Cloud dependence:** The stream is provided by EZVIZ cloud services. This project is **not** a local network decryption technique, and **not** an EZVIZ service replacement.

## Security

The add-on configuration requires the user's EZVIZ credentials for initial login and stores an account session in its private data directory. Home Assistant backups may still contain those secrets. The proxy has no separate HTTP authentication but binds only to `127.0.0.1`; do not open its port on the internet. Do not publish camera serials, verification codes, session JSON, or detailed upstream error traces containing authentication URLs.

## Credits

This proof of concept integrates existing software and acknowledges the upstream projects:

- [pyEzvizApi by RenierM26](https://github.com/RenierM26/pyEzvizApi)
- [go2rtc by AlexxIT](https://github.com/AlexxIT/go2rtc)
- [Home Assistant WebRTC Camera by AlexxIT](https://github.com/AlexxIT/WebRTC)

**Status:** Complete Raspberry Pi 5 **video streaming + Lovelace test passed**. Long-term reliability not yet established.
