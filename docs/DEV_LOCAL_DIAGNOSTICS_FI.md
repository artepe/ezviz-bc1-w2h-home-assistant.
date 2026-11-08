# W2H local_only — tutkimustulos ja DEV 0.3.3 -asennusvalmistelu

Tarkistettu 2026-11-08. Tämä tiedosto korvaa aikaisemman tutkimusmuistion.

## Käynnissä olevasta asennuksesta varmennettu

Supervisorin lisäosan `local_ezviz_bc1_w2h_dev` info vastasi: asennettu
versio 0.3.2, tarjottu versio 0.3.2, tila started, connection_mode local_only.
Kaksi vanhaa kamera-asetuspaikkaa on täytetty. Se ei ole W2H:n kanavakartta.

Tutkimusympäristö on core-ssh. Siinä ei ole Docker-socketia eikä pääsyä
EZVIZ-kontin /app- ja /data-hakemistoihin. Käyttöliittymän suorat lukupyynnöt
palauttivat 403:n. Pääsyrajoituksia ei muutettu.
W2H:n 9010 ja 9020 hyväksyivät yksittäisen TCP-yhteyden core-ssh:sta
kahden sekunnin aikarajalla; sovellusdataa ei lähetetty.

Näin ollen seuraavat ovat edelleen **UNKNOWN** kummallekin kameralle:

- /data/local_camera_1.json ja /data/local_camera_2.json olemassaolo ja validointi
  EZVIZ-kontissa;
- SDK:n oma yhteys W2H:hon, hyväksytty preview ja CAS-tunnistautuminen;
- todellinen kamerakanava W2H:ssa;
- vastaanotetut SDK-mediakehykset, MPEG-TS ja dekoodattava H.264-video.

Aikaisempi HTTP 503 ei yksin ratkaise mitään näistä. Vanha toteutus nielaisi
validointivirheet, hävitti SDK:n stderrin ja palautti saman 503:n myös
300 sekunnin uudelleenyritysodotuksen aikana.

## Valmistellun 0.3.3:n toiminta

Sama DEV-slug, image-repository, kamerat ja portit säilyvät. Manifestin versio
on 0.3.3. Lähdekoodia ei ole julkaistu eikä asennettu.

Open Web UI:n kamerakohtaiset tiedot luetaan lisäosan omassa prosessissa:

- tunnistetiedoston odotettu polku, olemassaolo (Yes / No / Unknown);
- rakenteellinen validointi (FORMAT_VALID tai turvallinen virhekoodi);
- viimeisen stream-yrityksen virhekoodi ja jäljellä oleva odotusaika;
- erikseen TCP connected, Preview accepted, Stream setup response,
  SDK media frame received ja MPEG-TS received.

UI:n automaattinen tilapäivitys ei aloita streamia tai hae pilviavaimia.
Vaihehavainnot koskevat viimeisintä yritystä; Not confirmed ei tarkoita
vahvistettua hylkäystä. Proxy restart nollaa prosessin muistitiedot.
Käynnissä olevan katselun myöhempi katkeaminen ei muuta ensimmäisen
käynnistysikkunan havaintoja.

Tiedostovalidointi tarkistaa tavallisen tiedoston, oikeudet (ei ryhmän/muiden
lukuoikeutta), enimmäiskoon, JSON-rakenteen, kameratunnuksen, yksityisen
IPv4-kohteen, portit 9010/9020, CAS-kenttien olemassaolon ja kanavan 1..256.
Symlinkit hylätään myös avaushetkellä. FIFO ei saa pysäyttää UI-päivitystä.
FORMAT_VALID ei varmista CAS-avaimen aitoutta, AES-muotoa tai voimassaoloa
eikä kanavan olemassaoloa laitteessa. SDK:n todettu AES-muotovirhe luokitellaan
INVALID_CREDENTIALS-koodiksi.

| Koodi | Vaadittu havainto |
| --- | --- |
| MISSING_CREDENTIALS | Tiedostoa ei löydy lukuhetkellä. |
| INVALID_CREDENTIALS | Tiedosto ei läpäise validointia tai SDK vahvistaa virheellisen AES-avaimen muodon. |
| LAN_CONNECT_FAILED | Sallitun W2H-kohteen TCP connect epäonnistui. Yleinen SDK-aikakatkaisu ei riitä. |
| CAS_AUTH_FAILED | Varattu dokumentoidulle yksiselitteiselle CAS-hylkäykselle. Nykyinen adapteri ei tuota tätä: tuntemattomia Result-arvoja ei tulkita. |
| CHANNEL_INVALID | Paikallinen kanavamääritys ei ole kokonaisluku 1..256. Ei väitettä laitteen kanavakartasta. |
| MEDIA_TIMEOUT | Hyväksytty preview (Result=0 ja kelvollinen Session), stream setup -vastaus ja käynnistysajan umpeutuminen ilman SDK-mediakehystä. |
| MPEGTS_INVALID | Stdout-dataa saapui, mutta kaksi täydellistä TS-pakettia ja 188 tavun synkronointi puuttuvat. |
| UNKNOWN | Muu virhe tai riittämätön näyttö, esimerkiksi puuttuva Session, yleinen SDK-virhe tai tyhjä stdout ilman vaihehavaintoja. |

CAS_AUTH_FAILED ei siis ole uusi nimi puuttuvalle Sessionille. Samoin
MEDIA_TIMEOUT ei ole uusi nimi mille tahansa tyhjälle stdoutille.

Prosessikohtaiset SDK-hookit on tarkistettu Dockerfilen lukitsemaa lähdettä
`a38ba757a3686cb412cc5029225e2608cdbccc4b` vasten. Ne tarkkailevat
send_encrypted_command- ja read_stream_frame_after_prefix-kutsuja muuttamatta
protokollapyyntöjä. Preview accepted vaatii 0x2012-vastauksen, Result=0:n ja
positiivisen numeerisen Sessionin. Stream setup response tarkoittaa
0x3106-vastausta 0x3105-pyyntöön. Session-arvoa ei tallenneta diagnostiikkaan.
Mediakehys voi sisältää muuta kuin videota: sen saapuminen ei todista videon
dekoodautumista eikä erillistä CAS-protokollatulosta.

Lapsiprosessin diagnostiikka kulkee nimettömän väliaikaistiedoston perityn
file descriptorin kautta. Kukin sallittu tapahtuma kirjoitetaan vain kerran;
vanhemman lukema on rajattu 4096 tavuun. Vain kiinteät tapahtumanimet ja
booleaanit viedään käyttöliittymään. SDK:n stderr ja salaisuudet eivät päädy
HTTP-vastaukseen. MPEG-TS-data kulkee edelleen omassa stdout-kanavassaan.

## Testaus ja toimitus

- 34 DEV-yksikkötestiä: tiedostojen ja kamerakohtaisten tulosten erottelu,
  symlinkit, virheiden luokittelu, epäselvän tuloksen UNKNOWN,
  pilvifallbackin esto, cooldown, SDK-hookit ja niiden palautus,
  katkelmallinen TS, yksityinen rajattu diagnostiikkakanava sekä oikean
  lapsiprosessin synteettinen TS ja erilliset vaihehavainnot.
- 74 perustestiä tavalliselle lisäosalle; lisäksi perustestit DEV-valinnalla.
- Python compileall ja git diff --check.
- Ei rakennettua imagea, Docker-smoketestiä, selaintestiä tai laitteiston
  videovarmennusta tässä ympäristössä. JavaScriptin renderöinti on tarkastettu
  lähdekoodista.

Asennukseen tarvitaan tämän lähteen 0.3.3-imagen rakennus ja julkaisu olemassa
olevalla DEV-workflowlla sekä saman DEV-lisäosan päivitys siihen. Pelkkä
config.yaml-version muutos ei toimita uutta koodia valmiiksi rakennetun imagen
sisälle. Tässä työssä ei käynnistetty workflowta tai päivitystä.

Päivityksen jälkeen varmista Supervisorin versio sekä imagen /app-tiedostojen
vastaavuus. Avaa Open Web UI ja lue ensin molempien tiedostojen tulokset.
Aja Test video kerran kameralle, odota tulos ja lue vaihehavainnot. Testaa
kamerat peräkkäin; älä käynnistä toista katselijaa samaan aikaan äläkä ohita
odotusaikaa. Näiden havaintojen perusteella voidaan paikantaa ensimmäinen
vahvistettu este. Älä tulosta tunnistetiedostoja tai SDK:n raakalokeja.

Pilviyhteyksiä, go2rtc-konfiguraatiota tai HAOSin tilaa ei muutettu.
