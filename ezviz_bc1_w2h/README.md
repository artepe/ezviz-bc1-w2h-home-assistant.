# EZVIZ BC1 / W2H Cloud Proxy (TEST)

**Experimental Raspberry Pi 5 / Home Assistant OS add-on — version 0.1.2.**

Run [pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) cloud live streaming on Raspberry Pi 5, replacing the currently verified MacBook relay. Requires EZVIZ account, W2H hub, BC1 subcamera, internet and go2rtc.

**GitHub Actions built and smoke-tested the ARM64 image; it is not yet installed on Raspberry Pi.**

[Complete Finnish setup / English technical notes](DOCS.md)

This add-on serves HTTP MPEG-TS at **127.0.0.1:8558** on the Home Assistant OS host network. Configure the existing go2rtc stream:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

The HACS WebRTC Camera card remains unchanged. No external internet port forwarding. No native RTSP from the W2H hub.

## Prebuilt container image (v0.1.2)

The GitHub Actions job **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for linux/arm64. The add-on's `config.yaml` points to this image, avoiding the Pi's Alpine `apk` networking failure.

**Important:** GitHub Container Registry packages may start **Private**, even when this code repository is Public. To allow Home Assistant OS to pull the image, open **GitHub → your profile → Packages → ezviz-bc1-w2h → Package settings → Change visibility → Public**. This publishes the compiled image, **not** your EZVIZ account information.

Run `ha store reload` and check `version_latest: 0.1.2` before installing. If the image pull fails with access denied, check the GHCR package visibility. If it fails for DNS/connectivity, inspect the Supervisor logs.
