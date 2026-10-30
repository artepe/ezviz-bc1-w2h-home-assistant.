# Video recovery and audio experiments (v0.2.2)

## 2026-10-30: stacked Lovelace cards + isolated audio checks

The BC1 iPhone/W2H **local UDP recording** was inspected again with FFprobe:
both recovered MP4 samples contained **H.264 video** and **AAC mono,
16,000 Hz audio**. This is positive evidence of audio on the **local
iPhone P2P path**, but it does **not** prove that the current EZVIZ cloud
VTM MPEG-TS proxy exports AAC.

The known-good Home Assistant/video setup still uses `#video=copy`,
and its Lovelace cards request `media: video`; those settings exclude
audio *by design*. Do **not** modify the working streams until the
camera manager's **Test audio** reports an audio track at its source.

Ready-made examples:

- [Two vertically stacked working video cards](../examples/lovelace-two-cameras.yaml)
- [Separate audio-enabled go2rtc aliases](../examples/go2rtc-two-cameras-audio-test.yaml)
- [Two stacked experimental audio cards](../examples/lovelace-two-cameras-audio-test.yaml)

### Safe experiment

1. Check that audio is enabled in the official EZVIZ phone app. In
   **EZVIZ Cameras → Test audio**, run the test for camera 1 and camera 2
   **one at a time**; close competing viewers first.
2. If Test audio says `Audio track received ... AAC`, keep the
   currently working source untouched and **add only** the
   `ezviz_bc1_audio_test` / `ezviz_bc1_2_audio_test` aliases from
   the go2rtc audio example to the existing `streams:` mapping.
   For the **Legacy** proxy, camera 1's audio-test source must use
   port **8668** rather than 8558, and its alias should be
   `ezviz_bc1_legacy_audio_test` (change the first experimental card
   `url:` accordingly).
3. Restart **go2rtc only**; select just the corresponding
   `*_audio_test` stream. If it plays, insert the stacked experiment
   card, start one camera, and use the visible speaker button to
   **unmute**. Browser autoplay normally starts muted.
4. If Test audio reports **video only**, editing `media:` or
   `muted:` in Lovelace will not solve it: the missing AAC has to
   be recovered/exposed in the upstream cloud proxy (or implement
   the iPhone's local P2P path). If the audio test has a track but
   still fails in go2rtc, record the safe error message from the
   go2rtc UI/FFmpeg diagnostics, and preserve the stable video.
5. Remove only the optional `*_audio_test` entries if the experiment
   fails. No other camera settings need to change.

The `#audio=aac` FFmpeg directive requests AAC output **from an
existing input audio track**. It neither manufactures missing audio nor
decrypts unknown encrypted streams. Two simultaneous live viewers
can wake battery cameras and interfere with testing.

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
