# EZVIZ BC1 + W2H → Home Assistant Live Streaming

**Unofficial, tested method to view EZVIZ BC1 battery cameras paired with an EZVIZ W2H base station in Home Assistant, without native camera RTSP or ONVIF.**

**Suomeksi:** Toimivaksi testattu tapa näyttää **EZVIZ BC1 -akkukameran** livekuva **W2H-tukiaseman** kautta Home Assistantin Lovelace-näkymässä ilman kameran omaa RTSP- tai ONVIF-palvelinta.

> [!IMPORTANT]
> **Verified setup:** EZVIZ BC1 → W2H → EZVIZ cloud → [pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) on **MacBook** → HTTP MPEG-TS → [go2rtc](https://github.com/AlexxIT/go2rtc) on **Home Assistant OS / Raspberry Pi 5** → [WebRTC Camera](https://github.com/AlexxIT/WebRTC) Lovelace card.
>
> This is **not an offline/local-only video solution**. A fully Raspberry Pi–hosted Python proxy / standalone add-on is **not yet implemented or tested**.

## Raspberry Pi 5 add-on — experimental test v0.1.2

**New test version is available in [`ezviz_bc1_w2h/`](ezviz_bc1_w2h/).** It aims to run the cloud video proxy **directly on Raspberry Pi 5 / Home Assistant OS**, so that the MacBook is no longer required.

- **[Finnish installation + options](ezviz_bc1_w2h/DOCS.md)** — detailed Pi setup and safe rollback.
- Source: [Dockerfile](ezviz_bc1_w2h/Dockerfile), [config.yaml](ezviz_bc1_w2h/config.yaml), [runner.py](ezviz_bc1_w2h/runner.py).
- Status: **prebuilt on GitHub Actions; NOT yet installed/tested on Raspberry Pi 5**. The MacBook method below remains the verified working version.
- Safety: binds the proxy to `127.0.0.1:8558` on the HA host and stores a private session in add-on data. Uses EZVIZ cloud (not local/offline RTSP).
- The GitHub repository must be **Public** before Home Assistant OS can install it from the community store without GitHub authentication.

Add this repository in Home Assistant → Apps / Add-on Store → Repositories:

```text
https://github.com/artepe/ezviz-bc1-w2h-home-assistant.
```

**go2rtc source for Pi-only testing** (same BC1 serial as add-on configuration):

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

Keep the existing Lovelace WebRTC card. Do not remove your working Mac configuration until the Pi test works.

### New in v0.1.2: prebuilt ARM64 image

GitHub Actions **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for Raspberry Pi 5. The add-on can download the Docker image rather than locally building it.

**The GHCR package must be set Public** (GitHub profile → Packages → `ezviz-bc1-w2h` → Package settings → Change visibility). The image's runtime on the Pi and EZVIZ authentication are **not yet verified**.

[Build workflow](.github/workflows/build-ezviz-image.yml) · [Pi add-on instructions](ezviz_bc1_w2h/DOCS.md)

## Confirmed hardware and results

| Component | Tested result |
| --- | --- |
| Camera | **EZVIZ BC1** battery camera |
| Base station | **EZVIZ W2H** |
| Automation host | **Home Assistant OS on Raspberry Pi 5** |
| Python proxy | **pyEzvizApi** cloud VTM stream proxy on macOS |
| Media relay | **go2rtc** Home Assistant add-on |
| Dashboard | **HACS WebRTC Camera** + Lovelace |
| Video | **H.264 at 1280 × 720** |
| Audio | **AAC** detected in a direct clip; audio disabled in the working go2rtc source |
| Saved clip | Requested 10 seconds; observed **7.69 seconds of playable media** |
| Live stream | **Working in go2rtc web player and Home Assistant WebRTC card** |
| Separate media decryption code | **Not needed on the tested clear-media stream path** |

One BC1 stream is end-to-end verified. Recognition of another camera on the same hub does **not** yet prove its video stream works. Results may vary by camera firmware, cloud region, account, battery state, and availability.

## How this works

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
MacBook / Python 3.12 / pyEzvizApi
  `pyezvizapi ... stream proxy`
  HTTP MPEG-TS :8558 (trusted LAN only)
         │
         ▼
Raspberry Pi 5 / Home Assistant OS / go2rtc + FFmpeg
  H.264 video copied, audio omitted
         │
         ▼
Home Assistant WebRTC Lovelace camera card
```

The BC1 does not need a native RTSP endpoint for this setup. The Python proxy obtains the live stream from EZVIZ cloud, and go2rtc presents it to the Home Assistant dashboard.

## Quick start — verified MacBook + Home Assistant setup

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
- [ ] Independent Python proxy running on Raspberry Pi 5 without the Mac
- [x] First experimental supervised Home Assistant add-on source published (**Pi build not tested**)
- [ ] Separate live-stream verification for a second BC1
- [ ] Audio remux/transcoding and stability/battery testing
- [ ] On-demand wake-up integration

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

**Status: working community proof of concept on EZVIZ BC1 + W2H with MacBook proxy.**
