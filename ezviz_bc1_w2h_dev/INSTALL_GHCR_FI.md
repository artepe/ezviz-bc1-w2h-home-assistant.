# DEV 0.3.1: valmis image Raspberry Pi 5:lle

DEV 0.3.0:n paikallinen BuildKit saattoi epäonnistua Alpine-pakettihakemistojen
latauksessa, vaikka HA:n tavallinen DNS toimi. Tämä muutos siirtää Docker-buildin
GitHub Actionsiin. Supervisorin oma verkkoyhteys ja buildin verkkoyhteys eivät ole
sama asia; tähän korjaukseen ei sisälly DNS-asetusten muuttamista.

Manifestin `image: "ghcr.io/artepe/ezviz-bc1-w2h"` ja `version: "0.3.1"`
ohjaavat Supervisorin hakemaan `ghcr.io/artepe/ezviz-bc1-w2h:0.3.1`-imagen.
Image-indeksi valitsee Pi 5:lle linux/arm64-version (HA:n aarch64) ja Intel/AMD:lle
linux/amd64-version. build.yaml on poistettu DEV-paketista eikä paikallista
Docker-buildia enää tarvita. Sama GHCR-paketti palvelee myös tavallista lisäosaa;
DEV-versio käyttää omaa 0.3.1-tagia eikä muuta tavallisen lisäosan 0.2.x-tagia.

## Julkaisu ja testit

Workflow `.github/workflows/build-ezviz-dev.yml` rakentaa molemmat arkkitehtuurit
natiiveilla GitHub-runnereilla. Se ajaa yksikkötestit, `pip check` -tarkistuksen,
SDK:n CLI/import-tarkistukset, FFmpeg/FFprobe- ja oikean MPEG-TS-äänifixtuurin
testit sekä oletuskäynnistyksen s6-ympäristötarkistuksen. Testikonteissa on
`--network none`; kamerayhteyksiä tai käyttäjän tunnuksia ei käytetä.

Pull request rakentaa ja testaa ilman julkaisua. Main-haaran sekä tämän korjauksen
`codex/dev-ghcr-prebuilt-images`-haaran push julkaisee vain testatut commit-kohtaiset
arkkitehtuurit. Molempien läpäistyä workflow julkaisee versiotagit ja yhteisen
multiarch-tagin. Kirjautuminen käyttää ainoastaan workflow'n `GITHUB_TOKEN`-arvoa
ja `packages: write` -oikeutta. Viimeinen tarkistus vetää molemmat arkkitehtuurit
ilman rekisteritunnuksia: jos paketti ei ole julkisesti luettavissa, julkaisuajo
ei ole onnistunut kokonaisuudessaan.

## Päivitys HA OS:ssä

1. Odota, että molemmat buildit ja julkaisuajo ovat vihreitä GitHub Actionsissa.
   PR:n vihreä build yksin ei tarkoita, että image olisi julkaistu.
2. Tee varmuuskopio nykyisestä DEV-lisäosasta ja sen datasta.
3. Jos käytät paikallista asennusta, korvaa sen **lähdetiedostot** tämän version
   `ezviz_bc1_w2h_dev`-hakemiston tiedostoilla. Säilytä hakemiston nimi ja slug
   `ezviz_bc1_w2h_dev`. Poista vanha `build.yaml` lähdekansiosta. Älä koske
   lisäosan yksityiseen `/data`-hakemistoon, asetuksiin tai tokeneihin.
4. Tarkista lisäosakaupan päivitykset. Valitse DEV-version päivitys versioon 0.3.1.
   Supervisorin tulee vetää valmis image; lokissa ei pitäisi näkyä `apk add`
   -buildia. Jos paikallinen lähde yhä rakentuu, varmista että config.yaml sisältää
   image-rivin ja version 0.3.1.
5. Käynnistä vain yksi EZVIZ-proxyversio kerrallaan. Nykyiset portit 8558/8559,
   kamerajärjestys, local_only/cloud-valinta sekä yksityiset tunnisteet säilyvät,
   kun päivität samaa paikallista lisäosaa. Repoasennus voi saada eri Supervisor-ID:n;
   se ei automaattisesti peri paikallisen lisäosan yksityisiä tietoja.

Tämä korjaa paketoinnin, ei vielä paikallisen W2H-autentikoinnin tai äänen
todentamista. Asennuksen onnistuminen vahvistetaan vasta oman HA OS:n
asennus- ja käynnistyslokista. Älä poista vanhaa asennusta palautuskeinona.

Viralliset lähteet:
- https://contributors.home-assistant.io/apps/guides/publishing/
- https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images
