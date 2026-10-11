# Changelog

## 0.1.1 — Alpine APK mirror retry

- Fix attempted for Raspberry Pi 5 install error: Alpine v3.22 APKINDEX fetch reported a temporary network error and apk misleadingly reported `python3`, `ffmpeg`, `git`, and `py3-pip` as unavailable.
- Docker build now tries the default Alpine CDN and three alternative Alpine package mirrors.
- If all mirrors fail, check Home Assistant Supervisor/Docker DNS and outbound HTTPS; this version has not yet been rebuilt on the user's Pi.
- No change to EZVIZ account, saved token, stream URL or Lovelace camera configuration.

## 0.1.0 — Experimental Raspberry Pi 5 test

- Added Home Assistant OS aarch64 add-on with Python 3.12 and FFmpeg.
- Pinned pyEzvizApi source revision, loopback-only EZVIZ cloud video proxy.
- Private first-login token persistence in /data and option to force re-login.
- Supervised process restart, initial go2rtc and WebRTC Lovelace setup guide.
- **Not yet verified:** container build on Pi 5, running auth flow, long-term stream, second camera.
