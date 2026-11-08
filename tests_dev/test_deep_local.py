"""Deep diagnostics must measure packets/decoding and leave no owned child."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ezviz_bc1_w2h_dev'))
from local_diagnostics import deep_result
from local_deep import capture_once, inspect_saved
from local_proxy import LocalService
import local_capture


class DeepTests(unittest.TestCase):
    def test_unknown_and_response_ids_never_imply_acceptance(self):
        result = deep_result({'PROCESS_STARTED', 'STREAM_SETUP', 'PREVIEW_RESPONSE'}, 'UNKNOWN')
        stages = {s['label']: s['status'] for s in result['stages']}
        self.assertEqual(stages['SDK process started'], 'CONFIRMED')
        for label in ('Stream setup accepted', 'Preview accepted', 'H.264 decoded', 'TCP 9010 connected'):
            self.assertEqual(stages[label], 'NOT_TESTED')
        self.assertFalse(result['ok'])

    def test_busy_and_camera_two_do_not_capture(self):
        service = object.__new__(LocalService)
        service.worker = SimpleNamespace(index=2)
        with patch('local_deep.capture_once') as capture:
            self.assertIn('CAMERA_NOT_SELECTED', service.deep_diagnostics()['message'])
            service.worker.index = 1
            service.viewer = threading.Lock()
            service.viewer.acquire()
            self.assertIn('LOCAL_BUSY', service.deep_diagnostics()['message'])
            capture.assert_not_called()

    def test_real_child_is_reaped_and_no_retry_occurs(self):
        service = object.__new__(LocalService)
        service.worker = SimpleNamespace(index=1, serial='SYNTHETIC')
        service.lock = threading.RLock()
        service.children = set()
        service.stopping = False
        with patch.object(service, 'local_command', return_value=[sys.executable, '-c',
                'import os; os.write(int(os.environ["LOCAL_DIAGNOSTIC_FD"]), b"PROCESS_STARTED\\nTCP_9010_FAILED\\n")']) as command:
            result = capture_once(service)
        self.assertEqual(len(service.children), 0)
        command.assert_called_once()
        stages = {s['label']: s['status'] for s in result['stages']}
        self.assertEqual(stages['TCP 9010 connected'], 'FAILED')
        self.assertEqual(stages['H.264 decoded'], 'NOT_TESTED')

    def test_sent_event_requires_completed_socket_write(self):
        sdk = SimpleNamespace()
        class Client:
            def send_encrypted_command(self, command):
                sdk._send_all_with_timeout(None, b'synthetic')
                raise TimeoutError()
            def read_stream_frame_after_prefix(self):
                return None
        sdk.EzvizLocalSdkClient = Client
        sdk._send_all_with_timeout = lambda *a: None
        sdk.parse_ezviz_local_sdk_xml_fields = lambda r: {}
        restore = local_capture.observe_sdk(sdk)
        try:
            with patch.object(local_capture, 'emit_event') as event:
                with self.assertRaises(TimeoutError):
                    Client().send_encrypted_command(0x2011)
                self.assertEqual([c.args[0] for c in event.call_args_list], ['PREVIEW_REQUESTED', 'PREVIEW_SENT'])
            with patch.object(sdk, '_send_all_with_timeout', side_effect=OSError), patch.object(local_capture, 'emit_event') as event:
                with self.assertRaises(OSError):
                    Client().send_encrypted_command(0x2011)
                event.assert_called_once_with('PREVIEW_REQUESTED')
        finally:
            restore()

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_h264_aac_packets_and_decoded_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.ts'
            generated = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                '-i', 'color=size=64x64:rate=5', '-f', 'lavfi', '-i', 'sine=frequency=440',
                '-t', '1', '-c:v', 'libx264', '-threads', '1', '-c:a', 'aac', '-f', 'mpegts', str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(generated.returncode, 0)
            events = set()
            inspect_saved(path, events)
            self.assertIn('H264_DECODED', events)
            self.assertIn('AUDIO_PACKETS', events)
            path.write_bytes(b'not media')
            events = set()
            inspect_saved(path, events)
            self.assertNotIn('H264_DECODED', events)
            self.assertNotIn('AUDIO_PACKETS', events)

class DeepIngressTests(unittest.TestCase):
    def test_ingress_csrf_and_local_only_required(self):
        from http.client import HTTPConnection
        from web import CameraServer
        client = SimpleNamespace(lock=threading.RLock(), raw_options=lambda: {'camera_serial': 'HUB001-CAM001'})
        runtime = SimpleNamespace(mode='local_only')
        server = CameraServer(('127.0.0.1', 0), client, runtime, allowed_hosts=('127.0.0.1',))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(token):
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('POST', '/api/cameras/8558/deep-local', '{}',
                {'Content-Type': 'application/json', 'X-CSRF-Token': token})
            response = connection.getresponse()
            status = response.status
            response.read()
            connection.close()
            return status
        try:
            with patch('web.build_opener') as opener:
                self.assertEqual(request('wrong'), 403)
                runtime.mode = 'cloud'
                self.assertEqual(request(server.csrf), 400)
                opener.assert_not_called()
                runtime.mode = 'local_only'
                import json
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(deep_result(set(), 'UNKNOWN')).encode()
                self.assertEqual(request(server.csrf), 200)
                self.assertEqual(opener.call_count, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
