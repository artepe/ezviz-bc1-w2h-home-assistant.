# Video recovery and audio experiments (v0.2.2)

**Jos aaniasetus pysaytti videon, palauta ensin aiemmin toiminut videomalli.** Version 0.2.1 oletusmallit pyysivat AAC-aanta ennen sen varmistamista BC1-laitteistolla. Taman jalkeen videon kaynnistyminen epaonnistui yhdessa raportissa. Tarkan syyn selvittamiseen tarvitaan uusi go2rtc-loki; pelkka asetuksen muutos ei todista, missa virhe syntyi.

## Palauta video

Kayta kameranakyman tavallisia **Connection & dashboard setup** -malleja. Ne pyytavat taas vain videon:

```yaml
streams:
  ezviz_bc1:
    - "ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_FIRST_BC1_SERIAL.ts#video=copy"
  ezviz_bc1_2:
    - "ffmpeg:http://127.0.0.1:8559/YOUR_W2H_SERIAL-YOUR_SECOND_BC1_SERIAL.ts#video=copy"
```

Muuta molempiin olemassa oleviin kortteihin `media: video`. Tallenna ja kaynnista **go2rtc** uudelleen. Testaa yksi kamera kerrallaan.

Lisaosan paivitys versioon **0.2.2** palauttaa kopioitavat oletusmallit. Se ei muuta aiemmin tallentamaasi go2rtc-asetusta tai Lovelace-korttia.

## Test audio

Sulje livekatselut ja valitse kameran **Test audio**. Testi tarkistaa lisaosan HTTP MPEG-TS -lahteen ennen go2rtc:ta, enintaan noin 22 sekunnin ajan.

| Tulos | Merkitys / seuraava vaihe |
| --- | --- |
| **Audio track received ... AAC ...** | Lahteessa on aaniraidan metatiedot. Tama ei viela varmista oikeita aanipaketteja, mikrofonisignaalin voimakkuutta tai selaintoistoa. Aanen kokeilun voi tehda alla erillisella streamilla. |
| **No audio track detected ... video only** | Lahteessa nakyi testissa vain videota. Tarkista kuuluuko aani EZVIZ-sovelluksessa ja onko mikrofoni/aanitallennus kaytossa. Jos sovelluksessa kuuluu aani, tarvitaan taman pilviformaatin aanituen lisaselvitys. |
| **Timed out / Could not inspect ...** | Lahteen tutkiminen ei onnistunut. Tama ei todista aaniraidan puuttumista. Tarkista Test video ja kokeile uudelleen muiden livekatseluiden ollessa suljettuina. |

## Experimental audio test

Kokeile tata vasta, kun video toimii ja Test audio loytaa aaniraidan. Sailyta olemassa olevat `ezviz_bc1` / `ezviz_bc1_2` -lahteet ja kortit. Yhdista seuraava **uusi** avain olemassa olevaan `streams:`-osioon; ala lisaa toista `streams:`-otsikkoa. Esimerkki toiselle kameralle:

```yaml
streams:
  ezviz_bc1_2_audio_test:
    - "ffmpeg:http://127.0.0.1:8559/YOUR_W2H_SERIAL-YOUR_SECOND_BC1_SERIAL.ts#video=copy#audio=aac"
```

Tallenna ja kaynnista go2rtc uudelleen. Tee valiaikainen kortti:

```yaml
type: custom:webrtc-camera
url: ezviz_bc1_2_audio_test
mode: mse
media: video,audio
ui: true
muted: true
title: EZVIZ BC1 - Audio test
```

Sulje muut livekatselut ja avaa vain testikortti. Poista mykistys kaiutinpainikkeesta. Jos toisto epaonnistuu, tallenna taman yrityksen go2rtc-loki ja palaa alkuperaisen kameran korttiin. Poista valiaikainen testistream tarvittaessa. Lisaosan **Experimental audio test** -osio antaa vastaavat kamerakohtaiset mallit.

`audio=aac` muuntaa lahteessa olevan aanen AAC-muotoon. Se ei luo puuttuvaa aaniraitaa. `audio=copy` aiheutti aiemmassa testissa virheen `AAC with no global headers is currently not supported`.

## Streaming-library limits

The app keeps the pinned [pyEzvizApi revision](https://github.com/RenierM26/pyEzvizApi/tree/6df75d95a2ee6a68fb71446ee74a55572e2014ea) and existing proxy command. Its [streaming contract](https://github.com/RenierM26/pyEzvizApi/blob/6df75d95a2ee6a68fb71446ee74a55572e2014ea/docs/streaming.md) describes descriptor-backed AAC-LC export with the correct media key. Descriptor-free RTP AAC and other classified audio codecs can remain video-only. MPEG-PS audio carries its own framing. The current proxy does not force audio decryption; changing this requires evidence of the actual source format.

Automated tests verify metadata detection using generated AAC/video and video-only MPEG-TS, plus isolation of experimental aliases. They do not certify real BC1 audio or reproduce every live-stream startup failure. **Test video** checks MPEG-TS transport bytes, not decoded picture quality.

Official downstream references: [go2rtc FFmpeg](https://github.com/AlexxIT/go2rtc/tree/v1.9.14/internal/ffmpeg), [go2rtc codec compatibility](https://github.com/AlexxIT/go2rtc#codecs-madness), [WebRTC Camera options](https://github.com/AlexxIT/WebRTC#configuration).
