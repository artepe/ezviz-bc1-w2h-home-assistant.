# W2H Camera 1 – 2026-11-08

HTTP 503 UNKNOWN ei yksin osoita LAN-autentikoinnin hylkäystä. DEV 0.3.7
hukkaa SDK:n poikkeusten vaihe-eron. Paikallinen lähdekooditutkimus ja lukitun
SDK:n offline-regressio vahvistivat lisäksi toiminnallisen virheen: CLI:n
--encrypt-type-oletus 1 ohittaa CAS-bundlen encrypt_type-arvon. Synteettinen
arvo 3 välittyy korjauksella oikein. Todellisen bundlen arvoa ei luettu;
korjauksen ei väitetä yksin ratkaisevan tämän W2H:n 503:a.

## Mitatut laitetulokset

Yksi socket.create_connection(('192.168.10.140', 9010), timeout=3) onnistui
noin 0,01 sekunnissa tästä työympäristöstä. Yhteys suljettiin heti. Ei previewta,
ei portin 9020 testiä, ei mediaa. Tämä ei mittaa HAOS-kontin verkkoreittiä.

/data/local_camera_1.json ei ole tässä ympäristössä. Nimen mukainen tiedosto
ei löytynyt /tmp- eikä /opt-puusta. Tunnistetietoja ei haettu uudelleen.

| Kysymys | Havainto |
|---|---|
| SDK-prosessi nykyisellä tiedostolla | NOT_TESTED: tiedosto puuttuu tästä ympäristöstä |
| CAS-tiedoston luku | NOT_TESTED; käyttäjän HAOS:ssa FORMAT_VALID |
| TCP 9010 | CONFIRMED tässä työympäristössä |
| 0x2011 lähetetty | NOT_TESTED |
| 0x2012 vastaanotettu | NOT_TESTED |
| CAS hyväksytty ja Session saatu | NOT_TESTED |
| 0x3105 / 0x3106 | NOT_TESTED |
| TCP 9020 ja mediapaketit | NOT_TESTED |
| MPEG-TS, H.264-dekoodaus ja ääni | NOT_TESTED oikealla laitteella |

## Toteutuksen korjaus ja mittaus

DEV 0.3.8 säilyttää tiedoston encrypt_type-arvon. Deep Local Diagnostics on
Camera 1:n ingress/CSRF-suojattu POST-toiminto local_only-tilassa. Se käyttää
proxyn samaa viewer-lukkoa. Varattu katselu ei käynnistä uutta istuntoa.
Ei uudelleenyrityksiä tai pilvipolkua. SDK:lle annetaan 12 sekunnin kesto;
ulompi lukija katkaisee 25 sekunnissa tai 8 MiB:n kohdalla ja lopettaa koko
omistetun prosessiryhmän. FFprobe ja FFmpeg saavat kumpikin enintään 5 s.
Väliaikainen tallenne poistuu testin päättyessä. Credential-tiedostoon ei kirjoiteta.

Lähetys vahvistetaan SDK:n _send_all_with_timeout-kutsun valmistuttua,
ei send_encrypted_command-kutsun alussa. Vastauksen komentotunnus erotetaan
hyväksynnästä. Preview edellyttää Result=0 ja positiivista numeerista Sessionia;
setupin hyväksyntä vaatii eksplisiittisen Result=0:n. Pelkkä 0x3106 jää
hyväksynnän osalta NOT_TESTED-tilaan. Numeerinen hylkäys antaa FAILED-tilan.
Session-arvoa tai raakaa vastausta ei palauteta.

MPEG-TS edellyttää ehjiä synkronointi-/otsakekenttiä ja FFproben tunnistamia
raitoja. H.264 edellyttää H.264-raidan paketteja ja FFmpegin dekoodaamaa
kuvakehystä. Ääni edellyttää luettuja audiopaketteja: raidan olemassaolo ei
riitä. Äänivarmennus ei vielä todista AAC-koodekkia eikä kuuluvaa ääntä.
Synteettinen H.264/AAC-koe varmentaa mittarin, ei Camera 1:n toimintaa.

## Alkuperäinen sovellus ja avoimet protokollakysymykset

APK/PCAP-aineistoa ei löytynyt luettavissa olevasta paikallisesta aineistosta.
REA 6.8.0 on tavoitettavissa mutta kohdebinaaria ei ole avattu. Ei JADX-,
Ghidra-, Frida- tai sovelluksen runtime-analyysiä. Mac-ohje:
[W2H_APP_CAPTURE_MAC_FI.md](W2H_APP_CAPTURE_MAC_FI.md).

| Kysymys | Vahvistettu näyttö / puuttuva aineisto |
|---|---|
| Sovelluksen LAN vai P2P | Tuntematon; onnistuneen sovelluskatselun liikenne puuttuu |
| CAS DevSerial | Käyttäjän mukaan W2H-sarjalla hankinta onnistui; sovelluksen arvo tuntematon |
| Todellinen paikallinen kanava | Tuntematon; 1 on ehdokas |
| Komennot | SDK:n lähdekoodi: 0x2011/0x2012, 0x3105/0x3106; sovelluksen käyttö vahvistamatta |
| Media-avain ja salaus | Tuntematon W2H:lla; CAS-komentoavain ei yksin todista median avainta |
| H.264/AAC-siirtomuoto | Tuntematon oikealla W2H:lla |
| Puuttuvat integraatiovaiheet | Eivät ratkea ennen autentikoidun preview/setup/media-vaiheen mittausta |

Lähderajaus: pyEzvizApi a38ba757a3686cb412cc5029225e2608cdbccc4b,
pyezvizapi/__main__.py (CLI-oletus ja argumenttien etusija), hcnetsdk.py
(send_encrypted_command ja bootstrap_preview_stream), _local_stream.py
(valinnainen media_key ja decrypt_video). SDK:n tuetut polut eivät todista
sovelluksen valitsemaa polkua. Integraatio ei ota media-avainta pilvestä eikä
ota decrypt_videoa käyttöön arvauksen perusteella.

## Päivitys ja yksi testi HAOS:ssa

Kun 0.3.8:n molemmat imaget on vahvistettu julkaistuiksi:

```sh
ha store reload
ha apps update 6d530a54_ezviz_bc1_w2h_dev
```

Varmista Open Web UI:n versioksi 0.3.8, sulje Camera 1:n katselu, valitse
local_only ja paina Camera 1:n Deep Local Diagnostics kerran. Toimita vain
kiinteät vaiheiden tilat. Älä lähetä CAS-tiedostoa. Kameraa 2 ei testata.
