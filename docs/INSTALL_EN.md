# EZVIZ BC1 / W2H to Home Assistant (English guide)

> **Update 2026-10-11: Raspberry Pi 5 standalone proxy WORKING.** Version 0.1.2 of the Home Assistant OS add-on was downloaded and installed from a GitHub Actions prebuilt ARM64 container. Initial EZVIZ login, private token storage and the cloud video proxy started successfully; **live picture appeared in go2rtc on the Pi**. No MacBook stream proxy needed. See [the Pi-specific add-on instructions](../ezviz_bc1_w2h/DOCS.md). The previous Mac-based path below is retained as a tested fallback. Pi-specific Lovelace playback, reboot and long-term stability remain to be confirmed.


## Tested scope

This is a **cloud-based** method for **EZVIZ BC1** battery cameras paired with an **EZVIZ W2H** hub. Two tested setups now exist: the original Python proxy on **macOS**, and a Python proxy in a **Home Assistant OS add-on on Raspberry Pi 5**. Both supplied live video to go2rtc; the HACS **AlexxIT/WebRTC** Lovelace card worked with the original proxy. It did not require local camera RTSP/ONVIF. It is **not** an offline solution.

## Architecture

**Recommended:** `BC1 → W2H → EZVIZ cloud/VTM → pyEzvizApi add-on on Raspberry Pi 5 → loopback HTTP MPEG-TS :8558 → go2rtc on HA OS → WebRTC Lovelace card`

**Legacy fallback:** `BC1 → W2H → EZVIZ cloud → pyEzvizApi on Mac → go2rtc on Pi → WebRTC`.

Observed media: H.264 1280×720 plus AAC in a recorded clip. The working go2rtc stream copies *video only* (`#video=copy`) to avoid the observed RTSP header error for AAC.

## Older MacBook-based alternative (tested fallback)

Install Homebrew, then:

```bash
brew install python@3.12 ffmpeg git
mkdir -p ~/ezviz-lab && cd ~/ezviz-lab
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv-video
source .venv-video/bin/activate
python -m pip install -U pip
python -m pip install -U 'git+https://github.com/RenierM26/pyEzvizApi.git'
```

Authenticate with your EZVIZ account and save a private session token using `pyezvizapi --save-token` as documented by the upstream project. Obtain the **BC1 subcamera serial** with `pyezvizapi --token-file ezviz_token.json devices status`. It may include the hub serial as a prefix. Never commit login information or session tokens.

Find your LAN IP with `ipconfig getifaddr en0`. Start:

```bash
pyezvizapi --token-file ezviz_token.json stream proxy \
  --serial 'YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL' \
  --listen-host 'YOUR_MAC_LAN_IP' \
  --listen-port 8558
```

The proxy URL is `http://YOUR_MAC_LAN_IP:8558/YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL.ts`. Leave the Mac terminal running. **No built-in proxy authentication: trusted LAN only.**

## Home Assistant / Raspberry Pi 5

Install the stable go2rtc Home Assistant add-on from `https://github.com/AlexxIT/hassio-addons`. In the **go2rtc Web UI → config**, add:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://YOUR_MAC_LAN_IP:8558/YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL.ts#video=copy
```

Save and test **go2rtc → ezviz_bc1 → stream**. It should show live image. Install [`AlexxIT/WebRTC`](https://github.com/AlexxIT/WebRTC) with HACS, restart HA, and configure the WebRTC integration against the existing go2rtc add-on (`http://localhost:1984` if the address is reachable within HA).

Manual Lovelace card:

```yaml
type: custom:webrtc-camera
url: ezviz_bc1
mode: mse
media: video
ui: true
title: EZVIZ BC1 – Live
```

That is the frontend path confirmed working for this experiment.

## Pi-only setup (verified go2rtc live picture)

Install the **EZVIZ BC1 / W2H Cloud Proxy (TEST) v0.1.2** add-on from `https://github.com/artepe/ezviz-bc1-w2h-home-assistant.`. Provide the BC1 subcamera serial, EZVIZ username/password in add-on Configuration, start it, and check logs for `EZVIZ token saved` and `Proxy process started`. In go2rtc config use:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL.ts#video=copy
```

The **live go2rtc stream was verified working on Pi 5 on 2026-10-11**. Add the [ready-made WebRTC Lovelace card](../examples/lovelace-webrtc.yaml) and verify its playback. The existing go2rtc and proxy add-ons use host networking; do not expose port 8558 publicly.

## Troubleshooting and limitations

See [troubleshooting](TROUBLESHOOTING.md). Some Generic Camera RTSP/HTTP modes failed in this test, but the WebRTC custom card worked. The Mac must stay powered on **only** if using the legacy Mac proxy. The Pi-only add-on is built and its live go2rtc stream has been verified; long-term recovery behavior is not yet validated. Live viewing drains battery and relies on EZVIZ cloud authentication.
