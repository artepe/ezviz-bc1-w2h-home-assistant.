"""Offline policy tests: local mode must fail closed before cloud access."""
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ezviz_bc1_w2h_dev"))

from connection import connection_mode
import local_capture
from local_proxy import LocalService
import runner
from supervisor_client import SupervisorClient, SettingsError
from web import CameraService


class ModeTests(unittest.TestCase):
    def setUp(self):
        runner.WORKERS = []
        runner.STOPPING = False

    def tearDown(self):
        runner.WORKERS = []

    def test_default_preserves_cloud_and_invalid_mode_is_rejected(self):
        self.assertEqual(connection_mode({}), "cloud")
        for mode in (None, "auto", "local", "", True):
            with self.assertRaises(ValueError):
                connection_mode({"connection_mode": mode})

    def test_local_never_reads_tokens_or_logs_in_even_with_relogin_requested(self):
        runtime = runner.Runtime()
        with patch.object(runner, "login", side_effect=AssertionError("cloud login")), \
             patch.object(runner, "prepare_workers", side_effect=AssertionError("token preparation")), \
             patch.object(runtime, "clear_tokens", side_effect=AssertionError("token deletion")), \
             patch.object(runner.Path, "is_file", side_effect=AssertionError("token read")), \
             patch.object(runner.subprocess, "Popen", return_value=Mock()) as spawn, \
             patch.object(runner, "log"):
            runtime.apply({"connection_mode": "local_only", "force_relogin": True,
                           "camera_serial": "HUB001-CAM001", "camera_serial_2": "HUB001-CAM002"}, 0)
        self.assertEqual(len(runner.WORKERS), 2)
        self.assertEqual(spawn.call_count, 2)
        for call in spawn.call_args_list:
            self.assertEqual(call.args[0][1], "/app/local_proxy.py")
            self.assertNotIn("--token-file", call.args[0])
        with patch.object(runner.subprocess, "run", side_effect=AssertionError("cloud trace")):
            self.assertFalse(runtime.trace_cloud(8558)["ok"])
            self.assertFalse(runtime.request_session_refresh())

    def test_switch_to_local_stops_previous_cloud_workers(self):
        previous = runner.ProxyWorker(1, "HUB001-CAM001", 8558, Path("/unused"))
        runner.WORKERS = [previous]
        runtime = runner.Runtime()
        with patch.object(runner, "shutdown_workers") as stop, \
             patch.object(runner, "poll_workers"), patch.object(runner, "login") as login:
            runtime.apply({"connection_mode": "local_only", "camera_serial": previous.serial}, 0)
        stop.assert_called_once_with([previous])
        login.assert_not_called()
        self.assertEqual(runner.WORKERS[0].mode, "local_only")

    def test_invalid_policy_stops_existing_workers_without_fallback(self):
        runner.WORKERS = [Mock()]
        runtime = runner.Runtime()
        with patch.object(runner, "shutdown_workers") as stop, patch.object(runner, "login") as login:
            runtime.apply({"connection_mode": "auto"}, 0)
        stop.assert_called_once()
        login.assert_not_called()
        self.assertEqual(runner.WORKERS, [])
        self.assertEqual(runtime.mode, "invalid")

    def test_snapshot_reports_local_file_status_without_keys_or_claiming_live_video(self):
        runtime = runner.Runtime()
        runtime.cameras = runner.parse_cameras({"camera_serial": "HUB001-CAM001"})
        runtime.mode = "local_only"
        with patch.object(runner, "WORKERS", []), \
             patch("local_capture.read_credentials", side_effect=ValueError("PRIVATE-CAS-SECRET")):
            state = runtime.snapshot()
        camera = state["cameras"][0]
        self.assertEqual(camera["local_credentials"], "missing_or_invalid")
        self.assertNotIn("PRIVATE-CAS-SECRET", json.dumps(state))
        self.assertNotIn("media_key", json.dumps(state))
        with patch.object(runner, "WORKERS", []), \
             patch("local_capture.read_credentials", return_value=("192.168.10.140", 3)):
            state = runtime.snapshot()
        self.assertEqual(state["cameras"][0]["local_credentials"], "format_valid")
        self.assertNotIn("video_verified", state["cameras"][0])

        runtime.mode = "cloud"
        with patch.object(runner, "WORKERS", []), \
             patch("local_capture.read_credentials", side_effect=AssertionError("do not read")):
            cloud_state = runtime.snapshot()
        self.assertNotIn("local_credentials", cloud_state["cameras"][0])

    def test_private_settings_save_preserves_account_and_cameras(self):
        client = SupervisorClient("synthetic")
        original = {"password": "!secret ezviz_password", "camera_serial": "HUB001-CAM001"}
        with patch.object(client, "raw_options", side_effect=[original, {**original, "connection_mode": "local_only"}]), \
             patch.object(client, "request") as request:
            client.save_connection_mode("local_only")
        self.assertEqual(request.call_args.args[1], {"options": {**original, "connection_mode": "local_only"}})

    def test_mode_save_checks_supervisor_did_not_drop_new_option(self):
        client = SupervisorClient("synthetic")
        with patch.object(client, "raw_options", return_value={}), patch.object(client, "request") as request:
            with self.assertRaises(SettingsError):
                client.save_connection_mode("local_only")
        self.assertEqual(request.call_count, 2)

    def test_connection_api_service_requests_reload(self):
        client, runtime = Mock(), Mock()
        CameraService(client, runtime).set_connection({"connection_mode": "local_only"})
        client.save_connection_mode.assert_called_once_with("local_only")
        runtime.reload.set.assert_called_once()


class LocalCaptureTests(unittest.TestCase):
    def credentials(self):
        return {"serial": "HUB001-CAM001", "channel": 3,
                "endpoint": {"host": "192.168.10.140", "command_port": 9010, "stream_port": 9020},
                "cas": {"key": "SYNTHETIC-TEST-ONLY", "operation_code": "SYNTHETIC-TEST-ONLY"}}

    def test_credentials_require_private_file_numeric_lan_host_and_explicit_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            data = self.credentials()
            path.write_text(json.dumps(data))
            path.chmod(0o600)
            self.assertEqual(local_capture.read_credentials(path, data["serial"]), ("192.168.10.140", 3))
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                local_capture.read_credentials(path, data["serial"])
            path.chmod(0o600)
            invalid = [
                {**data, "channel": None}, {**data, "channel": True},
                {**data, "serial": "OTHER-CAMERA"}, {**data, "cas": {}},
                {**data, "endpoint": {"host": "8.8.8.8"}},
                {**data, "endpoint": {"host": "cloud.example.invalid"}},
                {**data, "endpoint": {"host": "192.168.10.140", "stream_port": 443}},
            ]
            for value in invalid:
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError) as error:
                    local_capture.read_credentials(path, data["serial"])
                self.assertNotIn("SYNTHETIC", str(error.exception))

    def test_guard_blocks_cloud_dns_tcp_udp_and_other_lan_hosts_before_network(self):
        with patch.object(socket, "socket", socket.socket), patch.object(socket, "getaddrinfo", socket.getaddrinfo):
            local_capture.install_lan_guard("192.168.10.140")
            for destination in [("8.8.8.8", 443), ("192.168.10.141", 9010), ("192.168.10.140", 80)]:
                with socket.socket() as sock:
                    with self.assertRaises(OSError):
                        sock.connect(destination)
                    with self.assertRaises(OSError):
                        sock.connect_ex(destination)
                    with self.assertRaises(OSError):
                        sock.sendto(b"synthetic", destination)
            with self.assertRaises(OSError):
                socket.getaddrinfo("cloud.example.invalid", 443)

    def test_local_cli_has_no_cloud_or_decryption_flags(self):
        sdk = Mock()
        sdk.main.return_value = 0
        with patch.object(local_capture, "read_credentials", return_value=("192.168.10.140", 3)), \
             patch.object(local_capture, "install_lan_guard"), \
             patch.object(local_capture.logging, "disable"), \
             patch.dict(sys.modules, {"pyezvizapi": Mock(), "pyezvizapi.__main__": sdk}):
            self.assertEqual(local_capture.main(["/private/local.json", "HUB001-CAM001"]), 0)
        args = sdk.main.call_args.args[0]
        self.assertEqual(args[:2], ["stream", "local-sdk-dump"])
        self.assertEqual(args[args.index("--channel") + 1], "3")
        for flag in ("--fetch-cas", "--token-file", "--decrypt-video", "--username", "--password"):
            self.assertNotIn(flag, args)

    def test_local_failure_returns_503_without_opening_cloud(self):
        service = object.__new__(LocalService)
        service.lock = threading.RLock()
        service.viewer = threading.Lock()
        service.children = set()
        service.mode, service.hub_ip, service.cas_serial = "local", "static", ""
        service.cooldowns, service.last_result = {}, {}
        handler = Mock(wfile=io.BytesIO())
        worker = SimpleNamespace(serial="HUB001-CAM001")
        with patch.object(service, "open_local", return_value=None), \
             patch.object(service, "open_cloud", side_effect=AssertionError("cloud fallback")):
            service.stream(handler, worker)
        handler.send_response.assert_called_once_with(503)
        self.assertNotIn(b"SYNTHETIC", handler.wfile.getvalue())

    def test_missing_local_credentials_do_not_start_a_capture_process(self):
        service = object.__new__(LocalService)
        service.lock = threading.RLock()
        service.cooldowns, service.last_result = {}, {}
        worker = SimpleNamespace(serial="HUB001-CAM001", index=1)
        with patch("local_proxy.read_credentials", side_effect=ValueError("private details")), \
             patch("local_proxy.subprocess.Popen") as spawn:
            self.assertIsNone(service.open_local(worker, "static", ""))
        spawn.assert_not_called()
        self.assertEqual(service.last_result[worker.serial], "local_unavailable")

    def test_shutdown_terminates_every_owned_capture(self):
        service = object.__new__(LocalService)
        service.lock = threading.RLock()
        service.stopping = False
        first, second = Mock(), Mock()
        service.children = {first, second}
        with patch("local_proxy.terminate") as terminate:
            service.stop_children()
        self.assertTrue(service.stopping)
        self.assertCountEqual([call.args[0] for call in terminate.call_args_list], [first, second])


if __name__ == "__main__":
    unittest.main()
