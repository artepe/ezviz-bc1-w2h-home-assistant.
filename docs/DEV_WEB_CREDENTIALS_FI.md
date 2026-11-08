# DEV 0.3.4: paikalliset tunnistetiedot Open Web UI:n kautta

Tämä on DEV-korjaushaaran käyttöönottoreitti. Pilvistreamin toteutukseen,
stable-lisäosaan, go2rtc-asetuksiin tai olemassa oleviin pilvitokeneihin ei tehdä
muutoksia. Käyttö tapahtuu Home Assistantin suojatun ingressin kautta.

## Käyttö

1. Odota GitHubin **Build and publish EZVIZ DEV images** -ajon onnistumista
   korjaushaaralle `codex/dev-web-local-credentials`. Manifesti pyytää imagea
   `ghcr.io/artepe/ezviz-bc1-w2h:0.3.4`; pelkkä lähdekoodin versio ei osoita,
   että image on julkaistu. Asennusvalmius riippuu ajon tuloksesta.
2. Nykyinen asennus on Supervisorin mukaan `local_ezviz_bc1_w2h_dev` 0.3.3
   paikallisesta repositoriosta. GitHub-haara ei päivitä sen paikallista
   lähdehakemistoa. Ilman HAOS-isäntää käytä Home Assistantin
   **Asetukset → Lisäosat → Lisäosakauppa → Repositories** -valintaa ja lisää:
   `https://github.com/artepe/ezviz-bc1-w2h-home-assistant.#codex/dev-web-local-credentials`.
   [Home Assistantin virallinen haararepositorio-ohje](https://contributors.home-assistant.io/apps/guides/repository/).
   Asenna tämän repositorion **EZVIZ BC1 / W2H DEV - Local or Cloud** 0.3.4.
   Se on eri asennus ja sillä on oma datahakemisto; vanhat kamerat ja
   tunnistetiedostot eivät siirry automaattisesti. Älä poista vanhaa DEV:iä.
   Pysäytä vanha DEV sen omalla UI-painikkeella ennen uuden DEV:n käynnistystä,
   koska DEV:t käyttävät samoja portteja. Säilytä toimiva pilvilisäosa ennallaan;
   jos sen portit ovat samat, älä käynnistä rinnakkaista DEV:iä niiden päälle.
   Tarkista uuden Open Web UI:n versio 0.3.4 ja lisää kamerat siellä uudelleen.
3. Valitse DEV:ssä **Local only** ja avaa kameran **Local credentials**.
4. Anna **Observed W2H camera channel** havaittuna kokonaislukuna 1..256.
   Kamera-asetuspaikka, sarjanumeron loppuosa ja SDK:n oletus 1 eivät ole näyttöä
   kanavasta. Jos kanava on tuntematon, älä arvaa sitä.
5. Valitse jompikumpi tapa:
   - **Import private SDK JSON:** valitse omistajan valtuutetussa ympäristössä
     saama pyEzvizApi `local-sdk-keys` -vientitiedosto. JSONin serial-tunnuksen
     on vastattava UI:n koko kameratunnusta. Pakolliset kentät ovat `serial`,
     `endpoint.host`, `cas.key` ja `cas.operation_code`. Portit ovat 9010/9020;
     jos ne puuttuvat, käytetään näitä SDK-oletuksia. Mahdollinen viennin
     `channel` ei saa olla ristiriidassa annetun kanavan kanssa.
   - **Fetch from EZVIZ:** valitse tilin API-alue, anna tilin tunnus ja salasana,
     tarvittaessa vahvistuskoodi. Salli erikseen kertaluonteinen pilvikirjautuminen,
     P2P-rekisteröinti ja CAS-haku. CAS serial -ohitus on vapaaehtoinen ja vaatii
     havaittua laitetietoa; tyhjänä SDK käyttää kameran koko tunnusta. Älä kokeile
     eri sarjanumeroita arvaamalla. Haku päättyy viimeistään 60 sekunnissa.
6. **Replace existing credentials** tarvitaan vain olemassa olevan tiedoston
   korvaamiseen. Virheellinen tuonti ei korvaa aiempaa tiedostoa. Kukin kamera
   tallentuu oman porttinsa mukaiseen DEV:n /data-paikkaan oikeuksilla 0600.
7. Tallennus ilmoittaa vain **FORMAT_VALID**. Valitse tarvittaessa **Restart
   proxy**, odota käynnistys ja aja **Test video** kerran. Tarkista kamerakuvan
   näkyminen soittimessa. TCP-yhteys, Session tai TS-paketti ei yksin osoita
   dekoodattavaa videota. Testaa kamerat peräkkäin, ilman muita katselijoita.

Jos EZVIZ vaatii vahvistuksen, syötä saamasi koodi ja salasana uudelleen.
MFA:ta ei ohiteta. Jos LAN-metatieto, P2P-rekisteröinti tai CAS-haku epäonnistuu,
UI näyttää kiinteän virheilmoituksen eikä julkaise osittaista tunnistetiedostoa.
Valtuutettu tiedostotuonti toimii myös ilman pilviyhteyttä.

## Tutkimustulos ja rajat

Dockerfilen lukittu pyEzvizApi-commit on
`a38ba757a3686cb412cc5029225e2608cdbccc4b`. Sen
[get_local_sdk_stream_credentials_from_client](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/_local_stream.py#L2003)
hakee omistajan kirjautumisella CONNECTION/LAN-metatiedon, rekisteröi P2P-istunnon
ja kutsuu CAS `cas_get_encryption` -hakua valitulle sarjanumerolle.
SDK:n [CLI local-sdk-keys](https://github.com/RenierM26/pyEzvizApi/blob/a38ba757a3686cb412cc5029225e2608cdbccc4b/pyezvizapi/__main__.py#L4352)
antaa saman vientimuodon. UI käyttää SDK-funktiota omassa rajatussa prosessissa.
Se ei lue, päivitä, tallenna tai poista käytössä olevia pilvitoken-tiedostoja.
Tilipalvelun mahdollisia muiden istuntojen rajoja ei ole testattu laitteistolla.

Haku ei anna W2H:n kamerakanavaa. Todellinen BC1/W2H:n CAS DevSerial -valinta,
kanavakartta, avainten kelpoisuus ja paikallinen videovirta ovat yhä
laitteistolla varmentamatta. Haku voi epäonnistua, vaikka pilvivideo toimisi.
CAS AES-ohjausavain, operation code, laitteen tarran varmennuskoodi, tilin
salasana ja median purkuavain eivät ole keskenään vaihdettavia.

Paikallinen SDK-polku käyttää 9010/9020-portteja ja CAS-tuplaa: preview 0x2011
odottaa 0x2012-vastausta, Result=0 ja kelvollista Sessionia; stream setup on
0x3105/0x3106. Nämä ovat SDK-lähteestä selvitettyjä ehtoja, eivät tästä W2H:sta
vastaanotettuja onnistumisia. [Protokollatutkimus](W2H_LOCAL_PROTOCOL_RESEARCH_FI.md).

UI-haku ei hae median purkuavainta. Tuonnin mahdollinen media_key/media_key_hex
säilytetään, mutta nykyinen local_capture ei kytke median erillistä purkua päälle.
Salattu media voi siis jäädä lisäkehitystä vaativaksi esteeksi. Myös W2H:n
pitkäaikainen toiminta ilman WANia on varmentamatta. UI:n paikallistilan
kertaluonteinen, erikseen sallittu tunnistetietohaku ei muuta katselutilaa eikä
käynnistä pilvifallbackia. Automaattinen sivun päivitys ei tee tunnistetietohakuja.

Salasanat kulkevat lapsiprosessin stdin-putkessa, eivät komentorivillä. Käytetyt
tilitiedot eivät tallennu levylle. SDK:n lokitus on estetty ja stderr hylätään;
HTTP-vastauksissa ja tilatiedoissa ei palauteta avaimia, operointikoodeja,
tokeneita tai raakoja poikkeuksia. Selain tyhjentää salasanan ja vahvistuskoodin
pyynnön jälkeen ja lomakkeen suljettaessa. JSON-vientiä ei tallenneta selaimen
paikalliseen tallennustilaan. Älä liitä omaa vientiä GitHubiin tai keskusteluun.

Testit käyttävät vain synteettisiä tunnisteita: todellinen kirjautuminen,
W2H:n kanava/CAS-tulos ja videon vastaanotto on varmennettava erikseen.

## Automaattinen kanavahaku (DEV 0.3.5)

Local credentials → **Discover channel candidates** käyttää erillisellä
suostumuksella DEV:n olemassa olevaa `/data/ezviz_token.json`-istuntoa.
Se hakee pyEzvizApi:n `get_device_infos()`- ja `get_managed_device_ipcs()`-
metatiedot. Haku ei kirjaudu sisään, uusi istuntoa, hanki avaimia, rekisteröi
P2P:tä tai muuta katselutilaa. Puuttuva tai vanhentunut istunto ilmoitetaan.

[Virallinen Get device channel information](https://open.ys7.com/help/en/476)
on `POST /api/lapp/device/camera/list`, lomakekenttinä `accessToken` ja
`tukiaseman deviceSerial`. `ipcSerial` yksilöi kameran, `channelNo` on pilven
kanava. Consumer-istunnon `session_id` ei ole tämän rajapinnan `accessToken`.
Jos omistajalla on valtuutettu Open Platform -token, sen voi sijoittaa yksityisesti
DEV-kontin tiedostoon `/data/ezviz_open_token.json` muodossa
`{"accessToken":"<oma token>"}`, oikeuksin 0600. Valitse tokenin myöntänyt
Open Platform -palvelin lomakkeesta. Tokenia ei syötetä selaimeen eikä tallenneta
repositorioon. Ilman Open Platform -tokenia pyEzvizApi-metatietohaku toimii
olemassa olevalla consumer-istunnolla; virallista rajapintaa ei kutsuta väärällä
tokenilla.

Tunniste `tukiasema-kamera` yhdistetään täsmälliseen `ipcSerial`-kenttään ja
mahdolliseen `deviceSerial`-tukiasemaan, tai pyEzvizApi:n täyteen kameratunnukseen.
Metatiedon `channelNumber` on kanavamäärä eikä kanavakartta. Listajärjestys,
kameran numero tai SDK:n oletuskanava eivät ole näyttöä. Ristiriitaiset löydökset
näytetään kaikki ehdokkaina.

Pilven `channelNo`-arvon vastaavuutta paikallisen SDK:n `Channel`-arvoon ei ole
vahvistettu dokumentaatiolla tai näillä laitteilla. Siksi jokainen löydös on
**unverified SDK candidate**. Haku ei täytä tallennettavaa kanavaa eikä asenna
tunnistetietoja. Vahvista kanava erikseen paikallisella preview-vastauksella ja
kameran oikealla kuvalla ennen sen käyttöönottoa.

Tämän työympäristön tarkistuksessa 2026-11-08 ei löytynyt valtuutettua
EZVIZ-istuntoa. Kameroiden todellisia kanavia tai SDK-vastaavuutta ei siten
voitu mitata; niitä ei ole päätelty eikä esimerkkilukuja käytetty tuloksina.


## DEV 0.3.6: hankinnan virhevaiheet

Fetch from EZVIZ erottaa `lan_metadata` (exit 20), `p2p_registration`
(exit 21) ja `cas_lookup` (exit 22). CAS-vastauksen numeerinen `Result`
ja Session-kentän puuttuminen näytetään; HTTP-virheen status näytetään,
jos SDK antaa sen rakenteisena. Poikkeustekstejä ei tulosteta eikä niistä
poimita numeroita, koska ne voivat sisältää kokonaisia salaisia vastauksia.

Pinnattu SDK a38ba757 käyttää järjestystä get_device_infos →
register_p2p_session → cas_get_encryption → CasDeviceSession.from_response.
CAS-kutsun DevSerial on oletuksena valittu koko kameratunniste, myös silloin
kun se sisältää tukiaseman ja alikameran tunnisteen. Se ei automaattisesti
vaihdu W2H-tukiaseman sarjanumeroksi. UI näyttää lähteen `selected_camera`
tai `observed_override`, ei tunnisteen arvoa. Tukiaseman tunnistetta saa
käyttää vain havaitun, valtuutetun laitetiedon perusteella; automaattista
vaihtoehtojen kokeilua ei ole.

`Result=1052170` ilman Session-kenttää paikantaa epäonnistumisen CAS-haun
vastaukseen ennen paikallisen SDK-todennuksen aloittamista. Se ei yksin
osoita väärää DevSerial-tunnistetta, tilin oikeuspuutetta tai laitekohtaista
estoperustetta. Koodin tarkkaa merkitystä ja W2H/BC1-mäppäystä ei ole
vahvistettu. Uusi oikean laitteen ajo tarvitaan nykyisen estävän vaiheen
vahvistamiseksi. Muutokset eivät ota paikalliseen laitteeseen yhteyttä.

## DEV 0.3.7: tunnettu W2H LAN endpoint

Open Web UI → Local credentials → Fetch from EZVIZ: valitse erikseen
**Use known W2H LAN endpoint** ja hyväksy kertaluonteinen pilvikirjautuminen,
P2P-rekisteröinti sekä CAS-haku. Endpoint on kiinteä 192.168.10.140,
komentoportti 9010 ja stream-portti 9020. Valinta ei ole oletuksena käytössä.
Se ohittaa LAN-metatietohaun kokonaan; ulkoisia endpoint-osoitteita ei käytetä.

Ilman ohitusta `lan_metadata` erottaa `CAMERA_RECORD_MISSING`,
`CONNECTION_MISSING` (myös tyhjä CONNECTION), `LOCAL_IP_MISSING`,
`LAN_ENDPOINT_INVALID` ja `LAN_METADATA_REQUEST_FAILED`.
Aiempi exit 20 ei yksin todista, mikä näistä puuttui. Älä päättele sitä
vanhasta virheilmoituksesta: aja ilman ohitusta saadaksesi tarkan luokituksen.

Ohituksen jälkeen seuraava vaihe on `p2p_registration` (exit 21,
`P2P_REGISTRATION_FAILED`), sitten `cas_lookup` (exit 22,
`CAS_REQUEST_FAILED` tai `CAS_SESSION_INVALID`). Numeerinen CAS Result ja
HTTP-status näytetään, jos saatavilla; vastauksia, avaimia ja tokeneita ei tulosteta.

CAS-identiteetin evidenssi: lukitun SDK:n commit
`a38ba757a3686cb412cc5029225e2608cdbccc4b`,
`pyezvizapi/_local_stream.py:get_local_sdk_stream_credentials_from_client`
kutsuu `cas_get_encryption(cas_serial or serial)`.
`pyezvizapi/cas.py:cas_get_encryption` välittää annetun arvon DevSerialiksi.
SDK:n geneeriset CAM123-testit eivät varmista W2H:n/alilaitteen tunnistetta.
Tässä ei pilkota `G23915155-G28068598`-tunnistetta eikä kokeilla automaattisesti
sen osia. Oletus käyttää valittua kokonaista kameratunnistetta SDK:n mukaisesti;
Observed CAS serial -kenttään saa antaa vain erikseen havaitun arvon.
W2H:n vaatima DevSerial jää varmentamatta, kunnes saadaan laitekohtainen
CAS-vastaus tai valtuutetun asiakassovelluksen havainto.

Kameran 1 kanavaehdokas 1 ei ole paikallisesti varmennettu. Tunnistetietojen
onnistunut tallennus kertoo vain FORMAT_VALID-tilan. Todista autentikointi,
kanava ja streami vastaanottamalla video. Pilvivideon, token-tiedostojen ja
go2rtc:n toteutuksia ei muuteta tässä julkaisussa.
