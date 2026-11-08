"""Identity, authorization and secret-boundary checks for channel discovery."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ezviz_bc1_w2h_dev'))
from channel_discovery import candidates, discover, safe_result
from test_web_credentials import WebCredentialTests, SERIAL


class MappingTests(unittest.TestCase):
    def test_exact_identity_and_no_order_or_channel_count_inference(self):
        data = [{'deviceSerial': 'HUB', 'ipcSerial': 'OTHER', 'channelNo': 3},
                {'deviceSerial': 'HUB', 'ipcSerial': 'CAM', 'channelNo': 8},
                {'deviceSerial': 'OTHER', 'ipcSerial': 'CAM', 'channelNo': 9},
                {'deviceSerial': 'HUB-CAM', 'channelNumber': 16},
                {'deviceSerial': 'HUB-CAM', 'channelNo': True},
                {'deviceSerial': 'HUB-CAM', 'channelNo': '7'}]
        self.assertEqual(candidates(data, 'HUB-CAM', 'test'),
                         [{'channel': 8, 'source': 'test', 'verified': False}])
        self.assertEqual(candidates(list(reversed(data)), 'HUB-CAM', 'test'),
                         candidates(data, 'HUB-CAM', 'test'))

    def test_metadata_parent_context_and_conflicts(self):
        data = {'HUB-CAM': {'CHANNEL': {'resource': {'channelNo': 8}},
                            'resourceInfos': [{'deviceSerial': 'HUB-CAM', 'channelNo': 9}],
                            'other': {'deviceSerial': 'HUB-OTHER', 'channelNo': 4}}}
        items = candidates(data, 'HUB-CAM', 'pyEzvizApi device metadata')
        self.assertEqual([x['channel'] for x in items], [8, 9])
        safe = safe_result({'candidates': items + [{'channel': 7, 'source': 'SECRET'}],
                            'status': ['METADATA_OK', 'PRIVATE-TOKEN']}, 'HUB-CAM')
        self.assertTrue(safe['conflict'])
        self.assertFalse(safe['sdk_mapping_verified'])
        self.assertNotIn('SECRET', json.dumps(safe))
        self.assertNotIn('PRIVATE-TOKEN', json.dumps(safe))

    def test_missing_session_is_explicit_and_never_guesses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = discover(root / 'absent', 'HUB-CAM', 'isgpopen.ezvizlife.com')
        self.assertEqual(result['candidates'], [])
        self.assertIn('SESSION_MISSING', result['status'])
        self.assertIn('OPEN_TOKEN_MISSING', result['status'])

    def test_open_platform_uses_distinct_token_fixed_host_and_no_redirect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token = root / 'open.json'
            token.write_text(json.dumps({'accessToken': 'PRIVATE-OPEN-TOKEN'}))
            response = Mock()
            response.json.return_value = {'code': '200', 'data': [
                {'deviceSerial': 'HUB', 'ipcSerial': 'CAM', 'channelNo': 8}]}
            request = Mock(return_value=response)
            with patch.dict(sys.modules, {'requests': SimpleNamespace(post=request)}):
                result = discover(root / 'missing', 'HUB-CAM', 'isgpopen.ezvizlife.com', token)
            args, kwargs = request.call_args
            self.assertEqual(args[0], 'https://isgpopen.ezvizlife.com/api/lapp/device/camera/list')
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(kwargs['data']['deviceSerial'], 'HUB')
            self.assertEqual(result['candidates'][0]['channel'], 8)
            self.assertNotIn('PRIVATE-OPEN-TOKEN', json.dumps(result))

    def test_sdk_renewal_is_blocked_and_saved_token_is_unchanged(self):
        class Client:
            def __init__(self, **kwargs):
                pass
            def get_device_infos(self):
                self.login()
            def close_session(self):
                pass
            def login(self):
                raise AssertionError('must never renew')
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / 'token.json'
            token.write_text('{"session_id":"PRIVATE-SESSION"}')
            before = token.read_bytes()
            with patch.dict(sys.modules, {'pyezvizapi': SimpleNamespace(),
                                          'pyezvizapi.client': SimpleNamespace(EzvizClient=Client)}):
                result = discover(token, 'HUB-CAM', 'isgpopen.ezvizlife.com')
            self.assertIn('METADATA_LOOKUP_FAILED', result['status'])
            self.assertEqual(before, token.read_bytes())
            self.assertNotIn('PRIVATE-SESSION', json.dumps(result))


class DiscoveryWebTests(WebCredentialTests):
    def test_discovery_requires_consent_and_does_not_install_or_reload(self):
        with patch('web.subprocess.run') as run:
            self.assertEqual(self.call({'action': 'discover'})[0], 400)
            run.assert_not_called()
        output = {'candidates': [{'channel': 8, 'source': 'Open Platform channelNo', 'verified': True}],
                  'status': ['OPEN_OK'], 'secret': 'PRIVATE-TOKEN'}
        with patch('web.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(output).encode())):
            status, body = self.call({'action': 'discover', 'allow_cloud': True})
        self.assertEqual(status, 200)
        self.assertEqual(body['serial'], SERIAL)
        self.assertFalse(body['candidates'][0]['verified'])
        self.assertFalse(body['sdk_mapping_verified'])
        self.assertFalse(self.runtime.reload.is_set())
        self.assertEqual(list(self.root.iterdir()), [])
