"""Exercise migration, Supervisor persistence and the actual ingress HTTP API."""

import copy
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ezviz_bc1_w2h"))
sys.path.insert(0, str(ROOT / "scripts"))

from camera_config import Camera, parse_cameras, with_cameras
from release_metadata import metadata
import runner
from supervisor_client import SettingsError, SupervisorClient
from web import CameraServer, CameraService


class FakeSupervisorHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.seen_headers.append(dict(self.headers))
        if self.path == "/addons/self/info":
            self.respond({"result": "ok", "data": {"options": self.server.options}})
        elif self.path == "/addons/self/options/config":
            self.respond({"result": "ok", "data": self.server.options})
        else:
            self.respond({"result": "error"}, 404)

    def do_POST(self):
        self.server.seen_headers.append(dict(self.headers))
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.server.fail:
            self.respond({"result": "error", "message": "private-account-secret"}, 400)
            return
        self.server.options = body["options"]
        if self.server.drop_cameras:
            self.server.options.pop("cameras", None)
        self.respond({"result": "ok", "data": {}})


class SupervisorFixture(unittest.TestCase):
    def setUp(self):
        self.supervisor = ThreadingHTTPServer(("127.0.0.1", 0), FakeSupervisorHandler)
        self.supervisor.options = {
            "camera_serial": "HUB001-CAM001", "username": "offline@example.invalid",
            "password": "!secret ezviz_test", "force_relogin": False, "restart_delay": 10,
        }
        self.supervisor.seen_headers = []
        self.supervisor.fail = False
        self.supervisor.drop_cameras = False
        self.thread = threading.Thread(target=self.supervisor.serve_forever, daemon=True)
        self.thread.start()
        self.client = SupervisorClient("offline-supervisor-token", f"http://127.0.0.1:{self.supervisor.server_port}")
        self.runtime = Mock()
        self.runtime.reload = threading.Event()
        self.runtime.snapshot.return_value = {"message": "Ready", "cameras": []}

    def tearDown(self):
        self.supervisor.shutdown()
        self.supervisor.server_close()
        self.thread.join(timeout=2)


class CameraConfigurationTests(unittest.TestCase):
    def test_empty_install_can_open_camera_manager(self):
        self.assertEqual(parse_cameras({}), ())
        self.assertEqual(runner.parse_options({})[0], ())

    def test_upgrade_preserves_both_legacy_ports(self):
        cameras = parse_cameras({"camera_serial": "HUB001-CAM001", "camera_serial_2": "HUB001-CAM002"})
        self.assertEqual([(c.serial, c.port, c.stream) for c in cameras], [
            ("HUB001-CAM001", 8558, "ezviz_bc1"), ("HUB001-CAM002", 8559, "ezviz_bc1_2")])

    def test_second_camera_keeps_8559_if_first_is_absent(self):
        camera, = parse_cameras({"camera_serial_2": "HUB001-CAM002"})
        self.assertEqual((camera.port, camera.stream), (8559, "ezviz_bc1_2"))

    def test_removing_first_camera_does_not_move_second(self):
        raw = with_cameras({"camera_serial": "HUB001-CAM001"}, [Camera("Backyard", "HUB001-CAM002", 8559)])
        self.assertEqual(raw["camera_serial"], "")
        self.assertEqual(raw["camera_serial_2"], "")
        self.assertEqual(parse_cameras(raw)[0].port, 8559)

    def test_invalid_list_entries_are_rejected(self):
        for entry in [
            {"name": "Front", "serial": "invalid/path", "port": 8558},
            {"name": "Front", "serial": "HUB001-CAM001", "port": 8788},
            {"name": "Front", "serial": "HUB001-CAM001", "port": True},
            {"name": "", "serial": "HUB001-CAM001", "port": 8558},
            {"name": "bad\nname", "serial": "HUB001-CAM001", "port": 8558},
        ]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                parse_cameras({"cameras": [entry]})

    def test_duplicate_serial_or_port_is_rejected(self):
        for second in [Camera("Other", "HUB001-CAM001", 8559), Camera("Other", "HUB001-CAM002", 8558)]:
            with self.subTest(second=second), self.assertRaises(ValueError):
                with_cameras({}, [Camera("Front", "HUB001-CAM001", 8558), second])

    def test_snippets_follow_stable_ports_and_escape_titles(self):
        camera = Camera('Side "door"', "HUB001-CAM002", 8559)
        snippets = camera.snippets()
        self.assertIn("ezviz_bc1_2:", snippets["go2rtc"])
        self.assertIn("127.0.0.1:8559/HUB001-CAM002.ts#video=copy", snippets["go2rtc"])
        self.assertNotIn("#audio=", snippets["go2rtc"])
        self.assertIn("media: video\n", snippets["lovelace"])
        self.assertIn("muted: true\n", snippets["lovelace"])
        self.assertIn('title: "Side \\"door\\""', snippets["lovelace"])

    def test_audio_experiment_does_not_replace_working_video_alias(self):
        for port in (8558, 8559):
            camera = Camera("Front", "HUB001-CAM001", port)
            snippets = camera.snippets()
            self.assertIn(f"\n  {camera.stream}:\n", snippets["go2rtc"])
            self.assertNotIn("#audio=", snippets["go2rtc"])
            self.assertIn(f"\n  {camera.stream}_audio_test:\n", snippets["go2rtc_audio"])
            self.assertNotIn(f"\n  {camera.stream}:\n", snippets["go2rtc_audio"])
            self.assertIn(f"127.0.0.1:{port}/HUB001-CAM001.ts#video=copy#audio=aac", snippets["go2rtc_audio"])
            self.assertIn(f"url: {camera.stream}_audio_test\n", snippets["lovelace_audio"])
            self.assertIn("media: video,audio\n", snippets["lovelace_audio"])

    def test_release_tags_are_read_from_manifest(self):
        release = metadata(ROOT)
        self.assertEqual(release["image"], "ghcr.io/artepe/ezviz-bc1-w2h")
        config = (ROOT / "ezviz_bc1_w2h/config.yaml").read_text()
        self.assertIn(f'version: "{release["version"]}"', config)
        options = config.split("options:\n", 1)[1].split("schema:\n", 1)[0]
        self.assertIn('  camera_serial_2: ""', options)
        self.assertIn("  cameras: []", options)
        workflow = (ROOT / ".github/workflows/build-ezviz-image.yml").read_text()
        self.assertIn("steps.release.outputs.version", workflow)
        self.assertNotIn("ezviz-bc1-w2h:0.1.", workflow)


class PersistenceTests(SupervisorFixture):
    def test_add_camera_survives_new_client_and_preserves_secrets(self):
        original = copy.deepcopy(self.supervisor.options)
        service = CameraService(self.client, self.runtime)
        service.change("add", {"name": "Backyard", "hub_serial": "HUB001", "serial": "CAM002"})
        second_client = SupervisorClient("offline-supervisor-token", self.client.base_url)
        saved = second_client.raw_options()
        self.assertEqual([camera.port for camera in parse_cameras(saved)], [8558, 8559])
        self.assertEqual([camera.serial for camera in parse_cameras(saved)], ["HUB001-CAM001", "HUB001-CAM002"])
        for key in ("username", "password", "force_relogin", "restart_delay"):
            self.assertEqual(saved[key], original[key])
        self.assertTrue(self.runtime.reload.is_set())
        self.assertTrue(all(headers["Authorization"] == "Bearer offline-supervisor-token" for headers in self.supervisor.seen_headers))

    def test_save_that_silently_drops_cameras_is_not_reported_successful(self):
        self.supervisor.drop_cameras = True
        with self.assertRaisesRegex(SettingsError, "did not survive"):
            CameraService(self.client, self.runtime).change("add", {"name": "Backyard", "serial": "HUB001-CAM002"})
        self.assertFalse(self.runtime.reload.is_set())
        self.assertEqual(parse_cameras(self.supervisor.options)[0].serial, "HUB001-CAM001")

    def test_rejected_save_does_not_leak_upstream_response(self):
        self.supervisor.fail = True
        with self.assertRaises(SettingsError) as result:
            CameraService(self.client, self.runtime).change("add", {"name": "Backyard", "serial": "HUB001-CAM002"})
        self.assertNotIn("private-account-secret", str(result.exception))

    def test_edit_only_changes_target_camera_and_removal_keeps_port(self):
        service = CameraService(self.client, self.runtime)
        service.change("add", {"name": "Backyard", "serial": "HUB001-CAM002"})
        service.change("edit", {"name": "Garden", "serial": "HUB001-CAM003"}, 8559)
        cameras = parse_cameras(self.client.raw_options())
        self.assertEqual(cameras[0].serial, "HUB001-CAM001")
        self.assertEqual((cameras[1].name, cameras[1].serial, cameras[1].port), ("Garden", "HUB001-CAM003", 8559))
        service.change("remove", {}, 8558)
        self.assertEqual(parse_cameras(self.client.raw_options())[0].port, 8559)

    def test_concurrent_adds_do_not_lose_a_camera(self):
        service = CameraService(self.client, self.runtime)
        errors = []
        def add(index):
            try:
                service.change("add", {"name": f"Camera {index}", "serial": f"HUB001-CAM00{index}"})
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=add, args=(index,)) for index in (2, 3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
        self.assertFalse(errors)
        self.assertEqual([camera.port for camera in parse_cameras(self.client.raw_options())], [8558, 8559, 8560])


class IngressTests(SupervisorFixture):
    def setUp(self):
        super().setUp()
        self.ingress = CameraServer(("127.0.0.1", 0), self.client, self.runtime, allowed_hosts=("127.0.0.1",))
        self.ingress_thread = threading.Thread(target=self.ingress.serve_forever, daemon=True)
        self.ingress_thread.start()

    def tearDown(self):
        self.ingress.shutdown()
        self.ingress.server_close()
        self.ingress_thread.join(timeout=2)
        super().tearDown()

    def call(self, method, path, body=None, csrf=True, extra_headers=None):
        connection = HTTPConnection("127.0.0.1", self.ingress.server_port, timeout=3)
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if csrf:
            headers["X-CSRF-Token"] = self.ingress.csrf
        connection.request(method, path, None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        data = response.read().decode()
        status, response_headers = response.status, dict(response.headers)
        connection.close()
        return status, data, response_headers

    def test_ingress_path_assets_and_state_never_expose_account(self):
        status, page, _ = self.call("GET", "/", extra_headers={"X-Ingress-Path": "/api/hassio_ingress/offline-token"})
        self.assertEqual(status, 200)
        self.assertIn('<base href="/api/hassio_ingress/offline-token/">', page)
        self.assertIn("Add new camera", page)
        self.assertNotIn("offline@example.invalid", page)
        status, state, headers = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertNotIn("password", state)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_local_or_lan_clients_cannot_bypass_ingress_with_headers(self):
        self.ingress.allowed_hosts = frozenset({"172.30.32.2"})
        status, _, _ = self.call("POST", "/api/cameras", {"name": "Back", "serial": "HUB001-CAM002"}, extra_headers={"X-Forwarded-For": "172.30.32.2"})
        self.assertEqual(status, 403)

    def test_mutations_require_csrf(self):
        status, _, _ = self.call("POST", "/api/cameras", {"name": "Back", "serial": "HUB001-CAM002"}, csrf=False)
        self.assertEqual(status, 403)
        self.assertEqual(len(parse_cameras(self.supervisor.options)), 1)

    def test_add_edit_and_remove_through_http(self):
        for method, path, body in [
            ("POST", "/api/cameras", {"name": "Back", "serial": "HUB001-CAM002"}),
            ("PATCH", "/api/cameras/8559", {"name": "Garden", "serial": "HUB001-CAM002"}),
            ("DELETE", "/api/cameras/8559", {}),
        ]:
            with self.subTest(method=method):
                status, body, _ = self.call(method, path, body)
                self.assertEqual(status, 200, body)
                self.assertIn("verified", body)
        self.assertEqual([camera.port for camera in parse_cameras(self.supervisor.options)], [8558])

    def test_failed_persistence_is_a_visible_http_error(self):
        self.supervisor.drop_cameras = True
        status, body, _ = self.call("POST", "/api/cameras", {"name": "Back", "serial": "HUB001-CAM002"})
        self.assertEqual(status, 503)
        self.assertIn("did not survive", body)

    def test_test_video_reports_missing_listener(self):
        original = socket.create_connection
        def connect(address, *args, **kwargs):
            if address == ("127.0.0.1", 8558):
                raise ConnectionRefusedError
            return original(address, *args, **kwargs)
        with patch("web.socket.create_connection", side_effect=connect):
            status, body, _ = self.call("POST", "/api/cameras/8558/test", {})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["ok"])
        self.assertIn("8558", json.loads(body)["message"])

    def test_audio_probe_uses_only_saved_camera_and_requires_csrf(self):
        with patch("web.inspect_audio", return_value={"ok": True, "audio": True, "message": "AAC"}) as probe:
            status, _, _ = self.call("POST", "/api/cameras/8558/test-audio", {}, csrf=False)
            self.assertEqual(status, 403)
            probe.assert_not_called()
            status, _, _ = self.call("POST", "/api/cameras/1984/test-audio", {"url": "http://untrusted.invalid/"})
            self.assertEqual(status, 400)
            probe.assert_not_called()
            status, body, _ = self.call("POST", "/api/cameras/8558/test-audio", {"url": "http://untrusted.invalid/"})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["audio"])
            probe.assert_called_once_with("http://127.0.0.1:8558/HUB001-CAM001.ts")

    def test_concurrent_audio_probe_is_bounded(self):
        self.ingress.service.audio_test_lock.acquire()
        try:
            with patch("web.inspect_audio") as probe:
                status, body, _ = self.call("POST", "/api/cameras/8558/test-audio", {})
                self.assertEqual(status, 200)
                self.assertIsNone(json.loads(body)["audio"])
                self.assertIn("Another audio test", body)
                probe.assert_not_called()
        finally:
            self.ingress.service.audio_test_lock.release()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        runner.STOPPING = False
        runner.WORKERS = []

    def tearDown(self):
        runner.WORKERS = []

    def test_adding_second_camera_preserves_running_first_process(self):
        first = runner.ProxyWorker(1, "HUB001-CAM001", 8558, Path("/private/first.json"))
        first.process = Mock(pid=123)
        first.process.poll.return_value = None
        runner.WORKERS = [first]
        runtime = runner.Runtime()
        second = runner.ProxyWorker(2, "HUB001-CAM002", 8559, Path("/private/second.json"))
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "ezviz_token.json"
            token.write_text("{}")
            with patch.object(runner, "TOKEN", token), patch.object(runner, "prepare_workers", return_value=[second]), patch.object(runner, "poll_workers"), patch.object(runner, "shutdown_workers") as shutdown:
                runtime.apply({"camera_serial": first.serial, "camera_serial_2": second.serial}, 100)
                self.assertIs(runner.WORKERS[0], first)
                self.assertIs(runner.WORKERS[1], second)
                shutdown.assert_called_once_with([])

    def test_refreshed_second_camera_session_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "ezviz_token.json"
            token.write_text('{"session":"first"}')
            second = Path(directory) / "ezviz_token_camera_2.json"
            second.write_text('{"session":"second-refreshed"}')
            with patch.object(runner, "TOKEN", token):
                runner.prepare_workers(("HUB001-CAM001", "HUB001-CAM002"))
            self.assertIn("second-refreshed", second.read_text())

    def test_force_login_clears_sessions_once_even_without_cameras(self):
        runtime = runner.Runtime()
        with patch.object(runtime, "clear_tokens") as clear:
            runtime.apply({"force_relogin": True}, 100)
            runtime.apply({"force_relogin": True}, 101)
            clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
