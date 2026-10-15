# EZVIZ BC1 + W2H → Home Assistant Live Streaming

**Unofficial, tested method to view EZVIZ BC1 battery cameras paired with an EZVIZ W2H base station in Home Assistant, without native camera RTSP or ONVIF.**

**Suomeksi:** Toimivaksi testattu tapa näyttää **EZVIZ BC1 -akkukameran** livekuva **W2H-tukiaseman** kautta Home Assistantin Lovelace-näkymässä ilman kameran omaa RTSP- tai ONVIF-palvelinta.

> [!IMPORTANT]
> **Working Raspberry Pi 5 setup (verified 2026-10-11):** EZVIZ BC1 → W2H → EZVIZ cloud → [pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) in a **Home Assistant OS add-on on Raspberry Pi 5** → HTTP MPEG-TS at `127.0.0.1:8558` → [go2rtc](https://github.com/AlexxIT/go2rtc) → [WebRTC Camera](https://github.com/AlexxIT/WebRTC).
>
> **Verified:** ARM64 image installed successfully; headless EZVIZ authentication succeeded; private session token was saved; the Python proxy started; **live H.264 camera picture appeared in go2rtc from the Pi-hosted source, without MacBook as video proxy**. **The live picture also works in the Home Assistant Lovelace WebRTC card using the Pi-hosted stream**. **Not yet verified:** reboot recovery, long-term reliability, other BC1 units, audio, and automatic recovery after cloud session expiry.
>
> **Requires EZVIZ cloud / internet**. This is not native local RTSP or an offline camera connection.

## Raspberry Pi 5 app - camera manager v0.2.3

**Supervisor startup fix (0.2.3):** restore the container environment through s6's `with-contenv` before Python starts. This carries `SUPERVISOR_TOKEN` and `APP_VERSION` into the app. The repeated settings-unavailable warning now distinguishes a missing token, HTTP denial and connection failure, and reports recovery. The ARM64 workflow checks the actual default container startup as well as module/FFmpeg imports. [Current changelog](ezviz_bc1_w2h/CHANGELOG.md).

**Video recovery (0.2.2):** restore the original video-only defaults after a report that the 0.2.1 audio settings stopped playback. The exact stream failure still needs a fresh go2rtc log. **Test audio** remains available, and experimental audio snippets now use a separate `_audio_test` stream and temporary card. Keep the working video stream while investigating audio. [Recovery and audio diagnostics](docs/AUDIO.md). Updating this app does not edit existing go2rtc or Lovelace configuration.

**New: Open Web UI -> Add new camera.** Add, edit and remove cameras without manually adding YAML keys. Each save goes through Home Assistant Supervisor and is read back before success is shown. Cameras retain their loopback ports, including the original 8558 / 8559 URLs, and the manager provides an on-demand video transport test plus copyable go2rtc and Lovelace configuration.

**Update the existing app; do not uninstall it.** Both original camera fields now have visible defaults, so `camera_serial_2` belongs to the app's saved configuration. The ARM64 build reads its image tag from the app manifest, keeping the downloadable image and update version together. A completed image build is required before the update can be installed.

**[Update and Add new camera guide](docs/UPGRADE_0_2.md)** · The manager is available through **Open Web UI** and the optional **EZVIZ Cameras** sidebar. The built-in EZVIZ device/entity screen is a separate Home Assistant Core integration.

The 0.2.0 changes have offline configuration, persistence, ingress and process lifecycle tests. Live camera playback, multi-camera cloud limits and installation on the user's Pi must be checked on hardware. The end-to-end hardware report below describes the original v0.1.2 setup.

### Earlier two-camera option (v0.1.3, still supported)

**New: optional second camera.** Version 0.1.3 keeps the existing `camera_serial` stream on `127.0.0.1:8558` and adds `camera_serial_2` on `127.0.0.1:8559`. The two proxies have separate process supervision and private token files. The existing one-camera options still work. Offline lifecycle tests pass; second-camera live video and simultaneous cloud streaming still require a hardware test. The end-to-end live-video verification below applies to v0.1.2.

**Tested working in [`ezviz_bc1_w2h/`](ezviz_bc1_w2h/) on Raspberry Pi 5 / Home Assistant OS.** The Pi runs the cloud video proxy directly; no MacBook is needed as a video server.

- **[Finnish installation + options](ezviz_bc1_w2h/DOCS.md)** — detailed Pi setup and safe rollback.
- Source: [Dockerfile](ezviz_bc1_w2h/Dockerfile), [config.yaml](ezviz_bc1_w2h/config.yaml), [runner.py](ezviz_bc1_w2h/runner.py).
- Status: **installed and live-video tested on Raspberry Pi 5 (2026-10-11)**. The MacBook method below remains a tested fallback.
- Safety: binds the proxy to `127.0.0.1:8558` on the HA host and stores a private session in add-on data. Uses EZVIZ cloud (not local/offline RTSP).
- The GitHub repository must be **Public** before Home Assistant OS can install it from the community store without GitHub authentication.

Add this repository in Home Assistant → Apps / Add-on Store → Repositories:

```text
https://github.com/artepe/ezviz-bc1-w2h-home-assistant.
```

**Current video-only go2rtc source** (same BC1 serial as add-on configuration; use the separate experiment in the audio guide for sound):

```yaml
streams:
  ezviz_bc1:
    - "ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy"
```

Use your existing Lovelace WebRTC card with `url: ezviz_bc1`. **Pi-hosted Lovelace playback was confirmed working on 2026-10-11**; the MacBook is no longer required.

### Add a second BC1 with v0.1.3

1. Update the existing **EZVIZ BC1 / W2H Cloud Proxy (TEST)** app to **0.2.0** after the [image build](.github/workflows/build-ezviz-image.yml) succeeds. Keep the first camera in `camera_serial`, or use **Open Web UI -> Add new camera**.
2. In app **Configuration -> YAML**, add `camera_serial_2: YOUR_W2H_SERIAL-YOUR_SECOND_BC1_SERIAL`. Both cameras must be accessible through the same EZVIZ account. Leave the field absent or empty for one camera.
3. Save and restart the app. Its log should report camera 1 on port 8558 and camera 2 on port 8559. Process startup alone does not verify live video.
4. Add the second go2rtc source and test it in the go2rtc player before adding the dashboard card:

```yaml
streams:
  ezviz_bc1:
    - "ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts#video=copy"
  ezviz_bc1_2:
    - "ffmpeg:http://127.0.0.1:8559/YOUR_W2H_SERIAL-YOUR_SECOND_BC1_SERIAL.ts#video=copy"
```

Merge these entries into the existing `streams:` mapping. Use `url: ezviz_bc1_2` in the second WebRTC card. Complete examples: [two go2rtc streams](examples/go2rtc-two-cameras.yaml) and [two Lovelace cards](examples/lovelace-two-cameras.yaml).

Each camera runs through its own HTTP proxy. Keep ports 8558 and 8559 available on the HA host. A failed proxy restarts after `restart_delay` without restarting the other camera. Both cameras still depend on the EZVIZ cloud; live operation of the second camera and simultaneous viewing are not yet verified. Viewing both battery cameras continuously can increase battery use.

### Prebuilt ARM64 image (introduced in v0.1.2)

GitHub Actions **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for Raspberry Pi 5. The add-on can download the Docker image rather than locally building it.

The prebuilt GHCR package was **downloaded and installed successfully** on the test Pi. The original build attempt using Alpine `apk` on the Pi failed due to package-index network errors; GitHub Actions built the working image off-device.

[Build workflow](.github/workflows/build-ezviz-image.yml) · [Pi add-on instructions](ezviz_bc1_w2h/DOCS.md)

## Confirmed hardware and results

| Component | Tested result |
| --- | --- |
| Camera | **EZVIZ BC1** battery camera |
| Base station | **EZVIZ W2H** |
| Automation host | **Home Assistant OS on Raspberry Pi 5** |
| Python proxy | **pyEzvizApi** running directly in a Home Assistant OS add-on on **Raspberry Pi 5**; original MacBook proxy also worked |
| Media relay | **go2rtc** Home Assistant add-on |
| Dashboard | **HACS WebRTC Camera** + Lovelace |
| Video | **H.264 at 1280 × 720** |
| Audio | **AAC** detected in a direct clip; audio disabled in the working go2rtc source |
| Saved clip | Requested 10 seconds; observed **7.69 seconds of playable media** |
| Live stream | **Full Pi-only workflow confirmed (2026-10-11): live picture in go2rtc and Home Assistant Lovelace WebRTC card** |
| Separate media decryption code | **Not needed on the tested clear-media stream path** |

One BC1 stream is end-to-end verified. Recognition of another camera on the same hub does **not** yet prove its video stream works. Results may vary by camera firmware, cloud region, account, battery state, and availability.

## How the working Pi-only setup works

```text
EZVIZ BC1 battery camera
         │
         ▼
EZVIZ W2H hub
         │
         ▼
EZVIZ cloud authentication + VTM video streaming
         │
         ▼
Raspberry Pi 5 / Home Assistant OS
  experimental EZVIZ BC1 / W2H add-on v0.1.2
  pyEzvizApi cloud proxy → HTTP MPEG-TS 127.0.0.1:8558
         │
         ▼
go2rtc add-on (host network)
  FFmpeg H.264 video copy, no audio
         │
         ▼
WebRTC Camera Lovelace card
```

**No native RTSP/ONVIF camera connection needed.** Both the EZVIZ proxy and the go2rtc add-on use host networking; the loopback address stays on the Pi.

### Quick start: Raspberry Pi 5 / Home Assistant OS (verified end-to-end, including Lovelace)

1. In Home Assistant **Apps / Add-on Store -> Repositories** add this repository. Install **EZVIZ BC1 / W2H Cloud Proxy (TEST)**, version **0.2.0** once its image build succeeds. The prebuilt Linux/ARM64 image is provided by GitHub Actions; no Alpine `apk` image build on the Pi is necessary.
2. In the add-on **Configuration**, enter `camera_serial` (the BC1 subcamera serial including hub prefix, not just the W2H hub), EZVIZ `username` and `password`; leave `force_relogin: false`, `restart_delay: 30`. Never share credentials or account tokens.
   For an optional second camera, add its full serial as `camera_serial_2` in the configuration YAML.
3. Start the add-on. Its log should show **`EZVIZ token saved in private add-on storage`** and **`Proxy process started`**.
4. Install/configure the stable [go2rtc add-on](https://github.com/AlexxIT/hassio-addons). In **go2rtc → config**, set (or update) `ezviz_bc1`, keeping other streams unchanged:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

5. Save and restart go2rtc if required. Open **ezviz_bc1 → stream** in go2rtc's Web UI. The **Pi-hosted live image was verified working here on 2026-10-11**.
6. Install the [HACS WebRTC Camera integration](https://github.com/AlexxIT/WebRTC), connect to the existing go2rtc service, and add the following **Manual** Lovelace card. **Live video from the Pi-only proxy was confirmed working in this Lovelace card on 2026-10-11.**

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## 📹 EZVIZ BC1 / W2H
      **Live camera – Raspberry Pi 5**
      EZVIZ cloud → go2rtc → WebRTC
  - type: custom:webrtc-camera
    url: ezviz_bc1
    mode: mse
    media: video
    ui: true
    muted: true
    title: EZVIZ BC1 – LIVE
```

**See the detailed [Pi add-on installation guide](ezviz_bc1_w2h/DOCS.md).** A different stream name such as `ezviz_bc1_pi` is also valid, but its Lovelace `url` must match.

## MacBook-based method (tested fallback)

### 1. Install on the MacBook

Requirements: Homebrew, Python 3.12, FFmpeg, Git, an EZVIZ account with camera access, and a reachable home network.

```bash
brew install python@3.12 ffmpeg git
mkdir -p ~/ezviz-lab && cd ~/ezviz-lab
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv-video
source .venv-video/bin/activate
python -m pip install -U pip
python -m pip install -U 'git+https://github.com/RenierM26/pyEzvizApi.git'
```

### 2. Sign in and save a private session token

The following prompts are for **macOS zsh**. Do **not** upload or commit your EZVIZ credentials or token.

```bash
cd ~/ezviz-lab
source .venv-video/bin/activate
umask 077
read -r 'EZ_USER?EZVIZ login email: '
read -rs 'EZ_PASS?EZVIZ password: '; echo
pyezvizapi -u "$EZ_USER" -p "$EZ_PASS" --save-token devices status
unset EZ_USER EZ_PASS
```

Identify the **BC1 subcamera serial** in the device list, often in the form `W2H_SERIAL-BC1_SERIAL`. Do not use the hub serial alone.

### 3. Start the live-video proxy on MacBook

```bash
cd ~/ezviz-lab
source .venv-video/bin/activate
ipconfig getifaddr en0
pyezvizapi --token-file ezviz_token.json stream proxy \
  --serial 'YOUR_W2H_SERIAL-YOUR_BC1_SERIAL' \
  --listen-host 'YOUR_MAC_LAN_IP' \
  --listen-port 8558
```

Keep the Terminal running. The URL becomes:

```text
http://YOUR_MAC_LAN_IP:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts
```

**Security:** this proxy has no built-in password. Expose it only within a trusted LAN; do **not** forward port 8558 to the internet.

### 4. Test connectivity from Home Assistant

From the Home Assistant Terminal (not the Mac Terminal):

```bash
curl --connect-timeout 5 --max-time 15 -sS -o /tmp/bc1-test.ts \
  -w 'HTTP=%{http_code} received=%{size_download}\n' \
  http://YOUR_MAC_LAN_IP:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts
```

An HTTP 200 response with downloaded bytes demonstrates connectivity. The expected `curl (28)` after 15 seconds simply ends a continuous stream. Check playback separately.

### 5. Install/configure go2rtc on Home Assistant OS

Install the stable **go2rtc** add-on from [AlexxIT/hassio-addons](https://github.com/AlexxIT/hassio-addons). In **go2rtc Web UI → config**, add (or merge with your existing `streams:`):

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://YOUR_MAC_LAN_IP:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

Save the configuration. In the go2rtc web player, open **ezviz_bc1 → stream**. This was successful on Raspberry Pi 5.

**Why no audio?** The earlier `#video=copy#audio=copy` variant failed with `AAC with no global headers is currently not supported`. The verified working source uses **video only**.

### 6. Add the Home Assistant Lovelace live camera

Install [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC) using HACS, restart Home Assistant, and add the **WebRTC** integration. Connect it to the existing go2rtc add-on (typically `http://localhost:1984` if reachable from Home Assistant).

Add this **Manual** Lovelace card:

```yaml
type: custom:webrtc-camera
url: ezviz_bc1
mode: mse
media: video
ui: true
title: EZVIZ BC1 – Live
```

**Verified:** the BC1 live picture appeared in both the go2rtc player and the Home Assistant WebRTC card.

## Why not Generic Camera?

Home Assistant Generic Camera reported `Stream network error` or `Timeout while loading URL` for the attempted HTTP MPEG-TS and RTSP paths in the original experiment. The already-functioning go2rtc source displayed correctly through the HACS WebRTC card. This is an observation from one setup, **not** a general claim that Generic Camera is unsupported.

## Security and battery considerations

- Keep EZVIZ passwords, verification codes, serial numbers and tokens out of Git repositories and screenshots.
- Error traces may embed **session tokens in URLs**; redact or rotate exposed session credentials.
- Restrict pyEzvizApi proxy port **8558** and go2rtc API/RTSP ports **1984/8554** to a trusted LAN; never expose an unauthenticated stream publicly.
- **BC1 runs on battery**. Continuous streaming may keep it awake and drain its battery; prefer on-demand viewing.
- This approach **requires EZVIZ cloud access**, not offline local decoding.

## Limitations / development roadmap

- [x] Cloud BC1 live-video capture via pyEzvizApi
- [x] H.264 MPEG-TS playback on macOS
- [x] go2rtc video stream on Home Assistant OS / Raspberry Pi 5
- [x] HACS WebRTC Lovelace live-view card
- [x] Pi-hosted cloud proxy + go2rtc **live picture verified 2026-10-11**, MacBook not needed as stream proxy
- [x] Prebuilt GitHub Actions ARM64 image, add-on v0.1.2 installed and initial EZVIZ login verified on Raspberry Pi 5
- [x] Pi-only WebRTC Lovelace live video confirmed working (2026-10-11)
- [ ] Verify persistence across a Pi reboot, cloud session renewal, and multi-hour stability
- [ ] Separate live-stream verification for a second BC1
- [ ] Audio remux/transcoding and stability/battery testing
- [ ] On-demand wake-up integration

## End-to-end verification

- [End-to-end verification report](docs/VERIFIED_PI5_2026-10-11.md) — exact tested platform, components, results, issues, and remaining work. No account credentials or camera-specific IDs are published.

## Guides and examples

- [Suomenkielinen asennusopas](docs/ASENNUS_FI.md)
- [English setup guide](docs/INSTALL_EN.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [go2rtc source example](examples/go2rtc.yaml)
- [Lovelace camera card](examples/lovelace-webrtc.yaml)
- [Proxy helper script](scripts/start_proxy.sh)

## Credits

This repository documents an integration procedure and includes original helper scripts. It builds on existing open-source work:

- [RenierM26/pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) — EZVIZ cloud API and VTM-to-MPEG-TS streaming
- [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc) — media relay
- [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC) — Home Assistant Lovelace camera integration

This repository's MIT license covers its original content only; upstream software retains its respective licenses.

**Status (2026-10-11): complete Pi-only BC1 + W2H → EZVIZ cloud → pyEzvizApi → go2rtc → Home Assistant WebRTC Lovelace live video VERIFIED working. Experimental: long-term operation, reboot recovery and other camera models not yet tested.**
