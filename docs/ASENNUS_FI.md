# EZVIZ BC1 + W2H – asennus Home Assistantiin

> **Päivitys 11.10.2026:** EZVIZ BC1 + W2H -kameran livekuva **toimii nyt Raspberry Pi 5:llä ilman MacBookin videopalvelinta**. GitHub Actionsissa rakennettu Home Assistant -lisäosa v0.1.2 asennettiin Pi 5:lle, EZVIZ-kirjautuminen ja istuntotunnisteen tallennus onnistuivat, ja kuva näkyi sekä go2rtc:n live-soittimessa **että Home Assistantin Lovelace-valvomokortissa**. **Ensisijainen asennus:** [Raspberry Pi 5 -lisäosan ohje](../ezviz_bc1_w2h/DOCS.md). Alla oleva MacBook-ohje jää varavaihtoehdoksi.


## Mitä tämä tekee?

**EZVIZ BC1** -akkukamera on yhdistetty **EZVIZ W2H** -tukiasemaan. Kameran oman RTSP/ONVIF-portin puuttuminen ei estä tätä ratkaisua, koska video haetaan **EZVIZin pilvestä** käyttäjän omalla luvallisella kirjautumisella.

**Ensisijainen toimiva Pi-ketju:**

`BC1 → W2H → EZVIZ cloud → pyEzvizApi (Raspberry Pi 5:n HA-lisäosa) → 127.0.0.1:8558 → go2rtc → WebRTC-kortti`

**Vanha, myös todistettu vaihtoehto:** `BC1 → W2H → EZVIZ cloud → pyEzvizApi (MacBook) → go2rtc Pi:llä → WebRTC-kortti`. MacBook tarvitsee olla käynnissä vain jos valitset Mac-välityksen. Pi-videon **go2rtc- ja Lovelace-kuva on todettu toimivaksi**. Pitkäaikainen toiminta ja uudelleenkäynnistyksestä palautuminen ovat vielä testaamatta.

## Vanhat MacBook-ohjeet (varayhteys)

### 1. Asenna pyEzvizApi MacBookiin

Asenna ensin Homebrew (https://brew.sh) ja sitten:

```bash
brew install python@3.12 ffmpeg git
mkdir -p ~/ezviz-lab
cd ~/ezviz-lab
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv-video
source .venv-video/bin/activate
python -m pip install --upgrade pip
python -m pip install --upgrade 'git+https://github.com/RenierM26/pyEzvizApi.git'
```

Kirjaudu EZVIZiin **omilla** tunnuksillasi ja tallenna yksityinen token-tiedosto (`--save-token`). Toteutustapa riippuu käyttämästäsi CLI-versiosta; tarkista `pyezvizapi --help`.

```bash
umask 077
read -r 'EZ_USER?EZVIZ-sähköposti: '
read -rs 'EZ_PASS?EZVIZ-salasana: '; echo
pyezvizapi -u "$EZ_USER" -p "$EZ_PASS" --save-token devices status
unset EZ_USER EZ_PASS
```

Kehote pitää salasanan pois komentohistoriasta. Ohjelman käynnistysargumentti voi silti näkyä saman laitteen muille paikallisille prosesseille. Älä koskaan julkaise tokenia, salasanaa tai laitteen vahvistuskoodia.

Varmista laiteluettelosta BC1:n **alakameran tunnus**, joka voi olla muotoa `W2H-SERIAL-BC1-SERIAL`. Pelkkä W2H:n sarjanumero ei välttämättä kohdistu oikeaan kameraan.

### 2. Käynnistä livevideopalvelin MacBookilla

Selvitä MacBookin paikallinen IP:

```bash
ipconfig getifaddr en0
```

Käynnistä:

```bash
cd ~/ezviz-lab
source .venv-video/bin/activate
pyezvizapi --token-file ezviz_token.json stream proxy \
  --serial 'OMA_W2H-OMA_BC1' \
  --listen-host 'OMA_MACBOOK_IP' \
  --listen-port 8558
```

Pidä Terminal auki. Osoite on nyt `http://OMA_MACBOOK_IP:8558/OMA_W2H-OMA_BC1.ts`.

**Älä avaa porttia 8558 internetiin!** HTTP-virta ei kysy omaa salasanaa.

### 3. Tarkista yhteys Home Assistantista

Avaa Home Assistantin Terminal-lisäosa ja testaa:

```bash
curl -sS --connect-timeout 5 --max-time 15 -o /tmp/bc1-test.ts \
  -w 'HTTP=%{http_code}, bytes=%{size_download}\n' \
  http://OMA_MACBOOK_IP:8558/OMA_W2H-OMA_BC1.ts
```

`HTTP 200` ja vastaanotetut tavut todistavat verkkoyhteyden; jatkuvan videovirran 15 sekunnin aikakatkaisu on normaalia.

### 4. Määritä go2rtc MacBookin lähteellä

Home Assistant → **Asetukset → Sovelluskauppa**: lisää lisäosarepo `https://github.com/AlexxIT/hassio-addons`, asenna vakaa **go2rtc**, käynnistä ja avaa Web UI. Valitse **config** ja lisää:

```yaml
streams:
  ezviz_bc1:
    - ffmpeg:http://OMA_MACBOOK_IP:8558/OMA_W2H-OMA_BC1.ts#video=copy
```

Tallenna. Go2rtc:n omalla pääsivulla klikkaa `ezviz_bc1 → stream`. Kun kuva näkyy, yhteys on kunnossa.

Älä lisää `#audio=copy`: tässä testissä AAC-äänen alkuotsakkeet aiheuttivat virheen `AAC with no global headers is currently not supported`. Videon kopioiminen sellaisenaan toimii.

### 5. Lisää kamera Lovelaceen

HACS: etsi **WebRTC** (tekijä AlexxIT; repo `https://github.com/AlexxIT/WebRTC`), asenna ja käynnistä Home Assistant uudelleen. Lisää **WebRTC** kohdassa **Asetukset → Laitteet ja palvelut**. Osoitteeksi `http://localhost:1984` siinä kokoonpanossa, jossa go2rtc on Home Assistantin samassa palvelinympäristössä.

Lisää manuaalinen Lovelace-kortti:

```yaml
type: custom:webrtc-camera
url: ezviz_bc1
mode: mse
media: video
ui: true
title: EZVIZ BC1 – Live
```

Tämän videokortin toiminta on todettu toimivaksi oikealla BC1:n livekuvalla. **Generic Camera** antoi tässä kokoonpanossa aikakatkaisun, vaikka go2rtc:n oma katselu onnistui.

## Jos et saa kuvaa

Katso [vianhaku](TROUBLESHOOTING.md). Varmista MacBookin oma Terminal, palvelimen IP/portti, salausavaimen mahdolliset vaatimukset ja DNS. Pilvivideopalvelun täytyy olla saavutettavissa.

## Rajoitukset

- Tällainen toisto käyttää EZVIZ-pilveä. Ei ole offline-RTSP-ratkaisu.
- Akkukameran jatkuva katselu kuluttaa akkua.
- Videon ääntä ei ole mukana testatussa go2rtc-kortissa.
- Ensimmäinen BC1 testattu; toisen kameran pysyvää liveasetusta ei ole vielä todennettu.
- Raspberry Pi:hin itsenäisesti asennettu Python-videopalvelin on **toiminut käytännössä go2rtc:n livekuvan lähteenä 11.10.2026**. Vielä testaamatta: pitkäaikainen vakaus, kameran herätys, ääni sekä käynnistyksen ja tokenin palautuminen.
- **Valmis Raspberry Pi:n Lovelace-kortti:** [examples/lovelace-webrtc.yaml](../examples/lovelace-webrtc.yaml).
