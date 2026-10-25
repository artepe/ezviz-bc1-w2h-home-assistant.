# Troubleshooting / Vianhaku

## Cloud trace says zero packets, but phone app plays video

In 0.2.9 the source trace could yield an empty post-handshake packet list because the first-packet window was only 10 seconds. The separate `stream.start()` call consumes the negotiation response, so `0 control packets` cannot be taken to mean there was no cloud response. The old report also omitted `ENCRYPTED_STREAM` channel from media counts.

After the 0.2.10 image is published and updated, close go2rtc live players and the EZVIZ phone live view before pressing **Analyze cloud** once per camera. The report includes safe `VTM handshake result`, `session reported`, post-handshake RTP/MPEG_PS/MPEG_TS/UNKNOWN counts and encrypted counts. No raw video or authentication strings are returned. There may still be no packets: that indicates no packets **during the bounded observation**, not a permanent network failure.

Use this result before changing transport or decryption logic. Do not toggle `allow_encrypted`, guess media keys, reset camera serials, or edit video-only go2rtc sources to solve an upstream `FFMPEG_BAD_INPUT` without confirming the actual source format.


## FFMPEG_BAD_INPUT persists on 0.2.8 and both go2rtc feeds time out

Version 0.2.9 adds a privacy-safe upstream VTM packet inspection. Open EZVIZ Cameras, close other live views, and click **Analyze cloud** separately for each camera. The diagnostic tells whether the raw EZVIZ video channel is RTP, MPEG_PS, MPEG_TS, unknown or flagged encrypted, without capturing media bytes or exposing session information. It does not decode video, and cannot by itself prove codec compatibility. A trace with control packets but no video-channel packets means no media was observed during the bounded test. Tests are user initiated and are limited to once per 90 seconds per camera.

If source packets are RTP, investigate codec/parameter-set reception; if MPEG_PS, investigate missing pack/PES framing; if unknown or encrypted, first investigate upstream format/decryption. Do not keep cycling camera serials or go2rtc settings, because the proxy already reports FFMPEG_BAD_INPUT.


## Two BC1 streams fail with FFMPEG_BAD_INPUT after hub reconnect

The official EZVIZ phone app can show video while the experimental cloud proxy cannot remux the same camera's cloud media. Go2rtc cannot repair the proxy's HTTP 502. The upstream `pyEzvizApi` package pinned at 2026-10-10 did not include the subsequent cloud RTP timing fix PR #308.

Experimental 0.2.8 switches to the **2026-10-11 upstream version** pinned to `a38ba757a3686cb412cc5029225e2608cdbccc4b`. No camera or credentials changes. After the ARM64 CI image is published, update the existing EZVIZ app, open **EZVIZ Cameras → Test video** with other viewers closed, and then try go2rtc with the existing video-only streams. Confirm both cameras separately; a successful installation or healthy proxy process does not mean live video works.

If Test video still reports `FFMPEG_BAD_INPUT`, **stop repeated restarts**: the actual input is still unsupported or incomplete. Record the exact error code and investigate source media format separately; don't post raw FFmpeg stderr or EZVIZ URLs containing session tokens. Version 0.2.7 is the prior published rollback image. The 0.2.8 change is not a verified hardware repair.


## EZVIZ phone app live video works, but Test video returns FFmpeg HTTP 502

When W2H and both cameras stream normally in the EZVIZ mobile app, do not remove/re-add the cameras or keep refreshing account credentials. The app proxy has already reached the video processing stage, and the video conversion failure needs a more specific cause. Updating go2rtc sources does not repair a failing upstream MPEG-TS URL.

Version 0.2.7 examines FFmpeg failure details **only within the trusted add-on server**, and returns fixed, privacy-safe diagnostic codes from **Test video**:

- `FFMPEG_BAD_INPUT`: the data stream couldn't be parsed as expected (incomplete/unsupported input possible)
- `FFMPEG_NO_VIDEO`: there was no usable video stream to remux
- `FFMPEG_VIDEO_HEADER`: initial video headers or dimensions are absent
- `FFMPEG_TIMESTAMPS`: cloud media timing may be incompatible with remux
- `FFMPEG_BITSTREAM`: malformed video frame data
- `FFMPEG_PIPE`: FFmpeg lost a pipe (e.g. a media client disconnected)
- `FFMPEG_MISSING`, `FFMPEG_STALLED`, `FFMPEG_EXIT`, or generic `FFMPEG_REMUX`: other specific or unrecognized cases

First update the EZVIZ app after the validated ARM64 image is published, then open **EZVIZ Cameras → Test video** for one camera, and report only the diagnostic code. Keep the raw stderr private; it can include session URLs. The pinned pyEzvizApi version is intentionally unchanged until the fault is classified; later cloud RTP fixes might be useful only if they match the actual cause.


## HTTP timeout after disconnecting the W2H Ethernet cable (0.2.6)

The BC1 cameras use the W2H base station and EZVIZ cloud. Removing the W2H Ethernet cable takes the hub offline unless a working alternative network connection is configured. Restarting the Home Assistant app cannot bring an offline hub back onto the network.

1. Reconnect the W2H Ethernet cable to a working router/switch and check the W2H is **online** and both BC1 cameras show live view in the EZVIZ mobile app. If Wi-Fi is used instead of Ethernet, check the hub's actual wireless connection in the app/router. Do not assume Wi-Fi failover is configured.
2. Update the Home Assistant EZVIZ BC1 / W2H Cloud Proxy app to 0.2.6 and restart it. Open its **Open Web UI** page.
3. Run **Test video** for each configured BC1. The test allows up to 35 seconds for a sleeping camera after a hub outage. **Proxy ready** only means the local port is listening, not that the EZVIZ cloud supplied video.
4. If W2H is back online but no video arrives, click **Restart proxy** for the affected camera only, wait for it to restart, and run **Test video** again. The action is limited to once per minute; it does not delete session tokens or restart the other camera.
5. If Test video reports an expired session, the app's existing five-minute session refresh logic may sign in again. For persistent authentication errors inspect account settings. If Test video still fails with HTTP 502 codes VTM_ENCRYPTED, RTP_CODEC or RTP_INCOMPLETE, restarting the hub or local app is not proof of a software-media fix: record the exact diagnostic code for further investigation.
6. When Test video returns MPEG-TS, check the go2rtc video-only streams at ports 8558 and 8559, then the corresponding Lovelace cards. Avoid continual tests on battery cameras.


**2026-10-11 update:** Complete Raspberry Pi 5 add-on → go2rtc → Home Assistant Lovelace video playback is now verified working. See the [test report](VERIFIED_PI5_2026-10-11.md). The MacBook instructions are preserved as an optional fallback.

## Camera appears in `devices status`, but video does not start

- Verify that you selected the **BC1 subcamera** device, not only the W2H hub.
- The BC1 may sleep or report temporarily offline. Wake it through the official app and try again.
- The cloud VTM stream and account authorization must work; normal API login alone does not guarantee live streaming.

## `resultCode: 20002` / `MFA code required`

This was raised by pyEzvizApi when its **camera encryption key lookup** returned `resultCode: 20002`. The upstream library labels it MFA. In our test the response also contained Chinese `好友不存在` (friend not found); the server's exact meaning was not established. **Do not assume your EZVIZ account password is the media encryption code.**

The successful capture and proxy **did not use `--decrypt-video`**; they obtained a playable clear H.264 stream. Whether this works depends on the account/device and media encryption settings.

## `dig` resolves a hostname but `curl`/Python cannot

macOS `dig` can use a different DNS path than applications calling `getaddrinfo`.

```bash
dig @1.1.1.1 +short euauth.ezvizlife.com
python -c 'import socket; print(socket.getaddrinfo("euauth.ezvizlife.com",443)[0][4][0])'
curl -sS -o /dev/null -w '%{http_code}\n' https://euauth.ezvizlife.com/
```

In the successful experiment, temporarily configuring the Mac Wi-Fi DNS to `1.1.1.1` and `9.9.9.9` made Python and curl resolve the host. This does **not** prove that AdGuard blocked it; the resolver routing itself may have been involved. Do not modify DNS before checking current settings.

## go2rtc: `AAC with no global headers is currently not supported`

`ffmpeg:http://...#video=copy#audio=copy` caused an RTSP header error in the tested pipeline. **Working fix:** remove `#audio=copy` and keep `#video=copy`.

## `Stream network error` in Home Assistant Generic Camera

Check that the HA machine can actually reach the Mac HTTP proxy:

```bash
curl -sS --connect-timeout 5 --max-time 15 -o /tmp/ezviz_test.ts \
  -w 'HTTP=%{http_code} bytes=%{size_download}\n' \
  http://YOUR_MAC_LAN_IP:8558/YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL.ts
```

`HTTP 200` plus downloaded bytes means the network path responds; `curl (28)` is expected for an uninterrupted live stream stopped after 15 s. The data might still be invalid video until `ffprobe` verifies it.

In our setup Generic Camera initially reported a stream error for HTTP `.ts`, then timed out loading go2rtc's RTSP URL. **go2rtc's own browser player and WebRTC Camera Lovelace card both worked.** Prefer that verified path over repeatedly retrying Generic Camera without logs.

## `127.0.0.1` and which machine hosts the proxy?

In the **recommended Raspberry Pi 5 add-on**, both the EZVIZ cloud proxy and AlexxIT/go2rtc run with host networking. Hence **`127.0.0.1:8558` in go2rtc is the Pi's own EZVIZ proxy**, and this loopback source is verified working. The Home Assistant web interface address and port `8123` are NOT the MPEG-TS source.

In the **older MacBook-based configuration**, `127.0.0.1` on MacBook refers to the MacBook, not to Home Assistant. The Mac HTTP proxy needs to bind to the **Mac's LAN IP**, and go2rtc must use that address. Do not run macOS `ipconfig` in Home Assistant OS Terminal.

The WebRTC integration's `http://localhost:1984` is a **separate** address for go2rtc running alongside Home Assistant; its actual reachability depends on installation networking. go2rtc's WebUI was also directly accessible at the HA host's LAN IP and port 1984 in the tested setup.

## go2rtc still connects to the old MacBook IP / Connection refused

**Observed during successful Pi migration:** The Python add-on started, but go2rtc player continued reporting an old MacBook IP with `Connection refused`. The Pi did not cause that error: go2rtc was still using the previously saved source URL.

Go to **go2rtc → Web UI → config** and update the existing camera stream **without duplicating** `streams:` or the source key:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

Save, restart the go2rtc add-on if necessary, and open the **same stream name** (`ezviz_bc1 → stream`). If you added a separate Pi test stream named `ezviz_bc1_pi`, choose that stream in the player and set `url: ezviz_bc1_pi` in the Lovelace card.

**The Pi-hosted source and matching Home Assistant WebRTC Lovelace card both worked in the 2026-10-11 hardware test.**

## Pi 5 install fails while trying to fetch Alpine APKINDEX

On the tested Home Assistant OS machine, Docker build failed on `apk add` because all attempted Alpine mirrors returned temporary fetch errors. The Terminal having working DNS and HTTP access did not guarantee container build networking worked. Changing DNS or disabling AdGuard protection did not resolve the build.

The successful workaround was to build and smoke-test a Linux ARM64 image with GitHub Actions and **install add-on version 0.1.2 with a prebuilt GHCR image** rather than building locally.

```bash
ha store reload
ha apps install YOUR_REPOSITORY_PREFIX_ezviz_bc1_w2h
```

Use the actual slug returned by `ha store`; the repository-prefix part differs between installations. If image download is denied, check GHCR package visibility. If download is unreachable, inspect the **Supervisor** logs rather than the Home Assistant Core logs.

## `then dquote>` prompt on macOS

This is zsh waiting for a closing quote. Press **Control+C** (not Command+C) to cancel the unfinished command. Paste complete commands in the MacBook Terminal, not the HA shell.

## Security and logs

Detailed Python exception traces can include **EZVIZ session credentials inside query string URLs**. Do not post full traces unredacted. Keep logs private, change exposed credentials, and rotate compromised sessions.

## Platform expectations

- **Proven 2026-10-11:** **Pi 5 add-on pyEzvizApi → cloud MPEG-TS loopback proxy → Pi go2rtc → Home Assistant Lovelace WebRTC card**, with MacBook not needed as the stream server. Original MacBook proxy was also verified.
- **Not yet proven:** recovery from Home Assistant OS reboot, session renewal after cloud token expiry, independent second BC1, long-term uptime, exact power draw, battery impact, on-demand wake API.
