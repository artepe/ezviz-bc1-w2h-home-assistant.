# EZVIZ BC1 Legacy Cloud Test — original 0.1.2 baseline

**Purpose:** Compare the original cloud-based BC1/W2H path known to have shown
video in Home Assistant on 2026-10-11 against current 0.2.13.

This is an **isolated diagnostic add-on**, not a claim that the original
cloud protocol still works today. It uses the historical single-camera
runner and the original pyEzvizApi source revision
6df75d95a2ee6a68fb71446ee74a55572e2014ea.
Its OS base and transitive pip dependencies may have changed since 2026-10-11.

The old architecture uses **EZVIZ cloud/VTM**, not the local UDP P2P
traffic captured from the iPhone. The original working Mac/Pi video was
H.264 and the go2rtc stream was video-only.

## Non-destructive isolation

- Different HA app slug: ezviz_bc1_legacy (does not replace ezviz_bc1_w2h).
- Independent /data options and EZVIZ token (must sign in separately).
- Legacy proxy listens on 127.0.0.1:8668; current proxy keeps 8558/8559,
  experimental hybrid keeps 8658. Both add-ons use host networking.
- Boot mode manual; the test does not start on every system reboot.
- One BC1 only, exactly like the early version. Do not migrate two-camera
  configurations into it.

## Installing after the GitHub Actions image build succeeds

1. In GitHub Actions, wait until "Build original EZVIZ BC1 legacy test image"
   has completed both architectures and combined manifest successfully.
   No one should claim the image is available before then.
2. Home Assistant → Settings → Apps → App store → Refresh/reload store.
   This repository should already be configured:
   https://github.com/artepe/ezviz-bc1-w2h-home-assistant.
3. Install **EZVIZ BC1 Legacy Cloud Test**, then configure:
   - camera_serial: full BC1 subcamera serial
     G23915155-G28068598 (first camera)
   - username/password: your EZVIZ account (enter in HA options, never in GitHub)
   - force_relogin: false
   - restart_delay: 30
4. Start the legacy add-on. Its logs should say the cloud proxy started.
   This only means it is listening, **not** that video arrived.
5. Add a **new**, separate stream entry to the existing /config/go2rtc.yaml
   under the existing streams: map (do not create a second streams: key):

   ezviz_bc1_legacy: [ "ffmpeg:http://127.0.0.1:8668/G23915155-G28068598.ts#video=copy" ]

6. Restart only go2rtc after saving its configuration and test the new stream
   in the go2rtc UI: http://192.168.10.231:1984/
7. If live image appears, it proves the old protocol still works: the next
   step is to migrate its dependency/runtime into the modern two-camera add-on.
   If it fails with the **same VTM handshake result=5404**, reverting the
   Python runner is insufficient and the upstream EZVIZ session path must be
   fixed.

### Safe rollback

Stop/uninstall only **EZVIZ BC1 Legacy Cloud Test** and remove only the
new ezviz_bc1_legacy stream entry. The current 0.2.13 add-on, camera options,
and established go2rtc stream entries remain unchanged.

Do **not** make these ports internet-accessible. The MPEG-TS proxy is not
authenticated.
