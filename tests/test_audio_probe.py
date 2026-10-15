"""Distinguish missing audio, transport failures and actual AAC in MPEG-TS."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ezviz_bc1_w2h"))

from media_probe import inspect_audio


class AudioProbeTests(unittest.TestCase):
    def result(self, streams):
        return subprocess.CompletedProcess([], 0, json.dumps({"streams": streams}).encode())

    def test_audio_metadata_is_reported_without_source_or_stderr(self):
        completed = self.result([{"codec_type": "audio", "codec_name": "aac", "sample_rate": "16000", "channels": 1}])
        with patch("media_probe.subprocess.run", return_value=completed) as run:
            result = inspect_audio("http://127.0.0.1:8558/HUB001-CAM001.ts")
        self.assertTrue(result["audio"])
        self.assertIn("AAC, 16000 Hz, 1 channel(s)", result["message"])
        self.assertIn("not microphone volume", result["message"])
        self.assertNotIn("HUB001", json.dumps(result))
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 30)

    def test_video_only_is_distinct_from_failure_to_probe(self):
        with patch("media_probe.subprocess.run", return_value=self.result([{"codec_type": "video", "codec_name": "h264"}])):
            result = inspect_audio("offline")
        self.assertFalse(result["audio"])
        self.assertIn("video only during this test", result["message"])

    def test_timeout_and_bad_results_are_inconclusive_and_private(self):
        cases = [
            subprocess.TimeoutExpired("private-source", 22),
            FileNotFoundError("private-source"),
            subprocess.CompletedProcess([], 1, b"private-error-with-token"),
            subprocess.CompletedProcess([], 0, b"not-json-private-token"),
            subprocess.CompletedProcess([], 0, b'{"streams": [null]}'),
            subprocess.CompletedProcess([], 0, b'{"streams": []}'),
        ]
        for value in cases:
            with self.subTest(value=value):
                kwargs = {"side_effect": value} if isinstance(value, Exception) else {"return_value": value}
                with patch("media_probe.subprocess.run", **kwargs):
                    result = inspect_audio("private-source")
                self.assertFalse(result["ok"])
                self.assertIsNone(result["audio"])
                self.assertNotIn("private-", json.dumps(result))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe needed for transport fixture")
class ActualMpegtsTests(unittest.TestCase):
    def test_real_aac_transport_and_video_only_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            av = Path(directory) / "with_audio.ts"
            video = Path(directory) / "video_only.ts"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=25",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
                "-t", "1.5", "-c:v", "mpeg2video", "-c:a", "aac", "-f", "mpegts", str(av),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
            subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(av), "-map", "0:v:0", "-c", "copy", "-f", "mpegts", str(video),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
            detected = inspect_audio(str(av))
            self.assertTrue(detected["audio"], detected)
            self.assertIn("AAC, 16000 Hz", detected["message"])
            missing = inspect_audio(str(video))
            self.assertFalse(missing["audio"], missing)
            self.assertIn("video only", missing["message"])


if __name__ == "__main__":
    unittest.main()
