# Camera audio / Kameran aani (v0.2.1)

Vanha kameranakyma antoi asetukset `#video=copy` ja `media: video`. Ne rajaavat aanen pois: go2rtc kaynnistaa silloin FFmpegin parametrilla `-an`. Version 0.2.1 kopioitavat asetukset pyytavat myos aanen.

## Paivitys ja asetukset

1. Paivita olemassa oleva EZVIZ-lisaosa versioon **0.2.1**, kun sen GitHub Actions -rakennus on onnistunut. Aiemmat kamerat ja portit sailyvat.
2. Valitse **Open Web UI -> kameran Connection & dashboard setup**. Korvaa vanhat kameralahteet go2rtc:n asetuksissa uusilla malleilla. Ala lisaa toista `streams:`-otsikkoa tai samaa kameran nimea uudelleen.
3. Tallenna ja kaynnista **go2rtc** uudelleen. Pelkka EZVIZ-lisaosan paivitys ei muuta olemassa olevaa go2rtc-asetusta tai Lovelace-korttia.
4. Korvaa myos kortin asetukset. Avaa kameran kuva ja poista mykistys soittimen kaiutinpainikkeesta. `muted: true` sallii kuvan automaattisen kaynnistymisen; aani avataan napsauttamalla.

go2rtc (vaihda tunnukset omiin koko kameratunnuksiisi):

```yaml
streams:
  ezviz_bc1:
    - "ffmpeg:http://127.0.0.1:8558/YOUR_W2H_SERIAL-YOUR_FIRST_BC1_SERIAL.ts#video=copy#audio=aac"
  ezviz_bc1_2:
    - "ffmpeg:http://127.0.0.1:8559/YOUR_W2H_SERIAL-YOUR_SECOND_BC1_SERIAL.ts#video=copy#audio=aac"
```

Toisen kameran kortti (ensimmaiselle `url: ezviz_bc1`):

```yaml
type: custom:webrtc-camera
url: ezviz_bc1_2
mode: mse
media: video,audio
ui: true
muted: true
title: EZVIZ BC1 - Camera 2
```

`audio=aac` muuntaa olemassa olevan aaniraidan AAC-muotoon MSE-katselua varten. Se ei luo aaniraitaa puuttuvan tilalle. `audio=copy` aiheutti aiemmassa laitteistotestissa virheen `AAC with no global headers is currently not supported`.

## Test audio

Sulje muut livekatselut ja valitse kameran **Test audio**. Testi avaa kameran pilviyhteyden hetkeksi ja tarkistaa lisaosan oman HTTP MPEG-TS -lahteen ennen go2rtc:ta. Testi voi kestaa enintaan noin 22 sekuntia.

| Tulos | Merkitys / seuraava vaihe |
| --- | --- |
| **Audio track received ... AAC ...** | Aaniraita paasee lisaosan lapi. Tarkista uudet go2rtc-asetukset, uudelleenkaynnistys, kortin `media: video,audio`, kaiutinpainike ja laitteen aanenvoimakkuus. Raita ei viela todista mikrofonisignaalin voimakkuutta. |
| **No audio track detected ... video only** | Lahde lahetti testissa vain videota. Tarkista, kuuluuko aani EZVIZ-sovelluksessa ja onko kameran mikrofoni/aanitallennus kaytossa. Jos sovelluksessa kuuluu aani, tarvitaan taman pilvivirran aaniformaatin lisaselvitys; kortin muutos ei korjaa puuttuvaa raitaa. |
| **Timed out / Could not inspect ...** | Yhteytta ei voitu varmistaa. Testaa video ja kokeile uudelleen, kun muut livekatselut on suljettu. Tama ei todista, etta kamera olisi aaneton. |

Jos go2rtc:n uudessa lokissa nakyy viela `-an` samalla kameranimella, kaytossa on edelleen video-only-lahde. Uuden asetuksen FFmpeg-komennossa pitaaisi nakya `-c:a aac`.

## Streaming-library limits

The app keeps its pinned [pyEzvizApi revision](https://github.com/RenierM26/pyEzvizApi/tree/6df75d95a2ee6a68fb71446ee74a55572e2014ea). Its [streaming contract](https://github.com/RenierM26/pyEzvizApi/blob/6df75d95a2ee6a68fb71446ee74a55572e2014ea/docs/streaming.md) describes descriptor-backed AAC-LC export with the correct media key. Descriptor-free RTP AAC and other classified audio codecs may remain video-only. MPEG-PS audio carries its own framing. The current app's proxy command has no forced audio-decryption flag; changing this without evidence of the actual stream could break working video.

The source-track test helps distinguish these upstream limits from downstream configuration. It does not change camera microphone settings, add talkback, or certify audible sound on BC1 hardware. The automated transport fixtures prove AAC-track detection and video-only detection, not the camera's cloud behavior.

Official downstream references: [go2rtc FFmpeg](https://github.com/AlexxIT/go2rtc/tree/v1.9.14/internal/ffmpeg), [go2rtc codec compatibility](https://github.com/AlexxIT/go2rtc#codecs-madness), [WebRTC Camera card options](https://github.com/AlexxIT/WebRTC#configuration).
