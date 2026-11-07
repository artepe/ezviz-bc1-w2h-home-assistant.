# EZVIZ BC1 / W2H DEV 0.3.2 — paikallinen video ja äänen testaus

Tämä ohje koskee **DEV-lisäosaa** (`ezviz_bc1_w2h_dev`), ei vanhaa Cloud Proxy
(TEST) -lisäosaa. Se ei vaadi Home Assistant OS:n uudelleenkäynnistystä.

## Tilanne ja rajaukset

- **EZVIZ cloud**: pilvipalvelu avaa kamerayhteyden; paikallinen go2rtc
  toimii vain videovirran jatkovälittäjänä. Tämä ei ole pilvetön ratkaisu.
- **Local only**: integraatio ei tee pilvikirjautumista eikä käytä cloud-fallbackia.
  Se **vaatii** kamerakohtaisen paikallisen SDK:n tunnistetiedoston ja
  todetun W2H-kanavan. Näitä ei voi luoda pelkän laitteen PIN-koodin,
  sarjanumeron tai avoimien TCP-porttien perusteella.
- **LAN credentials: Missing or invalid**: tiedosto puuttuu tai sen rakenne,
  oikeudet, kameratunnus, kanava tai W2H-osoite on virheellinen.
- **LAN credentials: File format valid (video not verified)**: pelkkä
  tiedostomuoto läpäisee tarkistuksen. Se **ei** takaa CAS-valtuutusta,
  toimivaa dekoodausta eikä sitä, että kamerakuva tulee.

DEV:n nykyiset paikalliset tunnistetiedostot ovat lisäosan omassa
`/data/local_camera_1.json` ja `/data/local_camera_2.json` -hakemistossa.
Niitä ei kopioida GitHubiin, kuvakaappauksiin tai julkisiin lokeihin.
`local_only`-valinta ei hae tunnisteita pilvestä eikä muuta kameran
ohjelmistoa. W2H BC1:n itsenäistä offline-toimintaa ei ole vahvistettu.

## Testi A: ääni jo toimivalla pilvivirralla

1. Säilytä toimiva `connection_mode: cloud` ja vanhat
   `ezviz_bc1` / `ezviz_bc1_2` go2rtc-virrat.
2. Sulje muut EZVIZ- ja go2rtc-katselijat. Avaa DEV:n **Open Web UI**.
3. Suorita **Test audio** kameralle 1 ja kameralle 2 yksi kerrallaan.
4. Tulkitse testin tulos:
   - *Audio track received ... audio packets received*: ääntä sisältäviä
     paketteja demultipleksoitiin; kuuluvuutta ja selaintoistoa ei todistettu.
   - *Audio track advertised ... no audio packets*: raita löytyi, mutta
     yhtään audiopakettia ei havaittu; tulos ei riitä äänen vahvistamiseen.
   - *No audio track detected*: testin lähde tuotti pelkkää videota.
   - *Timed out* / *Could not inspect*: testi ei vahvistanut lähdettä.
5. Vain jos audiopaketteja saatiin, lisää **erillinen** testialias olemassa
   olevaan go2rtc:n `streams:`-osioon (älä korvaa toimivaa videovirtaa):

   ```yaml
   ezviz_bc1_audio_test:
     - "ffmpeg:http://127.0.0.1:8558/HUB_SERIAL-CAMERA_SERIAL.ts#video=copy#audio=aac"
   ```

   Korvaa paikkamerkit oikeilla kameratunnuksilla. Käytä toiselle kameralle
   porttia 8559 ja eri aliasnimeä. Testaa go2rtc:ssä yksi kamera kerrallaan.
6. Erillisessä WebRTC-kortissa aseta `url: ezviz_bc1_audio_test`,
   `media: video,audio`, `muted: true` ja poista mykistys toistossa.
   AAC-määritys ei luo puuttuvaa ääniraitaa eikä mahdollista kaksisuuntaista
   puhetta. Väärä ääniasetus ei saa rikkoa toimivaa videokorttia.

Valmiit testialias- ja korttiesimerkit:
[go2rtc](../examples/go2rtc-two-cameras-audio-test.yaml) ja
[Lovelace](../examples/lovelace-two-cameras-audio-test.yaml).

## Testi B: Local only turvallisesti

1. Varmista ensin, että **cloud**-tilassa molemmat kamerat toimivat, ja
   dokumentoi toimivat go2rtc-virrat.
2. DEV → **Configuration** → vaihda vain
   `connection_mode: local_only`; jätä sarjanumerot, portit ja muu
   konfiguraatio muuttumatta. Tallenna ja käynnistä **vain lisäosa**
   uudelleen.
3. Avaa DEV → **Open Web UI**. Tarkista kummankin kameran
   `LAN credentials` -rivi. `Missing or invalid` on odotettu tulos,
   jos oikeita paikallisia avaimia ei ole vielä hankittu; näin ei kannata
   toistaa videon avausta.
4. Jos tunnistetiedoston muoto on kunnossa, paina **Test video** ja sen
   jälkeen **Test audio**. Auki oleva 9010/9020-portti tai käynnistynyt
   proxy ei yksin vahvista videokuvaa eikä offline-toimintaa.
5. Vasta jos **uusi** paikallinen videoyhteys käynnistyy, estä **vain W2H:n
   internet-yhteys** reitittimeltä (säilytä LAN-yhteys Home Assistantiin).
   Sulje vanhat katselijat, avaa molemmat virrat uudelleen ja varmista
   toistuva videon sekä mahdollisen äänen toiminta.
6. Jos testi epäonnistuu, salli W2H:n WAN-liikenne uudelleen, palauta
   `connection_mode: cloud` ja käynnistä vain DEV-lisäosa uudelleen.

Älä avaa W2H-portteja internetiin, poista kameroiden tunnistautumista,
kokeile satunnaisia salausavaimia tai tee firmware-muutoksia tätä testiä
varten. Virhekoodit 1052170 ja 20002 eivät yksin todista laite- tai
verkkovikaa; niissä on voinut olla kyse eri tunnus-/media-avainkyselyistä.

## Tietoturva ja vianmääritys

- Älä jaa `ha apps info --raw-json` -tulostetta: se voi sisältää
  `password`-asetuksen, istuntotokenin tai muita yksityisiä arvoja.
- Käytä ensisijaisesti **Open Web UI**:n testitulosta ja
  `ha apps logs local_ezviz_bc1_w2h_dev` -lokin salaisuuksista
  puhdistettuja rivejä.
- Kameran salauskoodi, EZVIZ-tilin 2FA-koodi ja SDK:n media-avain ovat
  eri asioita; mitään niistä ei pidä merkitä automaattisesti toisen
  korvikkeeksi.
- Korjausta ei edellytä Home Assistantin uudelleenkäynnistys, DNS:n
  vaihtaminen tai go2rtc:n toimivan videovirran poistaminen.

**Varmennustaso:** DEV:n pilvivideo on toiminut Raspberry Pi 5:llä;
täysin itsenäistä paikallista BC1/W2H-videota eikä ääntä ole vielä
todistettu toimivaksi tällä kokoonpanolla.
