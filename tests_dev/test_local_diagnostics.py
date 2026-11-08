"""Local failure causes must survive HTTP 503 without leaking source text."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ezviz_bc1_w2h_dev"))
import local_capture
from local_diagnostics import LocalCredentialError, error_payload, explain_local_error
from local_proxy import LocalService
from web import CameraService


class DiagnosticTests(unittest.TestCase):
    def service(self):
        service = object.__new__(LocalService)
        service.lock = threading.RLock()
        service.viewer = threading.Lock()
        service.children = set()
        service.stopping = False
        service.mode, service.hub_ip, service.cas_serial = "local", "static", ""
        service.cooldowns, service.last_result = {}, {}
        return service

    def test_file_validation_causes_without_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            cases = [(None, "MISSING_CREDENTIALS"), (b'\xffsecret', "INVALID_CREDENTIALS")]
            base = {"serial": "HUB-CAM", "endpoint": {"host": "192.168.10.140"}}
            cases += [(json.dumps({**base, "channel": 0}).encode(), "CHANNEL_INVALID"),
                      (json.dumps({**base, "channel": 2}).encode(), "INVALID_CREDENTIALS")]
            for payload, code in cases:
                if payload is not None:
                    path.write_bytes(payload)
                    path.chmod(0o600)
                with self.assertRaises(LocalCredentialError) as error:
                    local_capture.read_credentials(path, "HUB-CAM")
                self.assertEqual(error.exception.code, code)
                self.assertNotIn("secret", str(error.exception))

    def test_error_survives_stream_and_cooldown_without_cloud(self):
        service = self.service()
        worker = SimpleNamespace(serial="HUB-CAM", index=1)
        with patch("local_proxy.read_credentials", side_effect=LocalCredentialError("INVALID_CREDENTIALS")), \
             patch("local_proxy.subprocess.Popen") as spawn, \
             patch.object(service, "open_cloud", side_effect=AssertionError("cloud")):
            for _ in range(2):
                handler = Mock(wfile=io.BytesIO())
                service.stream(handler, worker)
                handler.send_response.assert_called_once_with(503)
                self.assertEqual(handler.wfile.getvalue(), error_payload("INVALID_CREDENTIALS"))
        spawn.assert_not_called()
        self.assertEqual(service.last_result[worker.serial], "INVALID_CREDENTIALS")

    def test_process_errors_and_transport_validation(self):
        worker = SimpleNamespace(serial="HUB-CAM", index=1)
        packet = b'\x47' + bytes(187)
        cases = [(21, [b''], "UNKNOWN"), (22, [b''], "UNKNOWN"),
                 (23, [b''], "UNKNOWN"), (24, [b''], "INVALID_CREDENTIALS"),
                 (None, [b''], "UNKNOWN"), (1, [b''], "UNKNOWN"),
                 (0, [b'\x47bad', b''], "MPEGTS_INVALID"),
                 (None, [packet[:7], packet[7:], packet], None)]
        for exit_code, chunks, expected in cases:
            service = self.service()
            process = Mock()
            process.poll.return_value = exit_code
            with patch.object(service, "local_command", return_value=["private"]), \
                 patch("local_proxy.subprocess.Popen", return_value=process), \
                 patch("local_proxy.next_bytes", side_effect=chunks), \
                 patch("local_proxy.terminate"):
                result = service.open_local(worker, "static", "")
            if expected:
                self.assertIsNone(result)
                self.assertEqual(service.last_result[worker.serial], expected)
            else:
                self.assertEqual(result, (process, packet * 2))

    def test_sdk_exceptions_are_translated_without_echoing(self):
        for message, code in [("EZVIZ local preview response is missing Session (Result=PRIVATE)", 21),
                              ("EZVIZ local SDK AES key must be 16 bytes", 24),
                              ("PRIVATE unexpected data", 23)]:
            sdk = SimpleNamespace(_handle_local_sdk_stream_dump=Mock(side_effect=RuntimeError(message)))
            original = sdk._handle_local_sdk_stream_dump
            sdk.main = Mock(side_effect=lambda args: sdk._handle_local_sdk_stream_dump(args))
            with patch.object(local_capture, "read_credentials", return_value=("192.168.10.140", 2)), \
                 patch.object(local_capture, "credential_encrypt_type", return_value=3), \
             patch.object(local_capture.shutil, "which", return_value="/usr/bin/ffmpeg"), \
             patch.object(local_capture, "install_lan_guard"), \
                 patch.object(local_capture, "observe_sdk"), \
                 patch.dict(sys.modules, {"pyezvizapi": SimpleNamespace(hcnetsdk=Mock())}), \
                 patch.object(local_capture.logging, "disable"), \
                 patch.dict(sys.modules, {"pyezvizapi.__main__": sdk}):
                self.assertEqual(local_capture.main(["/private/file", "HUB-CAM", "20"]), code)
            self.assertIs(sdk._handle_local_sdk_stream_dump, original)
            self.assertIn("20s", sdk.main.call_args.args[0])
        for seconds in ("0", "61", "bad"):
            self.assertEqual(local_capture.main(["/private/file", "HUB-CAM", seconds]), 2)

    def test_ui_uses_local_messages_and_never_schedules_cloud_login(self):
        runtime = Mock(mode="local_only")
        from urllib.error import HTTPError
        error = HTTPError("http://private", 503, "private", {}, io.BytesIO(error_payload("UNKNOWN")))
        client = Mock(lock=threading.RLock())
        service = CameraService(client, runtime)
        with patch("web.parse_cameras", return_value=[SimpleNamespace(port=8558, serial="HUB-CAM")]), \
             patch("web.socket.create_connection"), patch("web.build_opener") as opener:
            opener.return_value.open.side_effect = error
            result = service.test(8558)
        self.assertIn("UNKNOWN", result["message"])
        self.assertNotIn("cloud video request failed", result["message"])
        runtime.request_session_refresh.assert_not_called()

    def test_local_busy_is_not_reported_as_503(self):
        message = explain_local_error(b"PRIVATE", 409)
        self.assertIn("HTTP 409", message)
        self.assertNotIn("PRIVATE", message)

    def test_unknown_payload_is_never_echoed(self):
        self.assertNotIn("PRIVATE", explain_local_error(b"LOCAL_ERROR:PRIVATE\n"))
        self.assertIn("UNKNOWN", explain_local_error(b"PRIVATE"))

class EvidenceTests(unittest.TestCase):
    def test_classification_requires_stage_evidence(self):
        from local_diagnostics import failure_code
        self.assertEqual(failure_code(set(), b'', None, True), 'STARTUP_TIMEOUT')
        self.assertEqual(failure_code({'TCP_CONNECTED'}, b'', 22, True), 'STARTUP_TIMEOUT')
        self.assertEqual(failure_code({'TCP_CONNECT_FAILED'}, b'', None), 'LAN_CONNECT_FAILED')
        stages = {'PREVIEW_ACCEPTED', 'STREAM_SETUP'}
        self.assertEqual(failure_code(stages, b'', None, True), 'MEDIA_TIMEOUT')
        self.assertEqual(failure_code(stages, b'', 23), 'UNKNOWN')
        self.assertEqual(failure_code(stages | {'MEDIA_FRAME'}, b'', None, True), 'STARTUP_TIMEOUT')
        self.assertEqual(failure_code(set(), b'garbage', 0), 'MPEGTS_INVALID')
        # Missing Session or an undocumented Result is never CAS_AUTH_FAILED.
        self.assertEqual(failure_code({'TCP_CONNECTED'}, b'', 21), 'UNKNOWN')

    def test_file_presence_and_validation_are_independent_and_private(self):
        from local_diagnostics import credential_status
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'camera.json'
            self.assertEqual(credential_status(path, 'HUB-CAM'), {'exists': False, 'validation': 'MISSING_CREDENTIALS'})
            path.write_text('PRIVATE malformed')
            path.chmod(0o600)
            self.assertEqual(credential_status(path, 'HUB-CAM'), {'exists': True, 'validation': 'INVALID_CREDENTIALS'})
            data = {'serial': 'HUB-CAM', 'endpoint': {'host': '192.168.1.2'}, 'channel': 2,
                    'cas': {'key': 'PRIVATE key', 'operation_code': 'PRIVATE operation'}}
            path.write_text(json.dumps(data))
            self.assertEqual(credential_status(path, 'HUB-CAM')['validation'], 'FORMAT_VALID')
            path.chmod(0o644)
            self.assertEqual(credential_status(path, 'HUB-CAM')['validation'], 'INVALID_CREDENTIALS')
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            self.assertEqual(credential_status(link, 'HUB-CAM')['validation'], 'INVALID_CREDENTIALS')
            link.unlink()
            link.symlink_to(Path(directory) / 'absent')
            self.assertEqual(credential_status(link, 'HUB-CAM'), {'exists': True, 'validation': 'INVALID_CREDENTIALS'})

    def test_sdk_hooks_record_only_confirmed_responses_and_restore(self):
        class Client:
            def send_encrypted_command(self, command):
                return self.response
            def read_stream_frame_after_prefix(self):
                return object()
        sdk = SimpleNamespace(EzvizLocalSdkClient=Client, parse_ezviz_local_sdk_xml_fields=lambda r: r.fields, _send_all_with_timeout=lambda *a, **kw: None)
        original = Client.send_encrypted_command
        restore = local_capture.observe_sdk(sdk)
        try:
            client = Client()
            with patch.object(local_capture, 'emit_event') as event:
                client.response = SimpleNamespace(response=SimpleNamespace(header=SimpleNamespace(command=0x2012), fields={'Result': 'PRIVATE'}))
                client.send_encrypted_command(0x2011)
                self.assertEqual([c.args[0] for c in event.call_args_list], ['PREVIEW_REQUESTED', 'PREVIEW_RESPONSE'])
                client.response.response.fields = {'Result': '0', 'Session': '123'}
                client.send_encrypted_command(0x2011)
                event.assert_called_with('PREVIEW_ACCEPTED')
                client.response.response.header.command = 0x3106
                client.send_encrypted_command(0x3105)
                event.assert_called_with('STREAM_SETUP_ACCEPTED')
                client.read_stream_frame_after_prefix()
                event.assert_called_with('MEDIA_FRAME')
                self.assertNotIn('PRIVATE', str(event.call_args_list))
        finally:
            restore()
        self.assertIs(Client.send_encrypted_command, original)

    def test_side_channel_is_bounded_and_allowlisted(self):
        import os
        from local_diagnostics import read_events
        with tempfile.TemporaryFile() as source:
            with patch.dict(os.environ, {'LOCAL_DIAGNOSTIC_FD': str(source.fileno())}), \
                 patch.object(local_capture, '_emitted_events', set()):
                for _ in range(100):
                    local_capture.emit_event('MEDIA_FRAME')
                    local_capture.emit_event('PRIVATE')
            self.assertEqual(read_events(source), {'MEDIA_FRAME'})
            self.assertEqual(os.fstat(source.fileno()).st_size, len(b'MEDIA_FRAME\n'))

    def test_two_camera_snapshot_keeps_file_results_separate(self):
        import runner
        runtime = runner.Runtime()
        runtime.mode = "local_only"
        runtime.cameras = runner.parse_cameras({'camera_serial': 'HUB001-CAM001', 'camera_serial_2': 'HUB001-CAM002'})
        checks = [{'exists': False, 'validation': 'MISSING_CREDENTIALS'},
                  {'exists': True, 'validation': 'FORMAT_VALID'}]
        with patch.object(runner, 'WORKERS', []), patch('local_diagnostics.credential_status', side_effect=checks) as check:
            state = runtime.snapshot()
        self.assertEqual([str(call.args[0]) for call in check.call_args_list], ['/data/local_camera_1.json', '/data/local_camera_2.json'])
        self.assertEqual([c['local_credential_check'] for c in state['cameras']], checks)
        self.assertTrue(all(c['local_stream']['evidence'] is None for c in state['cameras']))

    def test_real_child_side_channel_and_transport_are_independent(self):
        service = DiagnosticTests().service()
        worker = SimpleNamespace(serial='HUB-CAM', index=1)
        # Real subprocess plumbing, with synthetic bytes and no network.
        program = "import os; os.write(int(os.environ['LOCAL_DIAGNOSTIC_FD']), b'TCP_CONNECTED\\nPREVIEW_ACCEPTED\\nSTREAM_SETUP\\nMEDIA_FRAME\\n'); os.write(1, (b'\\x47'+bytes(187))*2)"
        with patch.object(service, 'local_command', return_value=[sys.executable, '-c', program]):
            result = service.open_local(worker, 'static', '')
        self.assertIsNotNone(result)
        process, first = result
        process.wait(timeout=3)
        process.stdout.close()
        self.assertEqual(len(first), 376)
        self.assertTrue(all(service.evidence[worker.serial][key] for key in ('tcp_connected', 'preview_accepted', 'stream_setup', 'media_frame_received', 'mpegts_received')))
        self.assertFalse(service.evidence[worker.serial]['sdk_ready'])


if __name__ == "__main__":
    unittest.main()
