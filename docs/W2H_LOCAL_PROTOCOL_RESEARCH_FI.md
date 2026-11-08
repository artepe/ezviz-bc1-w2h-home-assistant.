> DEV 0.3.4: ensisijainen tunnistetietojen haku ja tuonti tehdään nyt
> [Open Web UI:ssa](DEV_WEB_CREDENTIALS_FI.md). Alla olevat konttikomennot
> ovat aiemman tutkimuksen taustaa eivätkä uuden UI-polun vaatimus.

# W2H / BC1 paikallinen protokolla — 2026-11-08

## Tulos ja näytön rajat

Paikallinen H.264 ei ole vielä varmennettu. DEV-haara sisältää olemassa olevan
LAN-SDK-adapterin ja uuden offline-tuonnin kamerakohtaisille tunnistetiedoille.
MISSING_CREDENTIALS on lisäosan oma tiedostovirhe ennen verkkoyhteyttä,
ei W2H:n CAS-vastauskoodi. Sitä ei korjata portin tai salauksen arvauksella.

Tämän tutkimuskerran havainto: Pythonin socket.create_connection, 2 s aikaraja,
192.168.10.140:9010 ja :9020 hyväksyivät kumpikin yhden TCP-yhteyden.
Yhteydet suljettiin lähettämättä sovellusdataa. 192.168.10.231:22 palautti
ConnectionRefusedError. Tämä ei osoita muita HA-yhteystapoja mahdottomiksi.
Ei käytettävissä olevaa kirjautumista HA:han, W2H:n tunnistetietoja tai
nykyisen asennuksen tiedostoja. Tässä työssä ei muutettu HA:ta tai go2rtc:tä.

Rajattu tiedostohaku: projektihakemisto sekä /tmp ja /root enintään neljän
hakemistotason syvyydeltä; ei löytynyt analyysiin valittavaa EZVIZ-APK:ta,
SDK-binääriä tai PCAP-tiedostoa. Tämä ei tarkoita, ettei käyttäjällä ole niitä.

REA MCP 6.8.0 `binary_session({})`: ei avointa kohdetta; Ghidra ei määritetty,
JADX/JEB ja adb eivät käytettävissä. `inspect_pcap_client({})` palautti
capability_unavailable / unsupported_provider: tshark puuttuu, tarvitaan
Wireshark 4.x tshark ja capinfos. Binäärianalyysiä tai verkkokaappauksen
analyysiä ei siis suoritettu eikä niille ole Evidence ID:tä. Näitä rajoja ei
korvata lähdekoodin havainnoilla. REA ei itse kaappaa verkkoliikennettä.

## Vahvistettu SDK:n lähdekoodista, ei W2H:n liikenteestä

DEV Dockerfilen lukitus ja paikallisen puhtaan lähdepuun HEAD:
`a38ba757a3686cb412cc5029225e2608cdbccc4b`.
Lähteet:
[hcnetsdk.py](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/hcnetsdk.py),
[cas.py](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/cas.py),
[_local_stream.py](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/_local_stream.py),
[CLI](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/__main__.py).
SDK:n kommenttien mainitsemat APK-jäljitykset ovat upstreamin väitteitä;
niiden alkuperäistä ajonaikaista näyttöä ei tässä toistettu.

| Vaihe | Komento / vastaus | Lähdekoodin toiminta ja tulkinta |
| --- | --- | --- |
| Omistajan pilvi-istunto | CAS 0x2001 | cas_get_encryption lähettää TLS:n yli ClientID, Sign, DevSerial, ClientType; kohde tokenin service_urls.sysConf[15:17]. Ei sama kuin W2H:n 9010-yhteys. Vastaus-ID:tä ei tässä varmennettu. |
| CAS-tuplen luku | XML Response/Session | CasDeviceSession.from_response lukee @Key, @OperationCode, @EncryptType tai @Algorithm=AES128. Pelkkä XML Result ilman Sessionia ei riitä. |
| Valinnainen pre-start | 0x2013 / 0x2014 | Lähetetään vain, jos pre_start_body on annettu. DEV ei lähetä arvattua pre-start-runkoa. |
| Preview TCP 9010 | 0x2011 / 0x2012 | OperationCode, Channel, ReceiverInfo, IsEncrypt, ReceiverInfoEx, Authentication; muitakin valinnaisia kenttiä. Vastaus sisältää Sessionin. DEV hyväksyntähavainto vaatii Result=0 ja positiivisen 31-bittisen Sessionin. |
| Media TCP 9020 | 0x3105 / 0x3106 | Lähetetään preview-vastauksen Session sekä Rate=0, Mode=0. Vastaus-ID yksin ei todista onnistunutta CAS-tunnistusta tai videota. |
| Media | `$`-kehystetty RTP | SDK erottaa RTP:n MPEG-PS-kuorman, FFmpeg remuxaa MPEG-TS:ksi. Vastaanotettu kehys tai TS-synkronointi ei yksin todista H.264-dekoodausta. |
| Oman preview-istunnon lopetus | 0x2013 / 0x2014 | OperationCode ja juuri tämän asiakkaan hyväksytystä previewsta saatu Session; ei wildcard-lopetusta. |

CAS 0x2005 (verify) ja 0x300f (device message) esiintyvät CAS-moduulin muissa
toiminnoissa; ei näyttöä, että ne kuuluisivat W2H:n paikallisen videon avaukseen.
W2H:n virhekooditaulukkoa ei tunneta. Tuntematonta Result-arvoa tai puuttuvaa
Sessionia ei merkitä CAS_AUTH_FAILED-koodiksi. Ylävirran laitekohtaiset
virhekoodit eivät ole ilman mittausta BC1/W2H:n koodeja.

Paikallinen SDK-kehys on 32 tavun otsake, AES-128-CBC/PKCS#5-salattu XML ja
32 ASCII-merkin MD5(ciphertext)-häntä. Monitavuiset otsakekentät ovat big endian:
magic 0..3, version 4..7, sequence 8..11, marker 12..15, varattu 16..17,
command 18..19, status 20..23, salatun rungon pituus 24..27, reserved 28..31.
Status ja XML Result ovat eri kenttiä. Pyynnön status-oletus 0xffffffff ei ole
onnistumisen vastauskoodi. Otsake ei sisällä traileria rungon pituudessa.
SDK käyttää paikallisille ohjauskehyksille app-muotoista IV:tä, ei vanhan
CAS-helperin serial+operationCode-IV:tä. Tuontityökalu ei generoi avaimia/IV:itä.
App-muodossa SDK sitoo 9010-ohjausyhteyden lähdeportin ReceiverInfo.Portiin.

## Mistä omat tunnistetiedot ja kanavat saadaan

1. Ensisijainen lähdekoodin osoittama reitti on omistajan tavallinen EZVIZ-login
   ja `stream local-sdk-keys --serial ...`. Se hakee get_device_infos-tiedoista
   endpointin, rekisteröi P2P-istunnon oletuksena, hakee CAS-tuplen ja erikseen
   median avaimen get_cam_key-kutsulla. MFA voi olla tarpeen. Tämä alkuvalmistelu
   käyttää pilveä; se ei todista avainten pysyvyyttä tai mahdollisuutta uusia
   niitä pelkän LANin kautta. `--no-media-key` jättää median avaimen hakematta.
2. Valtuutettu vaihtoehto on omasta sovelluksesta/SDK:sta jo saatavilla oleva
   vastaava vienti tai omasta hyväksytystä istunnosta kerätty runtime-näyttö.
   APK:n staattinen analyysi kertoo kutsuketjun, ei tuota laitteen salaisia
   avaimia. TLS-kaappaus ei sellaisenaan paljasta CAS-tuplen sisältöä.
3. `--cas-serial` on erillinen pilvihaun kohde. Älä oleta, että hubin sarjanumero,
   kameran sarjanumero ja yhdistelmämuoto ovat vaihdettavissa. Selvitä todellinen
   DevSerial omistajan sovelluksen pyynnöstä tai laitemetadatasta. Jos CAS hylkää
   pyynnön, älä kokeile arvattuja avainpareja tai kierrä tunnistautumista.
4. `local-sdk-keys` EI palauta kanavakarttaa. Sen JSON sisältää serial,
   endpoint, cas ja mahdollisen media_key/media_key_hex. SDK:n channel=1 on
   oletus, ei laitteesta havaittu arvo. Selvitä kummankin kameran Channel
   hyväksytystä 0x2011-pyynnöstä omassa sovelluksessa tai omistajan saamasta
   eksplisiittisestä kanavametadatasta. Lisäosan paikka 1/2 tai sarjanumeron
   loppuosa ei osoita kanavaa. Ei automaattista kanavien läpikäyntiä.

| Lisäosan kamera | CAS-haun DevSerial | Preview Channel |
| --- | --- | --- |
| HUB_SERIAL-CAMERA_ONE | UNKNOWN | UNKNOWN |
| HUB_SERIAL-CAMERA_TWO | UNKNOWN | UNKNOWN |

Varmennuskoodi laitteen tarrassa, tilin salasana, pilvitoken, CAS-ohjausavain
ja median purkuavain ovat eri asioita. Älä sijoita yhtä toisen tilalle.

## Testattava DEV-tuonti ja rajattu LAN-testi

Suorita valtuutetussa ympäristössä, jossa on Dockerfilen lukitsema SDK ja
omistajan toimiva, suojattu token. Älä käytä debug-lokitusta. Tallenna erikseen
kummankin kameran vienti, älä tulosta sitä terminaaliin tai GitHubiin:

```sh
umask 077
pyezvizapi --token-file /private/owner-token.json stream local-sdk-keys \
  --serial HUB_SERIAL-CAMERA_ONE > /private/camera-one-export.json
```

Komennon toimivuus tällä yhdistelmäsarjanumerolla on vielä testaamatta. Käytä
`--cas-serial`-valitsinta vain havaitun DevSerialin perusteella. Varmista viennin
endpoint omasta laitteesta: W2H 192.168.10.140, command_port 9010, stream_port
9020. Älä aja vientiä uudelleen jatkuvan katselun yhteydessä.

Siirrä suojattu vienti DEV-konttiin valtuutetulla tavalla. Kontin /data ei ole
core-ssh-lisäosan /data. Selvitä kanava ensin ja aseta CHANNEL havaittuun
kokonaislukuun. Alla muuttujan puuttuminen estää tuonnin:

```sh
/opt/ezviz-venv/bin/python /app/local_credentials.py \
  --source /private/camera-one-export.json \
  --serial HUB_SERIAL-CAMERA_ONE --channel "${CHANNEL:?set observed channel}" --slot 1
```

Toista toiselle kameralle sen omalla viennillä, serialilla ja havaitulla kanavalla,
slot 2. Työkalu ei hae mitään verkosta, ei muuta serialia, ei hyväksy ristiriitaista
viennin channel-kenttää eikä korvaa olemassa olevaa kohdetta. Tulos FORMAT_VALID
tarkoittaa vain rakennetta ja avaimen pituutta, ei oikeaa avainta tai kanavaa.
Tiedosto julkaistaan atomisesti oikeuksilla 0600. Älä jaa vientiä tai /data-tiedostoja.

Yksittäinen rajattu LAN-testi DEV-kontissa, peräkkäin kameroille:

```sh
umask 077
/opt/ezviz-venv/bin/python /app/local_capture.py \
  /data/local_camera_1.json HUB_SERIAL-CAMERA_ONE 20 > /data/local-one.ts
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height \
  -of json /data/local-one.ts
ffmpeg -v error -i /data/local-one.ts -map 0:v:0 -frames:v 1 -f null -
```

Tyhjä/rikkinäinen tiedosto ei ole onnistunut testi. Varmennukseen tarvitaan
ffprobe codec_name=h264 ja onnistunut kuvan dekoodaus. Nykyinen local_capture
ei kytke median erillistä purkua päälle, vaikka vienti sisältäisi media_keyn.
Jos media on salattu, SDK:n rajattu `local-sdk-dump --decrypt-video` tarvitsee
oikean staattisen media_keyn sekä havaitun decrypt-codec-muodon. Tätä ei valita
automaattisesti, eikä CAS-avain yksin lupaa selväkielistä videota.

## Verkkoliikenteen vertailu ja jatkovarmennus

Kaappaa omistajan valtuuttamassa LANissa W2H:n 9010/9020-liikenne erikseen
kummankin kameran EZVIZ-live-katselusta. Tarvitaan oikea havaintopiste: HA:n
verkkoliitäntä ei tavallisesti näe puhelimen unicast-liikennettä tukiasemalle.
Esimerkiksi hallittu peilausportti tai puhelimen oma kaappaus. Rajattu suodatin:
`host 192.168.10.140 and (tcp port 9010 or tcp port 9020)`.
Pidä kaappaus yksityisenä; salattu kuormakin sisältää yksityistä istuntotietoa.

Kun tiedosto ja työkalut ovat käytettävissä: REA inspect_pcap_capture summary
säilyttää identiteetin/SHA-256:n; inspect_packet_capture ja inspect_packet_fields
auttavat valituissa kentissä. TCP on tavujono: reassemblai kehykset, älä tulkitse
yksittäistä pakettia kokonaiseksi komennoksi. Vertaa otsakkeen command/sequence,
portit, pituudet, 0x2012:n Result ja Sessionin olemassaolo sekä saman istunnon
0x3105/0x3106 ja median alku. Julkiseen raporttiin vain komentotunnukset,
numeeriset tuloskoodit ja boolean-havainnot; ei XML-runkoja, avaimia tai Sessionia.

APK/SDK-analyysiin käyttäjän toimittama laillinen tiedosto, hash ja versio;
REA:n paketti-inventaario ensin, sitten JADX/JEB:n avulla rajatut CAS-,
kanava- ja preview-kutsuketjut. Natiivikirjastolle soveltuva analyysimoottori.
Älä lataa satunnaista APK:ta tai oleta eri mallin SDK-jälkeä W2H-näytöksi.

Pilviriippumattomuuden hyväksymiskoe vaatii uuden LAN-istunnon WAN estettynä
vain W2H:lta ja DEV-testiprosessilta, sekä testit idle-jakson ja tukiaseman
uudelleenkäynnistyksen jälkeen. Tee tämä erillisessä ylläpitoikkunassa: W2H:n
WAN-esto katkaisee myös toimivat pilvireitit. Tässä työssä WAN-estoa ei tehty.
DEV:n Python-socket-rajoitus sallii vain annetun hubin 9010/9020; se ei ole
koko tukiaseman tai konttiverkon palomuuri.

Tutkimuskysymysten tila: SDK:n vaiheet **vastattu lähdekoodista**;
W2H:n todellinen CAS/kanavakartta ja vastauskoodit **avoin**;
LAN H.264 ja pitkäaikainen pilvettömyys **avoin**; laillinen vientireitti
**tunnistettu lähteestä, laitteistolla testaamatta**. Stable-lisäosan,
pilvireittien ja go2rtc:n konfiguraatio säilyvät ennallaan.
