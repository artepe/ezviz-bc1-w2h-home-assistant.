# EZVIZ BC1 / W2H Cloud Proxy (TEST)

**Experimental Raspberry Pi 5 / Home Assistant OS add-on — version 0.1.1.**

Run [pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) cloud live streaming on Raspberry Pi 5, replacing the currently verified MacBook relay. Requires EZVIZ account, W2H hub, BC1 subcamera, internet and go2rtc.

**Not tested on actual Raspberry Pi yet; use at your own risk.**

[Complete Finnish setup / English technical notes](DOCS.md)

This add-on serves HTTP MPEG-TS at **127.0.0.1:8558** on the Home Assistant OS host network. Configure the existing go2rtc stream:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

The HACS WebRTC Camera card remains unchanged. No external internet port forwarding. No native RTSP from the W2H hub.
