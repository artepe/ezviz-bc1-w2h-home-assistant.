# EZVIZ BC1 / W2H to Home Assistant (English guide)

## Tested scope

This is a **cloud-based** method for **EZVIZ BC1** battery cameras paired with an **EZVIZ W2H** hub. The experiment succeeded with a Python proxy on **macOS**, the go2rtc Home Assistant add-on on **Raspberry Pi 5**, and the HACS **AlexxIT/WebRTC** Lovelace card. It did not require local camera RTSP/ONVIF. It is **not** an offline solution.

## Architecture

`BC1 → W2H → EZVIZ cloud/VTM → pyEzvizApi on Mac → HTTP MPEG-TS → go2rtc on HA OS → WebRTC Lovelace card`

Observed media: H.264 1280×720 plus AAC in a recorded clip. The working go2rtc stream copies *video only* (`#video=copy`) to avoid the observed RTSP header error for AAC.

## MacBook

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

## Troubleshooting and limitations

See [troubleshooting](TROUBLESHOOTING.md). Some Generic Camera RTSP/HTTP modes failed in this test, but the WebRTC custom card worked. The Mac must stay powered on until the proxy is moved to Pi; the planned Pi-only add-on is **not yet built**. Live viewing drains battery and relies on EZVIZ cloud authentication.
