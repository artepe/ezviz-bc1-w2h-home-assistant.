"""Offline acquisition regression coverage using the exact pinned SDK."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ezviz_bc1_w2h_dev'))
import local_acquire as acquire


class Stages(unittest.TestCase):
    def setUp(self):
        try:
            import pyezvizapi.cas
        except ImportError:
            self.skipTest('Pinned SDK exercised in image')
        self.payload = dict(username='owner', password='SECRET', api_url='apiieu.ezvizlife.com', serial='HUB-CAMERA')
        self.client = Mock()
        self.login = patch('pyezvizapi.client.EzvizClient', return_value=self.client)
        self.endpoint = patch('local_acquire.lan_endpoint', return_value=Mock())
        self.cas = patch('pyezvizapi.cas.EzvizCAS')
        self.login.start()
        self.endpoint_mock = self.endpoint.start()
        self.cas_mock = self.cas.start()
        self.addCleanup(patch.stopall)

    def test_stages_stop_at_failure_and_hide_exception(self):
        for stage, code in [('lan_metadata', 20), ('p2p_registration', 21), ('cas_lookup', 22)]:
            self.endpoint_mock.side_effect = None
            self.client.register_p2p_session.side_effect = None
            self.cas_mock.return_value.cas_get_encryption.side_effect = None
            target = {'lan_metadata': self.endpoint_mock, 'p2p_registration': self.client.register_p2p_session,
                      'cas_lookup': self.cas_mock.return_value.cas_get_encryption}[stage]
            target.side_effect = RuntimeError('SECRET encrypted-response TOKEN')
            with self.assertRaises(acquire.LookupFailure) as caught:
                acquire.acquire(self.payload)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.diagnostic['stage'], stage)
            self.assertNotIn('SECRET', json.dumps(caught.exception.diagnostic))

    def test_stalled_p2p_preserves_stage_and_restores_alarm(self):
        import signal
        previous = signal.getsignal(signal.SIGALRM)
        def stalled(**kwargs):
            signal.raise_signal(signal.SIGALRM)
        self.client.register_p2p_session.side_effect = stalled
        with self.assertRaises(acquire.LookupFailure) as caught:
            acquire.acquire(self.payload)
        self.assertEqual(caught.exception.code, 21)
        self.assertEqual(caught.exception.diagnostic['error_code'], 'P2P_REGISTRATION_FAILED')
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.alarm(0), 0)
        self.cas_mock.assert_not_called()

    def test_cas_1052170_and_exact_devserial_no_fallback(self):
        self.cas_mock.return_value.cas_get_encryption.return_value = {'Response': {'Result': '1052170', 'Limit': 'SECRET'}}
        for override in ('', 'OBSERVED-HUB'):
            with self.assertRaises(acquire.LookupFailure) as caught:
                acquire.acquire(self.payload | {'cas_serial': override})
            detail = caught.exception.diagnostic
            self.assertEqual(detail['result_code'], 1052170)
            self.assertIs(detail['session_present'], False)
            self.cas_mock.return_value.cas_get_encryption.assert_called_with(override or 'HUB-CAMERA')
            self.assertNotIn('SECRET', json.dumps(detail))
        self.assertEqual(self.cas_mock.return_value.cas_get_encryption.call_count, 2)
        self.client.register_p2p_session.assert_called_with(max_retries=1)
        self.client.logout.assert_not_called()

    def test_known_endpoint_reaches_p2p_and_cas_without_metadata(self):
        self.endpoint.stop()
        self.client.get_device_infos.side_effect = AssertionError('metadata bypass')
        self.cas_mock.return_value.cas_get_encryption.return_value = {'Response': {'Result': 1052170}}
        with self.assertRaises(acquire.LookupFailure) as caught:
            acquire.acquire(self.payload | {'use_known_w2h': True})
        self.assertEqual(caught.exception.code, 22)
        self.assertEqual(caught.exception.diagnostic['result_code'], 1052170)
        self.client.get_device_infos.assert_not_called()
        self.client.register_p2p_session.assert_called_once_with(max_retries=1)
        self.cas_mock.return_value.cas_get_encryption.assert_called_once_with('HUB-CAMERA')

    def test_success_uses_sdk_format_without_media_key(self):
        from pyezvizapi.hcnetsdk import HcNetSdkLanEndpoint
        self.endpoint_mock.return_value = HcNetSdkLanEndpoint('HUB-CAMERA', '192.168.1.2')
        self.cas_mock.return_value.cas_get_encryption.return_value = {'Response': {'Session': {
            '@Key': 'secret-16-bytes!', '@OperationCode': 'PRIVATE', '@Algorithm': 'AES128'}}}
        result = acquire.acquire(self.payload)
        self.assertEqual(result['serial'], 'HUB-CAMERA')
        self.assertNotIn('media_key', result)
        self.client.get_cam_key.assert_not_called()


class Boundary(unittest.TestCase):
    def test_only_numeric_result_and_fixed_fields_cross_boundary(self):
        for raw in (b'SECRET', b'[]', json.dumps({'stage': 'cas_lookup', 'result_code': 'SECRET',
                    'cas_identity': 'SECRET', 'message': 'SECRET', 'session_present': False}).encode()):
            result = acquire.safe_failure(22, raw)
            self.assertNotIn('SECRET', json.dumps(result))
        result = acquire.safe_failure(22, json.dumps({'stage': 'cas_lookup', 'result_code': 1052170,
                     'session_present': False, 'cas_identity': 'selected_camera'}))
        self.assertIn('1052170', result['message'])
        self.assertIn('missing Session', result['message'])


class LanMetadata(unittest.TestCase):
    def setUp(self):
        try:
            import pyezvizapi.hcnetsdk
        except ImportError:
            self.skipTest('Pinned SDK exercised in image')
        self.client = Mock()

    def test_exact_missing_component_and_safe_boundary(self):
        for record, code in (({}, 'CAMERA_RECORD_MISSING'),
                ({'deviceInfos': {}}, 'CONNECTION_MISSING'),
                ({'CONNECTION': {}}, 'CONNECTION_MISSING'),
                ({'CONNECTION': {'localCmdPort': 9010}}, 'LOCAL_IP_MISSING'),
                ({'CONNECTION': {'localIp': ' '}}, 'LOCAL_IP_MISSING')):
            self.client.get_device_infos.return_value = record
            with self.assertRaises(acquire.LookupFailure) as caught:
                acquire.lan_endpoint(self.client, 'HUB-CAMERA')
            self.assertEqual(caught.exception.diagnostic['error_code'], code)
            result = acquire.safe_failure(20, json.dumps(caught.exception.diagnostic))
            self.assertEqual(result['error_code'], code)

    def test_known_endpoint_bypasses_metadata_without_wan_fields(self):
        self.client.get_device_infos.side_effect = AssertionError('must bypass')
        endpoint = acquire.lan_endpoint(self.client, 'HUB-CAMERA', True)
        self.assertEqual((endpoint.host, endpoint.command_port, endpoint.stream_port),
                         ('192.168.10.140', 9010, 9020))
        self.assertIsNone(endpoint.net_host)
        self.client.get_device_infos.assert_not_called()
        for consent in ('true', 1, None):
            with self.assertRaises(acquire.LookupFailure):
                acquire.lan_endpoint(self.client, 'HUB-CAMERA', consent)

    def test_metadata_never_uses_public_or_unexpected_endpoints(self):
        for host in ('8.8.8.8', 'attacker.example', '127.0.0.1', '169.254.1.2', '::1'):
            self.client.get_device_infos.return_value = {'CONNECTION': {'localIp': host}}
            with self.assertRaises(acquire.LookupFailure) as caught:
                acquire.lan_endpoint(self.client, 'HUB-CAMERA')
            self.assertEqual(caught.exception.diagnostic['error_code'], 'LAN_ENDPOINT_INVALID')
        self.client.get_device_infos.return_value = {'CONNECTION': {
            'localIp': '192.168.10.140', 'netIp': '8.8.8.8', 'netCmdPort': 8000}}
        endpoint = acquire.lan_endpoint(self.client, 'HUB-CAMERA')
        self.assertIsNone(endpoint.net_host)
        self.assertEqual(endpoint.command_port, 9010)
