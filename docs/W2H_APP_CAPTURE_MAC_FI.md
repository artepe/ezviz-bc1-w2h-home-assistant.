# Kamera 1: alkuperäisen sovelluksen aineisto MacBookilla

## Tämän työskentelykerran tila (2026-11-08)

Paikallinen haku /tmp-, /opt-, /workspace- ja /root-hakemistoista ei löytänyt
APK/APKS-, PCAP/PCAPNG-, HCNetSDK/PlayCtrl-SO- tai EZVIZ-AAR-aineistoa.
Hakujen pääsyvirheet ohitettiin; tämä ei ole käyttäjän Macin tai puhelimen inventaario.
REA MCP 6.8.0 vastasi. Ghidra ei määritetty, JADX MCP JAR puuttuu,
adb puuttuu, Frida-adapterin npm-riippuvuus puuttuu ja tshark/capinfos puuttuvat.
Ei sovelluksen dekompilointia tai Frida-ajoa. Yksi TCP 9010 -yhteys muodostui
0,01 sekunnissa tästä ympäristöstä. /data/local_camera_1.json puuttuu eikä
vastaavaa tiedostoa löytynyt /tmp- tai /opt-puusta; CAS/preview/mediakoetta ei ajettu.

Lukitulla pyEzvizApi-commitilla a38ba757a3686cb412cc5029225e2608cdbccc4b
tehty offline-toisto osoitti, että CLI:n encrypt_type-oletus 1 ohittaa bundle-arvon.
Synteettinen bundle-arvo 3 muuttui arvoksi 1 ennen stream-avausta. Korjaus välittää
arvon eksplisiittisesti. Tämä EI osoita oikean W2H:n CAS-arvoa eikä todista sen
503:n juurisyytä. Oikeat salaisuudet ja laitetiedostot jätettiin koskematta.

## Tarvittava aineisto

- Puhelimen käyttöjärjestelmä, EZVIZ-sovelluksen versionumero ja Android-versio.
- Androidilta saman asennuksen base.apk ja kaikki split-APK:t; ei eri version APK:ta.
- Kamera 1:n onnistuneen livevideon liikenne: 10 s ennen avaamista,
  noin 30 s liikkuvaa kuvaa, katselun sulkeminen ja 10 s jälkiseuranta.
- Tieto kaappauspisteestä, puhelimen LAN-IP:stä, kuvan toimimisesta ja avausajasta.
- Erikseen nykyisen DEV-lisäosan turvallinen local_stream/last_result/evidence-tila.
  Älä toimita /data/local_camera_1.json-tiedostoa, tokeneita tai tilin salasanaa.

APK kertoo mahdolliset koodipolut. Vain saman istunnon runtime- ja liikennenäyttö
osoittaa käytetyn polun, sarjanumeron roolin ja kanavan. Salaamaton RTP/MPEG-PS
ja h264-dekoodaus on varmennettava erikseen. Kameraa 2 ei avata.

## Androidin APK-kopio Macilla

Jos työkalut puuttuvat, asenna Android Platform Tools ja Wireshark niiden
virallisista jakeluista. Alla komennot eivät asenna ohjelmia tai muuta sovellusta.
Kytke oma Android USB:llä ja hyväksy USB debugging puhelimessa.

```sh
adb devices -l
adb shell pm list packages -3 | grep -i -E 'ezviz|hik'
```

Valitse listasta juuri käyttämäsi sovellus. Aja seuraava lohko bashissa ja vaihda
PACKAGE_NAME havaittuun pakettinimeen. Se kopioi vain sovelluspaketit, ei app dataa.

```bash
bash <<'BASH'
set -euo pipefail
umask 077
package='PACKAGE_NAME'
[ "$package" != PACKAGE_NAME ] || { echo 'Aseta havaittu pakettinimi'; exit 1; }
out="$HOME/ezviz-private-research/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out/apk"
adb shell pm path "$package" | tr -d '\r' > "$out/apk-paths.txt"
while IFS= read -r entry; do
  case "$entry" in
    package:*) adb pull "${entry#package:}" "$out/apk/" ;;
    *) echo 'Odottamaton pm path -tulos'; exit 1 ;;
  esac
done < "$out/apk-paths.txt"
shasum -a 256 "$out"/apk/*.apk > "$out/apk-sha256.txt"
echo "$out"
BASH
```

Jos useita Android-laitteita on kytkettynä, käytä joka adb-komennossa
`adb -s HAVAITTU_LAITETUNNUS`. Älä julkaise yksityistä aineistohakemistoa GitHubissa.

## Liikennekaappaus

Mac samassa Wi-Fi-verkossa ei yleensä näe puhelimen ja W2H:n välistä unicastia.
Käytä reitittimen kaappausta, peilausporttiin kytkettyä Macin Ethernet-liitäntää
tai valmiiksi toimivaa puhelimen kaappausta. VPN-pohjainen kaappaus voi muuttaa
sovelluksen reitinvalintaa; merkitse tämä rajoitus.

Wiresharkin Mac-asennuksessa tshark löytyy tavallisesti sovelluspaketista:

```sh
/Applications/Wireshark.app/Contents/MacOS/tshark -D
```

Valitse oikeasti liikenteen näkevä liitäntä. Korvaa OBSERVED_INTERFACE ja
PHONE_LAN_IP havaituilla arvoilla. Suodatin säilyttää myös puhelimen mahdollisen
P2P/relay-liikenteen. Älä rajaa tähän vaiheeseen vain portteja 9010/9020.

```sh
umask 077
mkdir -p "$HOME/ezviz-private-research"
/Applications/Wireshark.app/Contents/MacOS/tshark \
  -i OBSERVED_INTERFACE -n \
  -f 'host PHONE_LAN_IP or host 192.168.10.140' \
  -a duration:60 \
  -w "$HOME/ezviz-private-research/camera1-live.pcapng"
```

Avaa ainoastaan kamera 1. Kirjaa UTC-avausaika ja näkyikö liikkuva kuva.
Pidä PCAP yksityisenä: se voi sisältää myös muiden puhelinsovellusten liikennettä.
Kaappauksen kattavuus on tarkistettava ennen kuin puuttuva LAN-liikenne tulkitaan.

Pelkkien otsakekenttien ensitarkistus ilman pakettikuorman tulostamista:

```sh
/Applications/Wireshark.app/Contents/MacOS/tshark -n \
  -r "$HOME/ezviz-private-research/camera1-live.pcapng" \
  -Y 'ip.addr == 192.168.10.140 && (tcp.port == 9010 || tcp.port == 9020)' \
  -T fields -e frame.time_relative -e ip.src -e tcp.srcport \
  -e ip.dst -e tcp.dstport -e tcp.len
```

## Frida ja jatkoanalyysi

Tavallisella roottaamattomalla Androidilla ei oleteta olevan attach-oikeutta
julkaistuun sovellukseen. Älä roottaa pääpuhelinta tätä ohjetta varten.
Jos valtuutettu Frida-testiympäristö on jo olemassa:

```sh
frida --version
frida-ps -Uai
```

Tämä listaa sovellukset; se ei vielä hookkaa niitä. Täsmälliset hookit valitaan
APK:n todellisista luokka-/metodinimistä ja saman version natiivisymboleista.
Ei arvattuja hookkeja eikä yleistä argumenttien/return-arvojen dumppausta.
Raportoitavat tiedot: kiinteä vaihenimi, suhteellinen aika, tunnettu komento-ID,
kanava, tunnisteen rooli (hub/kamera/yhdistelmä), hyväksyntäboolean ja tuloskoodi.
Ei avaimia, operation codea, Sessionia, tokeneita, raakaa XML:ää tai mediapuskuria.

Analyysijärjestys: APK-hash/versio → pakettiluettelo → JADX:n todellinen
livekutsuketju → JNI ja valitut natiivikirjastot Ghidralla → rajatut Frida-hookit
→ saman live-istunnon PCAP → vertailu pyEzvizApi:n preview/setup/media-polkuun.
TCP-kehykset kootaan tavujonosta; yhden paketin rajoja ei pidetä komentorajoina.
Vain vahvistettu protokollaero johtaa protokollamuutokseen. Hyväksymisehto on
kamera 1:n H.264-tunnistus ja onnistunut kuvan dekoodaus paikallisesta istunnosta.

Lähteet:
- https://developer.android.com/tools/adb
- https://www.wireshark.org/docs/man-pages/tshark.html
- https://frida.re/docs/frida-ps/
