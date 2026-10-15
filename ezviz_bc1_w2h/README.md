# EZVIZ BC1 / W2H Cloud Proxy (TEST)

**Experimental Raspberry Pi 5 / Home Assistant OS app - version 0.2.1.**

Use **Open Web UI -> Add new camera** to save cameras through Home Assistant Supervisor with readback verification. Existing camera serials and ports 8558 / 8559 remain supported. Each camera has a private token file and supervised proxy. [Current update guide](../docs/UPGRADE_0_2.md).

**Audio fix in 0.2.1:** earlier generated settings disabled audio. New snippets use `#video=copy#audio=aac` and `media: video,audio`. Replace the existing go2rtc and card settings manually, restart go2rtc, and unmute the player. **Test audio** checks whether the source proxy supplies an audio track. Actual BC1 microphone sound still needs hardware verification. [Audio setup and diagnostics](../docs/AUDIO.md).

Run [pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) cloud live streaming on Raspberry Pi 5, replacing the currently verified MacBook relay. Requires EZVIZ account, W2H hub, BC1 subcamera, internet and go2rtc.

**Single-camera proof of concept, verified with v0.1.2 on 2026-10-11 on Raspberry Pi 5:** ARM64 image installed, EZVIZ login succeeded, private session was saved, proxy started and BC1 **live video appeared in go2rtc and the Lovelace WebRTC card** using the loopback stream. Multi-day reliability still needs testing.

[Complete Finnish setup / English technical notes](DOCS.md)

This add-on serves HTTP MPEG-TS at **127.0.0.1:8558** on the Home Assistant OS host network. Configure the existing go2rtc stream:

```yaml
streams:
  ezviz_bc1:
    - "ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy#audio=aac"
```

The HACS WebRTC Camera card uses `url: ezviz_bc1`; use [the complete YAML](../examples/lovelace-webrtc.yaml). No external internet port forwarding. No native RTSP from the W2H hub.

For a second camera, use **Add new camera**. The legacy `camera_serial_2` option is also supported. Add a go2rtc stream named `ezviz_bc1_2` pointing to port 8559 and a WebRTC card with `url: ezviz_bc1_2`. See the [two-camera go2rtc example](../examples/go2rtc-two-cameras.yaml) and [two-camera Lovelace example](../examples/lovelace-two-cameras.yaml).

## Prebuilt container image (v0.1.2)

The GitHub Actions job **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for linux/arm64. The add-on's `config.yaml` points to this image, avoiding the Pi's Alpine `apk` networking failure.

**Important:** GitHub Container Registry packages may start **Private**, even when this code repository is Public. To allow Home Assistant OS to pull the image, open **GitHub → your profile → Packages → ezviz-bc1-w2h → Package settings → Change visibility → Public**. This publishes the compiled image, **not** your EZVIZ account information.

Run `ha store reload` and check `version_latest: 0.2.1` before updating. Wait for the v0.2.1 image build to succeed first. If the image pull fails with access denied, check the GHCR package visibility. If it fails for DNS/connectivity, inspect the Supervisor logs.
