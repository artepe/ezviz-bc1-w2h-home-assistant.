"""Bounded audio-track inspection. Never return FFprobe errors or source URLs."""

from __future__ import annotations

import json
import re
import subprocess


def inspect_audio(source: str) -> dict[str, object]:
    """Inspect source metadata only; a track does not prove audible microphone data."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-analyzeduration", "8000000",
                "-probesize", "4000000", "-rw_timeout", "15000000",
                "-show_entries", "stream=codec_type,codec_name,sample_rate,channels",
                "-of", "json", source,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=22,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "audio": None, "message": "Audio test timed out. Close live views, check the camera in the EZVIZ app, and try again."}
    except OSError:
        return {"ok": False, "audio": None, "message": "Could not start the audio test. Check the app log and installed version."}

    try:
        if result.returncode != 0:
            raise ValueError
        data = json.loads(result.stdout)
        streams = data["streams"]
        if not isinstance(streams, list) or not all(isinstance(stream, dict) for stream in streams):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeError):
        return {"ok": False, "audio": None, "message": "Could not inspect the camera stream. Check Test video and the EZVIZ cloud connection, then try again."}

    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if audio is None:
        if any(stream.get("codec_type") == "video" for stream in streams):
            return {"ok": False, "audio": False, "message": "No audio track detected: the camera proxy supplied video only during this test. Check microphone/audio recording in the EZVIZ app. If it is enabled, the upstream cloud format may not support audio export; changing the Lovelace card cannot add a missing track."}
        return {"ok": False, "audio": None, "message": "No video or audio tracks were detected. Check Test video and the camera connection."}

    codec = audio.get("codec_name", "")
    label = codec.upper() if isinstance(codec, str) and re.fullmatch(r"[a-z0-9_]{1,32}", codec) else "unknown codec"
    details = [label]
    rate = str(audio.get("sample_rate", ""))
    if rate.isdigit() and 0 < int(rate) <= 384000:
        details.append(f"{int(rate)} Hz")
    channels = audio.get("channels")
    if isinstance(channels, int) and not isinstance(channels, bool) and 0 < channels <= 32:
        details.append(f"{channels} channel(s)")
    return {"ok": True, "audio": True, "message": f"Audio track received from the camera proxy: {', '.join(details)}. Use the audio-enabled go2rtc and Lovelace settings below, restart go2rtc, and unmute the player. This checks the track, not microphone volume."}
