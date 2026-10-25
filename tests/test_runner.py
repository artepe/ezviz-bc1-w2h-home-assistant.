"""Offline checks for camera isolation, token handling and process lifecycle."""

import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ezviz_bc1_w2h"))
SPEC = importlib.util.spec_from_file_location("ezviz_runner", ROOT / "ezviz_bc1_w2h/runner.py")
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def worker(index=1):
    return runner.ProxyWorker(
        index=index,
        serial=f"HUB001-CAM00{index}",
        port=8557 + index,
        token=Path(f"/private/camera{index}.json"),
    )


class ConfigurationTests(unittest.TestCase):
    def test_existing_options_keep_one_camera(self):
        cameras, user, password, relogin, retry = runner.parse_options(
            {"camera_serial": "HUB001-CAM001"}
        )
        self.assertEqual(cameras, ("HUB001-CAM001",))
        self.assertEqual((user, password, relogin, retry), ("", "", False, 30))

    def test_second_camera_is_optional_and_whitespace_is_trimmed(self):
        cameras, *_ = runner.parse_options(
            {"camera_serial": " HUB001-CAM001 ", "camera_serial_2": "  "}
        )
        self.assertEqual(cameras, ("HUB001-CAM001",))

    def test_camera_order_is_stable_for_port_assignment(self):
        cameras, *_ = runner.parse_options(
            {"camera_serial": "HUB001-CAM001", "camera_serial_2": " HUB001-CAM002 "}
        )
        self.assertEqual(cameras, ("HUB001-CAM001", "HUB001-CAM002"))

    def test_duplicate_camera_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different"):
            runner.parse_options(
                {"camera_serial": "HUB001-CAM001", "camera_serial_2": "HUB001-CAM001"}
            )

    def test_bad_serial_and_retry_delay_are_rejected(self):
        for overrides in (
            {"camera_serial_2": "invalid/serial"},
            {"restart_delay": 9},
            {"restart_delay": 301},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                runner.parse_options({"camera_serial": "HUB001-CAM001", **overrides})


class TokenTests(unittest.TestCase):
    def test_private_token_files_and_legacy_port_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "ezviz_token.json"
            token.write_text('{"session": "offline-test"}')
            token.chmod(0o644)
            with patch.object(runner, "TOKEN", token):
                workers = runner.prepare_workers(("HUB001-CAM001", "HUB001-CAM002"))
            self.assertEqual([w.port for w in workers], [8558, 8559])
            self.assertEqual(workers[0].token, token)
            self.assertNotEqual(workers[0].token, workers[1].token)
            for w in workers:
                self.assertEqual(w.token.read_bytes(), token.read_bytes())
                self.assertEqual(w.token.stat().st_mode & 0o777, 0o600)
            workers[1].token.write_text('{"session": "refreshed-second"}')
            self.assertIn("offline-test", token.read_text())

    def test_single_camera_does_not_create_second_token(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "ezviz_token.json"
            token.write_text("{}")
            with patch.object(runner, "TOKEN", token):
                workers = runner.prepare_workers(("HUB001-CAM001",))
            self.assertEqual(len(workers), 1)
            self.assertEqual(list(Path(directory).iterdir()), [token])


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        runner.STOPPING = False
        runner.WORKERS = []
        runner.LOGIN_PROCESS = None

    def test_workers_use_distinct_ports_and_token_files(self):
        workers = [worker(1), worker(2)]
        with patch.object(runner.subprocess, "Popen") as spawn, patch.object(runner, "log"):
            runner.poll_workers(workers, retry=30, now=100)
        self.assertEqual(spawn.call_count, 2)
        for w, call in zip(workers, spawn.call_args_list):
            command = call.args[0]
            self.assertEqual(command[command.index("--serial") + 1], w.serial)
            self.assertEqual(command[command.index("--listen-port") + 1], str(w.port))
            self.assertEqual(command[command.index("--token-file") + 1], str(w.token))
            self.assertEqual(command[command.index("--listen-host") + 1], "127.0.0.1")
            self.assertTrue(call.kwargs["start_new_session"])
            self.assertEqual(call.kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(call.kwargs["stderr"], subprocess.DEVNULL)

    def test_failed_camera_restarts_after_delay_without_restarting_peer(self):
        failed, healthy = worker(1), worker(2)
        failed.process = Mock(pid=101)
        failed.process.poll.return_value = 1
        healthy.process = Mock(pid=102)
        healthy.process.poll.return_value = None
        healthy_process = healthy.process
        with patch.object(runner.os, "killpg") as kill, patch.object(
            runner.subprocess, "Popen"
        ) as spawn, patch.object(runner, "log") as log:
            runner.poll_workers([failed, healthy], retry=30, now=100)
            self.assertIsNone(failed.process)
            self.assertIs(healthy.process, healthy_process)
            kill.assert_called_once_with(101, signal.SIGKILL)
            spawn.assert_not_called()
            runner.poll_workers([failed, healthy], retry=30, now=129)
            spawn.assert_not_called()
            runner.poll_workers([failed, healthy], retry=30, now=130)
            spawn.assert_called_once()
            self.assertIs(healthy.process, healthy_process)
            self.assertNotIn(failed.serial, str(log.call_args_list))

    def test_start_failure_retries_only_that_camera(self):
        failed, healthy = worker(1), worker(2)
        healthy.process = Mock(pid=102)
        healthy.process.poll.return_value = None
        with patch.object(runner.subprocess, "Popen", side_effect=OSError("private details")), patch.object(
            runner, "log"
        ) as log:
            runner.poll_workers([failed, healthy], retry=30, now=100)
        self.assertEqual(failed.retry_at, 130)
        self.assertIsNone(failed.process)
        self.assertIsNotNone(healthy.process)
        self.assertNotIn("private details", str(log.call_args_list))

    def test_shutdown_stops_both_process_groups_and_reaps_children(self):
        workers = [worker(1), worker(2)]
        for index, w in enumerate(workers):
            w.process = Mock(pid=101 + index)
        workers[1].process.wait.side_effect = [subprocess.TimeoutExpired("proxy", 5), 0]
        with patch.object(runner.os, "killpg") as kill, patch.object(runner, "log"):
            runner.shutdown_workers(workers)
        self.assertEqual(
            kill.call_args_list,
            [
                unittest.mock.call(101, signal.SIGTERM),
                unittest.mock.call(102, signal.SIGTERM),
                unittest.mock.call(101, signal.SIGKILL),
                unittest.mock.call(102, signal.SIGKILL),
            ],
        )
        self.assertTrue(all(w.process is None for w in workers))

    def test_trace_counts_encrypted_video_channel_and_sanitizes_handshake(self):
        events = [
            {"channel_name": "HANDSHAKE", "result_code": 0, "has_stream_session": True,
             "streamurl": "https://secret.example?token=PRIVATE"},
            {"channel_name": "ENCRYPTED_STREAM", "transport": "UNKNOWN", "encrypted": True,
             "media": "PRIVATE"},
        ]
        result = runner.summarize_cloud_trace(json.dumps(events).encode())
        self.assertTrue(result["ok"])
        self.assertIn("session reported=yes", result["message"])
        self.assertIn("encrypted=1", result["message"])
        self.assertIn("UNKNOWN=1", result["message"])
        self.assertNotIn("PRIVATE", result["message"])
        no_packet = runner.summarize_cloud_trace(json.dumps(events[:1]).encode())
        self.assertFalse(no_packet["ok"])
        self.assertIn("No video-channel packets observed after handshake", no_packet["message"])
        self.assertNotIn("control packets, but no video-channel packets", no_packet["message"])

    def test_proxy_timeout_is_passed_to_vtm_socket(self):
        w = worker()
        with patch.object(runner.subprocess, "Popen", return_value=Mock()):
            runner.start_worker(w, retry=10, now=0.0)
        # Worker command options are separate from go2rtc / FFmpeg options.
        with patch.object(runner.subprocess, "Popen", return_value=Mock()) as popen:
            runner.start_worker(w, retry=10, now=1.0)
        args = popen.call_args.args[0]
        self.assertEqual(args[args.index("--timeout") + 1], "20")

    def test_media_failure_exposes_only_safe_handshake_counts(self):
        payload = json.dumps({
            "ok": False, "stage": "MEDIA_READ", "code": "VTM_IDLE_TIMEOUT",
            "handshake_result": 0, "has_stream_session": True,
            "media_packet_count": 0,
            "session_id": "DONT_LOG_ME",
        }).encode()
        result = runner.summarize_cloud_trace(payload)
        self.assertFalse(result["ok"])
        self.assertIn("VTM_IDLE_TIMEOUT", result["message"])
        self.assertIn("handshake result=0", result["message"])
        self.assertIn("Session reported=yes", result["message"])
        self.assertIn("packets=0", result["message"])
        self.assertNotIn("DONT_LOG_ME", result["message"])

    def test_safe_phase_status_does_not_reflect_untrusted_fields(self):
        data = {
            "ok": False,
            "stage": "VTM_HANDSHAKE",
            "code": "TIMEOUT",
            "http_status": 403,
            "signed_url": "https://secret.invalid/?token=VERY_PRIVATE",
        }
        result = runner.summarize_cloud_trace(json.dumps(data).encode())
        self.assertFalse(result["ok"])
        self.assertIn("VTM_HANDSHAKE / TIMEOUT", result["message"])
        self.assertIn("HTTP 403", result["message"])
        self.assertNotIn("secret.invalid", result["message"])
        self.assertNotIn("VERY_PRIVATE", result["message"])
        data["stage"] = "PRIVATE_USER_STRING"
        self.assertIn("unrecognized", runner.summarize_cloud_trace(json.dumps(data).encode())["message"])

    def test_trace_summary_shows_only_fixed_packet_metadata(self):
        payload = b'[{"channel_name":"CONTROL","transport":"UNKNOWN","token":"secret"},' \
            b'{"channel_name":"STREAM","transport":"RTP","encrypted":true,"url":"secret"},' \
            b'{"channel_name":"STREAM","transport":"MPEG_PS","encrypted":false}]'
        result = runner.summarize_cloud_trace(payload)
        self.assertTrue(result["ok"])
        self.assertIn("RTP=1", result["message"])
        self.assertIn("MPEG_PS=1", result["message"])
        self.assertIn("encrypted=1", result["message"])
        self.assertNotIn("secret", result["message"])
        no_media = runner.summarize_cloud_trace(b'[{"channel_name":"CONTROL"}]')
        self.assertFalse(no_media["ok"])
        self.assertIn("no video-channel packets", no_media["message"].lower())
        self.assertFalse(runner.summarize_cloud_trace(b'not-json')["ok"])

    def test_trace_invokes_only_selected_camera_without_showing_upstream_output(self):
        first, second = worker(1), worker(2)
        first.process = Mock(pid=100)
        first.process.poll.return_value = None
        second.process = Mock(pid=200)
        second.process.poll.return_value = None
        runner.WORKERS = [first, second]
        runtime = runner.Runtime()
        metadata = b'[{"channel_name":"STREAM","transport":"RTP","encrypted":false}]'
        with patch.object(runner.subprocess, "run", return_value=Mock(returncode=0, stdout=metadata)) as run:
            self.assertTrue(runtime.trace_cloud(8558)["ok"])
            args = run.call_args.args[0]
            self.assertEqual(args[args.index("--serial") + 1], first.serial)
            self.assertEqual(args[args.index("--token-file") + 1], str(first.token))
            self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(run.call_count, 1)
            self.assertFalse(runtime.trace_cloud(8558)["ok"])
            self.assertEqual(run.call_count, 1)
            self.assertTrue(runtime.trace_cloud(8559)["ok"])

    def test_manual_restart_only_touches_selected_proxy_and_is_rate_limited(self):
        first, second = worker(1), worker(2)
        first.process = Mock(pid=101)
        second.process = Mock(pid=102)
        original_peer = second.process
        runner.WORKERS = [first, second]
        runtime = runner.Runtime()
        with patch("runner.time.monotonic", return_value=1000), patch.object(
            runner, "shutdown_workers"
        ) as shutdown, patch.object(runner, "log"):
            self.assertTrue(runtime.restart_camera(first.port))
            shutdown.assert_called_once_with([first])
            self.assertFalse(runtime.restart_camera(first.port))
        self.assertIs(second.process, original_peer)
        self.assertEqual(first.retry_at, 0.0)
        self.assertTrue(runtime.reload.is_set())
        with patch("runner.time.monotonic", return_value=1061), patch.object(
            runner, "shutdown_workers"
        ) as shutdown, patch.object(runner, "log"):
            self.assertTrue(runtime.restart_camera(first.port))
            shutdown.assert_called_once_with([first])
        self.assertFalse(runtime.restart_camera(9999))

    def test_stop_signal_prevents_new_workers(self):
        workers = [worker(1), worker(2)]
        with patch.object(runner.subprocess, "Popen") as spawn:
            runner.stop(signal.SIGTERM, None)
            runner.poll_workers(workers, retry=30, now=100)
        spawn.assert_not_called()

    def test_process_exit_race_during_cleanup_is_safe(self):
        process = Mock(pid=101)
        with patch.object(runner.os, "killpg", side_effect=ProcessLookupError):
            runner.signal_process_group(process, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
