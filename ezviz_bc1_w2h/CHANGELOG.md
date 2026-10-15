# Changelog

## 0.2.1 - Audio settings and source-track diagnostics (2026-10-15)

- Fix generated go2rtc settings to request `#video=copy#audio=aac` and Lovelace cards to request `media: video,audio`. The previous video-only source causes go2rtc to add FFmpeg `-an`, disabling audio. AAC is re-encoded to avoid the previously observed AAC global-header copy error.
- Add **Test audio** to the camera manager. Inspect the configured loopback source with a bounded FFprobe process, report audio codec/rate/channels, and distinguish video-only output from connection/probe failure. Only one audio probe runs at a time. No source URLs, account data or upstream error output are returned.
- Existing go2rtc and dashboard configuration must be replaced manually with the new snippets, and go2rtc restarted. The app does not edit these external configurations.
- Keep the pinned streaming library and working proxy commands unchanged. Its RTP audio export supports descriptor-backed AAC-LC with the required media key; other upstream formats can remain video-only. Actual BC1 microphone audio remains unverified on hardware.
- Validate audio metadata detection using generated AAC/video and video-only MPEG-TS fixtures, alongside the existing persistence, ingress and lifecycle tests.

## 0.2.0 - Camera manager and update packaging (2026-10-15)

- Added an ingress-only **EZVIZ Cameras** panel with **Add new camera**, editing, removal, an on-demand video transport test, and copyable go2rtc / Lovelace settings.
- Save options through Supervisor and read them back before confirming success. Restore previous settings if an older schema silently strips camera entries. Preserve account credentials and `!secret` references.
- Both legacy scalar camera fields now have explicit defaults and visible configuration translations. Existing serials and ports 8558 / 8559 are retained; the camera manager migrates them to a persistent list on its first save.
- Support up to 16 cameras with stable, non-overlapping ports. Reconcile changes without restarting unaffected camera proxies; retain each camera's refreshed private session.
- Keep the same app slug and GHCR package so the existing installation can be updated. Read image version/tag directly from the app manifest in the ARM64 build workflow, and smoke-test the packaged manager modules and static assets.
- Added offline migration, save/readback, HTTP API, ingress access, camera isolation and rollback checks. Hardware validation of 0.2.0 and live multi-camera operation is pending.

## 0.1.3 - Optional second BC1 camera (2026-10-12)

- Added optional `camera_serial_2`; existing one-camera options remain valid.
- Camera 1 keeps loopback port 8558. Camera 2 uses loopback port 8559.
- Each camera has a supervised proxy with independent restart timing and a separate private token file. Initial account authentication is reused before workers start.
- Terminate owned proxy process groups, including FFmpeg children, on shutdown or before restarting a failed worker.
- Added 13 offline tests for configuration compatibility, private token files, camera isolation, retries and shutdown. Run these checks before the ARM64 image build.
- Added two-camera go2rtc and Lovelace examples and upgrade instructions.
- **Hardware validation pending:** second-camera live video, simultaneous cloud streams, reboot recovery and long-term operation. The single-camera live-video test remains the v0.1.2 result from 2026-10-11.

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
