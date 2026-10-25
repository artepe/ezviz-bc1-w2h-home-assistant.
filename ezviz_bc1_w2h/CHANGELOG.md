# Changelog

## 0.2.9 - Bounded source-protocol diagnosis (no video capture)

- Add a manual **Analyze cloud** action for saved BC1 cameras. It runs the installed pyEzvizApi `stream trace` inside the EZVIZ app container and reports only counts of RTP, MPEG-PS, MPEG-TS, unknown and encrypted video-channel packets.
- Do not collect/store video bytes, credentials, cloud URLs, FFmpeg stderr or other packet contents. Ignore any unknown fields in the trace JSON. Suppress raw subprocess errors, bound tests to 24 trace packets and 45 seconds, serialize traces and rate-limit repeated requests per camera to 90 seconds.
- CSRF-protect the ingress endpoint and restrict it to saved camera ports; only configured private token file is used. Add unit and endpoint tests.
- Existing 0.2.8 pinned pyEzvizApi, proxy behavior and all go2rtc stream definitions are unchanged. This is a source-protocol diagnosis, not a verified decoding fix.


## 0.2.8 - Trial cloud RTP media timing fix for FFmpeg_BAD_INPUT

- Move the pinned `pyEzvizApi` dependency from 2026-10-10 commit `6df75d95a2ee6a68fb71446ee74a55572e2014ea` to 2026-10-11 commit `a38ba757a3686cb412cc5029225e2608cdbccc4b` (upstream PR #308), which updates cloud RTP stream timing and packet processing relevant to FFmpeg MPEG-TS remuxing.
- Investigates observed `HTTP 502 [FFMPEG_BAD_INPUT]` on EZVIZ BC1/W2H where the mobile app live view works but both Home Assistant streams fail. This is an **experimental upstream fix**, not yet hardware-verified for this failure.
- Retain existing EZVIZ credentials/session storage, two-camera ports, go2rtc video-only sources, per-camera restart, and privacy-safe diagnostics.
- CI builds and smoke-checks the pinned ARM64 image before publishing. If the test still returns FFMPEG_BAD_INPUT, collect the new diagnostic result and revert to prior published 0.2.7 if necessary.


## 0.2.7 - Precise, privacy-safe FFmpeg failure codes

- Fix overly generic `HTTP 502 [FFMPEG_REMUX]` Test video error classification. The upstream library returns a bounded FFmpeg stderr tail, but previous versions hid all actionable details under one label.
- Detect missing FFmpeg, missing video stream, invalid input, missing codec/frame headers, invalid timestamps, broken video bitstream, broken pipes, stalled input writers and unknown FFmpeg process exits.
- Show only allowlisted constant messages; never display FFmpeg stderr, signed URLs, raw HTTP payloads or private camera/account details.
- Preserve the known-working pinned pyEzvizApi version, proxy topology, EZVIZ login and video-only go2rtc sources while gathering a real cause from hardware.
- Add privacy-safe regression coverage for each new FFmpeg diagnosis.


## 0.2.6 - Manual recovery from W2H / BC1 connectivity outages

- Extend the user-initiated Test video network timeout from 15 to 35 seconds to allow sleeping BC1 cameras to wake after the base station reconnects.
- Add a one-camera Restart proxy action in the ingress UI, rate-limited to once a minute per camera. It restarts the selected local streaming subprocess without erasing EZVIZ sessions or changing another camera.
- Provide a separate safe DEVICE_OFFLINE diagnosis when the cloud explicitly reports an offline hub/camera, and actionable W2H cable/connectivity guidance for test timeouts.
- Keep automatic repeated cloud stream probing disabled to avoid draining battery cameras or creating a request storm. Physical hub connectivity must be restored before local software recovery can work.
- Add isolated worker restart, ingress security, and offline-hub classification regression tests.

## 0.2.5 - Distinguish cloud media failure causes

- Improve Camera manager Test video HTTP 502 reporting: identify encrypted VTM stream packets, RTP codec detection, missing video frames/routes, FFmpeg remux failures, MPEG transport and decryption issues separately.
- Continue to use allowlisted, fixed messages; never log or display raw cloud URLs, session tokens, serials or error bodies.
- No camera configuration, stream parameters or upstream pyEzvizApi dependency changed. Further corrective changes depend on the new diagnostic code from actual hardware.


## 0.2.4 - Safe EZVIZ cloud video diagnostics

- Camera manager Test video now classifies the upstream HTTP 502 response from pyEzvizApi into cloud session, VTDU video token, VTM resource/server, no-media timeout, network and media conversion cases.
- Raw upstream error bodies are never logged or shown because they can include EZVIZ tokens, camera serials and private cloud URLs.
- If the upstream error specifically reports an invalid or expired EZVIZ cloud session, schedule a token refresh and restart the affected proxy sessions. Coalesce requests and allow at most one refresh every five minutes to avoid repeated login attempts. General video timeouts and sleeping battery cameras never trigger this reset.
- Add offline regression tests for safe messages, secret non-disclosure and refresh backoff. Camera sources and credentials remain unchanged.


## 0.2.3 - Restore Supervisor environment through s6 startup (2026-10-15)

- Launch `run.sh` through `/command/with-contenv bash`, restoring the container environment before starting Python. The previous plain Bash launcher did not load the environment saved by s6, including `SUPERVISOR_TOKEN` and `APP_VERSION`.
- Keep the documented self-only Supervisor endpoints and existing default role. Missing tokens and HTTP 403 now produce distinct controlled diagnostics without exposing response bodies or token values.
- Log a repeated Supervisor settings error at most once per five minutes unless its reason changes. Report recovery, retain the last loaded configuration on failure, and keep retrying every 15 seconds.
- Add an actual ARM64 container-startup check using the default `/init -> run.sh -> runner.py` path and synthetic environment values. Earlier module checks overrode the entrypoint and did not exercise this path. Compare the previous 0.2.2 image as a one-release regression baseline.
- Load the built ARM64 image locally in CI, complete the module/media/default-startup checks, and only then push the validated image to GHCR.
- Add HTTP contract tests for rendered self configuration, preservation of raw secret references, missing environment tokens and forbidden access. Real camera/cloud behavior still needs the next user-side video test.

## 0.2.2 - Restore video defaults and isolate audio experiments (2026-10-15)

- Restore `#video=copy` and `media: video` in default snippets and examples after a report that the 0.2.1 audio configuration stopped video playback. The exact failure needs a fresh go2rtc log; AAC audio playback is not certified on BC1 hardware.
- Keep **Test audio** and add clearly marked experimental audio snippets under a separate disclosure. They use a distinct `_audio_test` alias and temporary card, preserving the working video alias.
- Clarify that detecting an audio track does not prove microphone volume, valid audio packets, or successful browser playback. Explain how to restore existing go2rtc/card settings; installing the app does not edit them.
- Add a regression check that audio examples cannot replace the primary video stream alias. Existing camera storage, ports, authentication and proxy commands are unchanged.

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
