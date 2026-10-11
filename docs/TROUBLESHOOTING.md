# Troubleshooting / Vianhaku

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
