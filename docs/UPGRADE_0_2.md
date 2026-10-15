# Update to 0.2.0 and add cameras

Version 0.2.0 keeps the same repository, app slug and container package as the old installation. Update the existing app to retain its EZVIZ account and private session. There is no need to uninstall it.

## Install the update

1. Check that the [ARM64 image build](https://github.com/artepe/ezviz-bc1-w2h-home-assistant./actions/workflows/build-ezviz-image.yml) completed successfully for version 0.2.0. The image version is now read from `ezviz_bc1_w2h/config.yaml`, rather than hardcoded in the workflow.
2. In Home Assistant, open Settings -> Apps / Add-ons -> App store -> three-dot menu -> Check for updates / Reload.
3. Open the existing **EZVIZ BC1 / W2H Cloud Proxy (TEST)** app and select **Update**. Its installed version should become **0.2.0**.
4. Start the app and select **Open Web UI**. Optionally enable **Show in sidebar**; the panel is called **EZVIZ Cameras**.
5. The first camera is imported from `camera_serial`. A previously saved `camera_serial_2` is imported too. A field that was dropped by the old app must be added again.

The repository address includes its final dot:

```text
https://github.com/artepe/ezviz-bc1-w2h-home-assistant.
```

For the existing installation with app ID `6d530a54_ezviz_bc1_w2h`, the equivalent Home Assistant Terminal commands are:

```sh
ha store reload
ha apps update 6d530a54_ezviz_bc1_w2h
```

If Home Assistant still lists an older release, confirm that it has this exact repository, reload the app store, and inspect the Supervisor log if the repository fetch or container download fails. The GHCR package must remain public for an unauthenticated app install.

## Add new camera

1. In **Open Web UI**, select **Add new camera**.
2. Enter a name, such as `Backyard`.
3. Enter the W2H base station serial and the second BC1 serial, or paste the complete `HUB_SERIAL-CAMERA_SERIAL` identifier in Camera serial.
4. Select **Save camera**. The app saves through Supervisor, reads the settings back and confirms only if every camera was retained. An unsuccessful save displays an error; the previous options are restored if an old schema drops the new list.
5. The new proxy starts automatically. Adding or renaming another camera does not restart the first camera. If the second slot is available, it uses port 8559 and stream name `ezviz_bc1_2`.
6. Select **Test video** for an on-demand transport check. **Proxy ready** means that the local proxy is listening; it does not prove live video. The test checks one MPEG-TS packet; final picture playback is checked in go2rtc.
7. Expand **Connection & dashboard setup** and copy the go2rtc stream and Lovelace card. Merge the stream entry into the existing `streams:` mapping; do not add a second `streams:` key.

Up to 16 cameras can be configured. Each retains its assigned port when another camera is removed, preventing existing go2rtc URLs from changing. All cameras must be accessible through the configured EZVIZ account. Live multi-camera operation still needs validation on the actual cameras.

## Settings and compatibility

The two original options remain supported and now both have visible defaults:

```yaml
camera_serial: YOUR_HUB_SERIAL-YOUR_FIRST_CAMERA_SERIAL
camera_serial_2: YOUR_HUB_SERIAL-YOUR_SECOND_CAMERA_SERIAL
cameras: []
```

After the first save in the camera manager, these scalar fields are cleared and the cameras move into one list:

```yaml
camera_serial: ""
camera_serial_2: ""
cameras:
  - name: Driveway
    serial: YOUR_HUB_SERIAL-YOUR_FIRST_CAMERA_SERIAL
    port: 8558
  - name: Backyard
    serial: YOUR_HUB_SERIAL-YOUR_SECOND_CAMERA_SERIAL
    port: 8559
```

Account credentials, retry delay and secret references are preserved. The Web UI never returns credentials or cloud tokens to the browser. Do not populate both a scalar field and the list with the same camera; duplicates are rejected.

Camera 1 remains on port 8558, and camera 2 on 8559. Existing go2rtc and Lovelace entries for those ports continue to apply. Newly configured camera slots use ports 8560 through 8573.

## About the Home Assistant device screen

The built-in EZVIZ integration's device and entity screen belongs to Home Assistant Core. This app supplies a separate ingress camera manager; **Add new camera** is in **Open Web UI / EZVIZ Cameras**, not a new button on that Core device screen. Adding a proxy camera supplies a live-video source; it does not create or repair the built-in integration's sensor entities.

## Jos camera_serial_2 katosi tallennettaessa

Go2rtc:n streamin luominen ei kaynnista toisen kameran palvelinta. Ensin EZVIZ-lisaosan taytyy tuntea ja tallentaa kameran tunnus. Vanhan version asetusrakenne saattoi poistaa tuntemattoman kentan, jolloin portissa 8559 ei ollut palvelinta ja kortti naytti `Connection refused`.

Paivita olemassa oleva lisaosa versioon 0.2.0. Avaa **Avaa kayttoliittyma -> Add new camera**. Tallennus tarkistetaan nyt lukemalla asetukset takaisin Home Assistantista. Kameran voi lisata myos lisaosan Asetukset-valilehden nakyvaan Kameran 2 tunnus -kenttaan. YAML-asetukset tulevat voimaan lisaosan uudelleenkaynnistyksessa; kameran hallinnasta lisatty kamera kaynnistyy automaattisesti.
