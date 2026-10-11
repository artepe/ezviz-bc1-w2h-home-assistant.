# Changelog

## 2026-10-11 — Complete end-to-end Pi 5 + Lovelace validation (v0.1.2)

- Confirmed Home Assistant OS / Pi 5 installs the prebuilt `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` image successfully.
- Confirmed addon starts, authenticates to EZVIZ, writes a private session token under `/data`, and starts the `pyEzvizApi` cloud MPEG-TS proxy bound to `127.0.0.1:8558`.
- Confirmed BC1 live image appeared in both the **go2rtc browser player AND the Home Assistant Lovelace WebRTC card** using `ffmpeg:http://127.0.0.1:8558/YOUR_SERIAL.ts#video=copy`; MacBook stream proxy was no longer required.
- Published reusable Lovelace WebRTC card, Pi-first setup guide and [verification report](../docs/VERIFIED_PI5_2026-10-11.md).
- Remaining validation: restart-on-boot, cloud session renewal, second BC1, audio, long-term uptime and battery use.

## 0.1.2 — Prebuilt ARM64 Docker image from GitHub Actions

- GitHub Actions successfully built and published `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for linux/arm64.
- Python CLI and FFmpeg smoke tests on the built image succeeded under QEMU.
- Home Assistant add-on now uses `image:` and pulls the ready-made image instead of building on Raspberry Pi (workaround for Docker/Alpine DNS network errors).
- **The GitHub Container Registry package must be Public for unauthenticated installation.** On GitHub go to your profile → Packages → ezviz-bc1-w2h → Package settings → Change visibility → Public.
- Subsequent 2026-10-11 hardware test confirmed Pi 5 deployment, headless EZVIZ login and go2rtc live stream; reconnection remains unverified.

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
