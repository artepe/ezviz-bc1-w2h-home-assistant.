# EZVIZ BC1 / W2H Cloud Proxy - camera manager v0.2.1

**Aani (0.2.1):** uudet kopioitavat asetukset ovat `#video=copy#audio=aac` ja `media: video,audio`. Korvaa myos aiemmin tallennetut go2rtc- ja korttiasetukset ja kaynnista go2rtc uudelleen. **Test audio** kertoo, onko lisaosan lahteessa aaniraita. [Aanen kayttoonotto ja vianhaku](../docs/AUDIO.md).

**Uusi kameran hallinta:** paivita olemassa oleva lisaosa versioon **0.2.0** ja valitse **Open Web UI / Avaa kayttoliittyma -> Add new camera**. Asetusten tallennus varmennetaan Home Assistantista, ja aiemmat kameratunnukset seka portit sailyvat tuettuina. Lisaosa loytyy myos sivupalkista nimella **EZVIZ Cameras**, kun Show in sidebar on valittu.

**[Nykyinen paivitys- ja kameran lisaysohje / current upgrade guide](../docs/UPGRADE_0_2.md).** Tama hallintanakyma kuuluu lisaosaan; Home Assistantin sisaisen EZVIZ-integraation laite- ja anturisivu on erillinen.

The following sections retain the original installation and hardware-test history. Use the linked 0.2.0 guide for current update and camera-management instructions.

**v0.1.3 adds an optional second camera.** The single-camera hardware test below was performed with v0.1.2. The new two-camera process supervision and token isolation have offline test coverage; second-camera live video and simultaneous viewing still require a hardware test.

**Tested on Raspberry Pi 5 / Home Assistant OS on 2026-10-11:** prebuilt v0.1.2 image installed; EZVIZ login succeeded; private token was saved; Python cloud proxy started; the **BC1 live camera appeared in go2rtc AND in the Home Assistant Lovelace WebRTC card using the Raspberry Pi loopback source**. The old MacBook proxy remains an optional fallback. This is still experimental: reboot recovery, multi-hour reliability, cloud token renewal and second-camera operation have not yet been verified.

## Mikä tämä on?

Tämä Home Assistant OS -lisäosa ajaa testatussa kokoonpanossa **EZVIZ BC1 -akkukameran / W2H-tukiaseman** Python-videopalvelimen suoraan **Raspberry Pi 5:llä**, ilman MacBookia.

Virta kulkee **EZVIZ-pilven** kautta:

```text
EZVIZ BC1 + W2H -> EZVIZ cloud -> pyEzvizApi on Pi 5
   -> 127.0.0.1:8558 -> go2rtc -> WebRTC Lovelace card
```

**Tämä EI ole offline-RTSP eikä uusi oma EZVIZ-protokollatoteutus.** Videovirran hakemisessa käytetään [RenierM26/pyEzvizApi](https://github.com/RenierM26/pyEzvizApi) -kirjastoa.

## Asennus Home Assistant OS:ään

1. GitHub-repositorion pitää olla **Public**, jotta Home Assistantin lisäosakauppa voi hakea sen ilman kirjautumista.
2. Home Assistant → **Settings → Apps / Add-on Store → ⋮ → Repositories**: lisää
   `https://github.com/artepe/ezviz-bc1-w2h-home-assistant.`
3. Päivitä sovelluskauppa ja valitse **EZVIZ BC1 / W2H Cloud Proxy (TEST)**.
4. Asenna lisäosa. Versiosta **0.1.2** alkaen Pi **lataa valmiin ARM64-Docker-imagen** GitHub Container Registrystä, eikä sen tarvitse rakentaa imagea Alpine-paketeista. Tämä kiersi testikoneen Docker-ympäristön APKINDEX/DNS-latausongelman.
5. Avaa lisäosan **Configuration** ja syötä:
   - **camera_serial**: BC1-alakameran koko tunnus, esimerkiksi `HUB_SERIAL-CAMERA_SERIAL` (ei pelkkä W2H:n tunnus).
   - **username**: EZVIZ-tilisi sähköpostiosoite.
   - **password**: EZVIZ-tilisi salasana (ei kameran kuvan salaus-/verification-koodi).
   - **force_relogin**: `false`
   - **restart_delay**: `30`
6. **Save → Start → Log**. Etsi lokista `EZVIZ token saved` ja `Proxy process started`.
7. Tarkista go2rtc:n yhteys alla olevan YAML:n avulla. BC1:n livekuva näkyi tällä asetuksella Pi:n go2rtc:ssä **11.10.2026**; vasta tämän jälkeen vanhan MacBook-videopalvelimen voi pysäyttää.

**Huomio tunnuksista:** Home Assistantin add-on Configuration tallentaa tunnukset asetuksiinsa, joita voidaan varmuuskopioida. Älä jaa asetustiedostoja tai varmuuskopioita. Istuntotunniste tallennetaan lisäosan yksityiseen `/data/ezviz_token.json`-tiedostoon, jota ei julkaista GitHubiin. Voit poistaa käyttäjätunnuksen ja salasanan asetuksista onnistuneen ensikirjautumisen jälkeen, jos istunto jatkaa toimintaansa. Kun istunto vanhenee, anna ne uudelleen ja valitse `force_relogin: true` yhden käynnistyksen ajaksi; palauta sen jälkeen `false`.

**MFA-rajoitus:** Ensiversion kirjautuminen on headless eikä osaa pyytää 2FA-koodia vuorovaikutteisesti. Jos tilisi vaatii MFA-vahvistuksen, kirjautuminen voi epäonnistua.

## Vaihda go2rtc MacBookista Pi:hin

go2rtc → **config**: korvaa olemassa olevan `ezviz_bc1`-virran arvo. Säilytä muu sisältö ennallaan.

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://127.0.0.1:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

Vaihda `YOUR_HUB_SERIAL-YOUR_BC1_SERIAL` samaan koko tunnukseen kuin lisäosan `camera_serial`.

Tässä käytetään `127.0.0.1`, koska **sekä tämä lisäosa että AlexxIT/go2rtc-lisäosa käyttävät Home Assistant OS:n host-verkkoa**. Videopalvelin on tarkoituksella vain paikallisesti saatavilla. Älä lisää porttiohjausta internetistä!

`#video=copy` on todennettu videoasetus. `#audio=copy` antoi MacBook/Pi-välitysketjussa virheen `AAC with no global headers is currently not supported`. Toimivaksi todettu asetus välittää tässä vain videon.

Testaa ensin go2rtc:n oma **ezviz_bc1 → stream**, sitten Home Assistantin Lovelace-kortti. **Molemmat toimivat Pi 5:n videopalvelimella 11.10.2026 toteutetussa testissä:**

```yaml
type: custom:webrtc-camera
url: ezviz_bc1
mode: mse
media: video
ui: true
title: EZVIZ BC1 – Live
```

### Valmis Lovelace-valvomokortti

Alla on testatussa järjestelmässä toimiva manuaalinen Lovelace-kortti. Asenna ensin HACS [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC) ja määritä WebRTC-integraatio käyttämään go2rtc:tä.

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## 📹 EZVIZ BC1 / W2H
      **Livekamera – Raspberry Pi 5**
      Videovirta: EZVIZ Cloud → go2rtc → WebRTC
  - type: custom:webrtc-camera
    url: ezviz_bc1
    mode: mse
    media: video
    ui: true
    muted: true
    title: EZVIZ BC1 – LIVE
```

Jos streamin nimi on `ezviz_bc1_pi`, vaihda vain `url: ezviz_bc1_pi`. Huomio: pitkäaikainen livekatselu voi kuluttaa BC1-akkua.

## Jos testi epäonnistuu

- Jos lisäosa ei näy: varmista että GitHub-repo on **Public**, osoite on täsmälleen oikein (repon nykyisessä nimessä on loppupiste), ja päivitä sovelluskauppa.
- Jos vanhan version Docker-imagen rakentaminen epäonnistui Alpine/APKINDEX-virheeseen, päivitä lisäosakauppa ja asenna **v0.1.2**, joka lataa esirakennetun ARM64-imagen. Jos se ei lataudu, tarkista Supervisorin lokit ja GitHub-paketin julkinen näkyvyys.
- Jos kirjautuminen epäonnistuu: tarkista EZVIZ-tunnukset, pilviyhteys, DNS ja mahdollinen MFA.
- Jos kamera ei vastaa: BC1 saattaa olla lepotilassa; avaa kameranäkymä virallisesta EZVIZ-sovelluksesta ja kokeile uudestaan.
- Jos lataat kuvaa, mutta se ei näy: katso go2rtc-logi ja varmista, että MacBookin IP on poistettu `ezviz_bc1`-määrityksestä.
- Jos token vanhenee: syötä kirjautumistiedot ja kokeile `force_relogin: true` kerran.
- Jos haluat palata toimivaan versioon, palauta go2rtc:n vanha MacBook-URL:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://YOUR_MAC_IP:8558/YOUR_HUB_SERIAL-YOUR_BC1_SERIAL.ts#video=copy
```

**Älä lähetä kuvakaappauksissa salasanoja, lisäosan `options.json`-tiedostoa, `ezviz_token.json`-tiedostoa tai EZVIZ-istunto-URL:ia.** Kolmannen osapuolen kirjaston virhelokissa voi esiintyä tunnuksia, joten lisäosa piilottaa sen suoran tulosteen.

## Testausraportti

Koko Raspberry Pi 5 -ketjun onnistunut testi, mukaan lukien Home Assistantin Lovelace-kortti, on dokumentoitu englanniksi: [End-to-end verification, 2026-10-11](../docs/VERIFIED_PI5_2026-10-11.md).

## Toinen kamera (v0.1.3)

Paivita olemassa oleva lisaosa versioon **0.1.3**, kun GitHub Actions -imagebuild on valmistunut. Avaa lisaosan **Configuration -> YAML** ja lisaa toinen tunnus:

```yaml
camera_serial: YOUR_HUB_SERIAL-YOUR_FIRST_CAMERA_SERIAL
camera_serial_2: YOUR_HUB_SERIAL-YOUR_SECOND_CAMERA_SERIAL
```

Sailyta muut tilisi asetukset. Molempien kameroiden tulee nakya samalla EZVIZ-tililla. Toinen tunnus on valinnainen; sen voi jattaa pois tai tyhjaksi. Tallenna ja kaynnista lisaosa uudelleen. Ensimmainen kamera kayttaa porttia 8558 ja toinen porttia 8559.

Lisaa go2rtc:n olemassa olevaan `streams:`-osaan:

```yaml
  ezviz_bc1_2:
    - ffmpeg:http://127.0.0.1:8559/YOUR_HUB_SERIAL-YOUR_SECOND_CAMERA_SERIAL.ts#video=copy
```

Tallenna, kaynnista go2rtc uudelleen tarvittaessa ja kokeile ensin toisen kameran kuvaa sen omasta websoittimesta. Lisaa sen jalkeen dashboardille manuaalinen kortti:

```yaml
type: custom:webrtc-camera
url: ezviz_bc1_2
mode: mse
media: video
ui: true
muted: true
title: EZVIZ kamera 2
```

Valmiit kahden kameran esimerkit: [go2rtc](../examples/go2rtc-two-cameras.yaml) ja [dashboard](../examples/lovelace-two-cameras.yaml). Kaynnistysloki kertoo prosessien kaynnistymisesta, mutta livekuva on tarkistettava erikseen. Toisen kameran ja molempien samanaikaisen katselun toimintaa ei viela ole testattu oikealla laitteistolla.

## Technical details (English)

- **Architecture:** aarch64 only (Raspberry Pi 5).
- **Base:** pinned Home Assistant Alpine 3.22 image with Python 3.12, FFmpeg.
- **API dependency:** pinned [pyEzvizApi revision](https://github.com/RenierM26/pyEzvizApi/commit/6df75d95a2ee6a68fb71446ee74a55572e2014ea).
- **Source:** EZVIZ VTM cloud, not W2H local RTSP.
- **Bind:** camera 1 on 127.0.0.1:8558; optional camera 2 on 127.0.0.1:8559. `host_network: true`; no public video service.
- **Token:** persisted under private app `/data`. The first session remains in `ezviz_token.json`; the second uses its own copy in `ezviz_token_camera_2.json` so the proxies do not write the same token file concurrently. The second copy is refreshed from the first before workers start.
- **Process monitoring:** each proxy automatically restarts on exit with its own configurable retry delay. Shutdown terminates both owned process groups, including FFmpeg children.
- **Logging:** raw dependency error messages suppressed because they can contain session tokens.
- **Scope:** up to two BC1 cameras per app instance in v0.1.3. One BC1 camera's live feed was verified on v0.1.2 from the Pi app through go2rtc AND the Home Assistant Lovelace WebRTC card. Two-camera live video remains unverified.
- **Limitations:** Pi install, first-login, token persistence, go2rtc live picture and **Pi-only Lovelace live view all verified 2026-10-11**. Boot recovery, multi-hour uptime, token renewal, second-camera support and battery impact remain unverified. No interactive MFA login or audio in the verified video pipeline.

This add-on is a **working initial Pi proof of concept**, not a production-ready integration.

## Prebuilt container image (v0.1.2, installed successfully on Pi)

The GitHub Actions job **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for linux/arm64. The add-on's `config.yaml` points to this image, avoiding the Pi's Alpine `apk` networking failure.

**Important:** GitHub Container Registry packages may start **Private**, even when this code repository is Public. To allow Home Assistant OS to pull the image, open **GitHub → your profile → Packages → ezviz-bc1-w2h → Package settings → Change visibility → Public**. This publishes the compiled image, **not** your EZVIZ account information.

For the two-camera update, run `ha store reload` and check `version_latest: 0.1.3` before updating the app. Wait for its GitHub Actions build to succeed so the matching image is available. If the image pull fails with access denied, check the GHCR package visibility. If it fails for DNS/connectivity, inspect the Supervisor logs.
