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
