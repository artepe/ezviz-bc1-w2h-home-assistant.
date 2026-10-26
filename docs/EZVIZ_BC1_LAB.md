# EZVIZ BC1 Lab v0.1.0 – separate Mac proxy test integration

Experimental integration for testing EZVIZ BC1 camera feeds in Home Assistant. This is **not** a replacement for the existing `ezviz_bc1_w2h` Home Assistant add-on; both may coexist. Home Assistant's camera entities consume the MPEG-TS stream provided by the already-running Mac VTM proxy.

**Mac proxy requirements:** two proxies already running and reachable over the LAN:
- Camera 1 serial `G23915155-G28068598`, port `8558`
- Camera 2 serial `G23915155-G28068570`, port `8559`
- Proxy host `192.168.10.245` (adjust if the Mac IP changes).

## Install in Home Assistant OS Terminal

```sh
curl -fLsS 'https://raw.githubusercontent.com/artepe/ezviz-bc1-w2h-home-assistant./main/tools/install_ezviz_bc1_lab.sh' -o /tmp/install_ezviz_bc1_lab.sh
sh /tmp/install_ezviz_bc1_lab.sh
ha core check && ha core restart
```

Alternatively manually copy the `custom_components/ezviz_bc1_lab/` directory into `/config/custom_components/ezviz_bc1_lab/`, then restart Home Assistant.

In Home Assistant: **Settings → Devices & services → Add integration → EZVIZ BC1 Lab (Local Test)**. Confirm the host, camera serials, and ports.

Entities:
- `camera.ezviz_bc1_lab_camera_1`
- `camera.ezviz_bc1_lab_camera_2`
- Two binary sensors named `EZVIZ BC1 Lab Proxy N reachable`.

Exact entity IDs may have numeric suffixes if already in use. A proxy reachability sensor only checks a TCP port; it does not prove working video. For an initial picture test, open the new camera entity and select live view. If the picture does not load, inspect the Mac proxy output and run `ffprobe` on the URL.

**Security:** the proxy's HTTP video endpoints have no authentication. Bind them only to a trusted LAN and never forward their ports from the internet. Do not commit EZVIZ login credentials, cookie headers or `token.json`. This setup uses EZVIZ cloud and is not an offline RTSP camera implementation.

**Status:** the integration's Python sources passed syntax checks, and Mac processes were observed listening on ports 8558/8559. Actual video playback inside Home Assistant is not yet confirmed on the user's cameras.
