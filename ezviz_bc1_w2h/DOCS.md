# EZVIZ BC1 / W2H Cloud Proxy — TEST v0.1.2

**Tested on Raspberry Pi 5 / Home Assistant OS on 2026-10-11:** prebuilt v0.1.2 image installed; EZVIZ login succeeded; private token was saved; Python cloud proxy started; the **BC1 live camera appeared in go2rtc using the Raspberry Pi loopback source**. The old MacBook proxy remains a tested fallback. This is still experimental: reboot recovery, multi-hour reliability, Pi-only Lovelace playback and second-camera operation have not yet been verified.

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

Testaa ensin go2rtc:n oma **ezviz_bc1 → stream** (**Pi-versiolla vahvistettu toimivaksi**), sitten Home Assistantin Lovelace-kortti (Pi-versiolla varmistettava erikseen):

```yaml
type: custom:webrtc-camera
url: ezviz_bc1
mode: mse
media: video
ui: true
title: EZVIZ BC1 – Live
```

### Valmis Lovelace-valvomokortti

Alla on hieman näyttävämpi manuaalinen Lovelace-kortti. Asenna ensin HACS [AlexxIT/WebRTC](https://github.com/AlexxIT/WebRTC) ja määritä WebRTC-integraatio käyttämään go2rtc:tä.

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

## Technical details (English)

- **Architecture:** aarch64 only (Raspberry Pi 5).
- **Base:** pinned Home Assistant Alpine 3.22 image with Python 3.12, FFmpeg.
- **API dependency:** pinned [pyEzvizApi revision](https://github.com/RenierM26/pyEzvizApi/commit/6df75d95a2ee6a68fb71446ee74a55572e2014ea).
- **Source:** EZVIZ VTM cloud, not W2H local RTSP.
- **Bind:** 127.0.0.1:8558, `host_network: true`; no public video service.
- **Token:** persisted under private add-on `/data`.
- **Process monitoring:** proxy process automatically restarts on exit with a configurable delay.
- **Logging:** raw dependency error messages suppressed because they can contain session tokens.
- **Scope:** one BC1 camera per add-on instance. One camera's live feed has been verified from the Pi add-on through go2rtc; Lovelace has also been verified using the previous MacBook proxy.
- **Limitations:** Pi install, first-login, token persistence and go2rtc live picture **verified 2026-10-11**. Pi-only Lovelace view, boot recovery, multi-hour uptime, token renewal, second-camera support and battery impact remain unverified. No interactive MFA login or audio in the verified video pipeline.

This add-on is a **working initial Pi proof of concept**, not a production-ready integration.

## Prebuilt container image (v0.1.2, installed successfully on Pi)

The GitHub Actions job **successfully built and published** `ghcr.io/artepe/ezviz-bc1-w2h:0.1.2` for linux/arm64. The add-on's `config.yaml` points to this image, avoiding the Pi's Alpine `apk` networking failure.

**Important:** GitHub Container Registry packages may start **Private**, even when this code repository is Public. To allow Home Assistant OS to pull the image, open **GitHub → your profile → Packages → ezviz-bc1-w2h → Package settings → Change visibility → Public**. This publishes the compiled image, **not** your EZVIZ account information.

Run `ha store reload` and check `version_latest: 0.1.2` before installing. If the image pull fails with access denied, check the GHCR package visibility. If it fails for DNS/connectivity, inspect the Supervisor logs.
