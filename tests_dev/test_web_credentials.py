"""Exercise private ingress setup with synthetic secrets, without EZVIZ access."""
import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ezviz_bc1_w2h_dev'))
from web import CameraServer
from local_capture import read_credentials
from local_credentials import install_data
import local_acquire

SERIAL = 'HUB001-CAM001'
SECRET = 'secret-16-bytes!'


def bundle():
    return {'serial': SERIAL, 'endpoint': {'host': '192.168.10.140'},
            'cas': {'key': SECRET, 'operation_code': 'PRIVATE-OP'},
            'session_id': 'PRIVATE-TOKEN'}


class WebCredentialTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.client = SimpleNamespace(lock=threading.RLock(), raw_options=lambda: {'camera_serial': SERIAL})
        self.runtime = SimpleNamespace(mode='local_only', reload=threading.Event(), snapshot=lambda: {'cameras': []})
        self.server = CameraServer(('127.0.0.1', 0), self.client, self.runtime, allowed_hosts=('127.0.0.1',))
        self.server.service.credential_directory = self.root
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.payload = {'action': 'import', 'channel': 7, 'credentials': bundle()}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def call(self, payload=None, token=True, port=8558, method='POST', raw=None):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-CSRF-Token'] = self.server.csrf
        data = json.dumps(self.payload if payload is None else payload) if raw is None else raw
        connection.request(method, f'/api/cameras/{port}/local-credentials', data, headers)
        response = connection.getresponse()
        body = response.read().decode()
        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
        connection.close()
        for secret in (SECRET, 'PRIVATE-OP', 'PRIVATE-TOKEN', 'ACCOUNT-PASSWORD'):
            self.assertNotIn(secret, body)
        return response.status, json.loads(body)

    def test_ingress_csrf_method_and_body_limits(self):
        self.assertEqual(self.call(token=False)[0], 403)
        self.server.allowed_hosts = frozenset()
        self.assertEqual(self.call()[0], 403)
        self.server.allowed_hosts = frozenset(('127.0.0.1',))
        self.assertEqual(self.call(method='PATCH')[0], 404)
        self.assertEqual(self.call(raw='x' * 32769)[0], 413)
        self.assertEqual(self.call(raw='not json')[0], 400)
        self.assertFalse(list(self.root.iterdir()))

    def test_valid_import_is_private_atomic_and_never_proves_video(self):
        with patch('web.subprocess.run', side_effect=AssertionError('offline import contacted cloud')):
            status, body = self.call()
        self.assertEqual(status, 200)
        self.assertIn('FORMAT_VALID', body['message'])
        self.assertIn('video remain unconfirmed', body['message'])
        target = self.root / 'local_camera_1.json'
        self.assertEqual(read_credentials(target, SERIAL), ('192.168.10.140', 7))
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('session_id', json.loads(target.read_text()))
        self.assertTrue(self.runtime.reload.is_set())
        before = target.read_bytes()
        self.assertEqual(self.call()[0], 400)
        self.assertEqual(target.read_bytes(), before)
        bad = copy.deepcopy(self.payload)
        bad['replace'] = True
        bad['credentials']['cas']['key'] = 'bad'
        self.assertEqual(self.call(bad)[0], 400)
        self.assertEqual(target.read_bytes(), before)
        good = copy.deepcopy(self.payload)
        good.update(channel=8, replace=True)
        self.assertEqual(self.call(good)[0], 200)
        self.assertEqual(read_credentials(target, SERIAL)[1], 8)
        self.assertFalse(list(self.root.glob('.local-import-*')))

    def test_invalid_channel_serial_host_key_and_cloud_policy(self):
        for channel in (None, True, 0, 257, '7', 1.5):
            with self.subTest(channel=channel):
                self.assertEqual(self.call(self.payload | {'channel': channel})[0], 400)
        for field, value in [('serial', 'OTHER-CAMERA'), ('channel', 9),
                             ('endpoint', {'host': '8.8.8.8'}),
                             ('endpoint', {'host': 'localhost'}),
                             ('endpoint', {'host': '192.168.10.140', 'command_port': 8000}),
                             ('cas', {'key': SECRET})]:
            data = bundle() | {field: value}
            self.assertEqual(self.call(self.payload | {'credentials': data})[0], 400)
        self.assertEqual(self.call(port=8573)[0], 400)
        self.assertEqual(self.call(self.payload | {'replace': 1})[0], 400)
        self.runtime.mode = 'cloud'
        with patch('web.subprocess.run') as run:
            self.assertEqual(self.call()[0], 400)
            run.assert_not_called()
        self.assertFalse(list(self.root.iterdir()))

    def cloud_payload(self):
        return {'action': 'acquire', 'channel': 7, 'allow_cloud': True,
                'username': 'OWNER', 'password': 'ACCOUNT-PASSWORD', 'api_url': 'apiieu.ezvizlife.com'}

    def test_acquisition_requires_explicit_consent_and_fixed_region(self):
        with patch('web.subprocess.run') as run:
            for fields in ({'allow_cloud': False}, {'api_url': 'attacker.example'}, {'sms_code': 'bad'}):
                self.assertEqual(self.call(self.cloud_payload() | fields)[0], 400)
            run.assert_not_called()
        self.server.service.credential_lock.acquire()
        try:
            self.assertEqual(self.call()[0], 400)
        finally:
            self.server.service.credential_lock.release()

    def test_acquisition_private_stdin_and_no_cloud_token_file_changes(self):
        token = self.root / 'ezviz_token.json'
        token.write_text('existing cloud token')
        with patch('web.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(bundle()).encode())) as run:
            self.assertEqual(self.call(self.cloud_payload())[0], 200)
        args, kwargs = run.call_args
        self.assertNotIn('ACCOUNT-PASSWORD', str(args))
        self.assertEqual(json.loads(kwargs['input'])['password'], 'ACCOUNT-PASSWORD')
        self.assertEqual(kwargs['timeout'], 60)
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(token.read_text(), 'existing cloud token')
        self.assertEqual(read_credentials(self.root / 'local_camera_1.json', SERIAL)[1], 7)

    def test_acquisition_failures_never_publish_or_expose_errors(self):
        for code in (1, 10, 11, 12):
            with patch('web.subprocess.run', return_value=SimpleNamespace(returncode=code, stdout=b'PRIVATE-TOKEN')):
                status, body = self.call(self.cloud_payload())
                self.assertTrue(status == 400 or body.get('ok') is False)
        for error in (subprocess.TimeoutExpired('ACCOUNT-PASSWORD', 60), OSError('PRIVATE-OP')):
            with patch('web.subprocess.run', side_effect=error):
                self.assertEqual(self.call(self.cloud_payload())[0], 400)
        self.assertFalse(list(self.root.iterdir()))

    def test_stage_diagnostics_reach_ingress_without_secrets(self):
        for code, stage in ((20, 'lan_metadata'), (21, 'p2p_registration'), (22, 'cas_lookup')):
            diagnostic = {'stage': stage, 'result_code': 1052170, 'session_present': False,
                          'cas_identity': 'selected_camera', 'key': SECRET, 'message': 'PRIVATE-TOKEN'}
            with patch('web.subprocess.run', return_value=SimpleNamespace(
                    returncode=code, stdout=json.dumps(diagnostic).encode())):
                status, body = self.call(self.cloud_payload())
            self.assertEqual(status, 200)
            self.assertFalse(body['ok'])
            self.assertEqual(body['stage'], stage)
            self.assertIn('1052170', body['message'])
        self.assertFalse(list(self.root.iterdir()))

    def test_all_camera_slots_and_symlink_replacement(self):
        install_data(bundle(), self.root, SERIAL, 7, 16)
        self.assertEqual(read_credentials(self.root / 'local_camera_16.json', SERIAL)[1], 7)
        target = self.root / 'local_camera_1.json'
        victim = self.root / 'victim'
        victim.write_text('retain')
        target.symlink_to(victim)
        self.assertEqual(self.call(self.payload | {'replace': True})[0], 400)
        self.assertEqual(victim.read_text(), 'retain')


class AcquisitionAdapterTests(unittest.TestCase):
    def test_real_sdk_export_import_and_key_representation(self):
        try:
            from pyezvizapi.hcnetsdk import EzvizCasDeviceInfo, HcNetSdkLanEndpoint
            from pyezvizapi.local_stream_transport import EzvizLocalSdkCredentials
        except ImportError:
            self.skipTest('Pinned SDK is exercised inside the built DEV image')
        endpoint = HcNetSdkLanEndpoint(SERIAL, '192.168.10.140', command_port=9010, stream_port=9020)
        device = EzvizCasDeviceInfo(SERIAL, 'PRIVATE-OP', SECRET)
        credentials = EzvizLocalSdkCredentials(endpoint, device)
        self.assertEqual(device.key_bytes, SECRET.encode())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install_data(credentials.as_dict(), root, SERIAL, 7, 1)
            self.assertEqual(read_credentials(root / 'local_camera_1.json', SERIAL), ('192.168.10.140', 7))



if __name__ == '__main__':
    unittest.main()
