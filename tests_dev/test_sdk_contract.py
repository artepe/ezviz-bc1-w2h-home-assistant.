"""Exercise the pinned real CLI with synthetic data and no socket opening."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ezviz_bc1_w2h_dev'))
import local_capture
from local_diagnostics import failure_code


class SdkContractTests(unittest.TestCase):
    def test_real_cli_preserves_saved_endpoint_channel_and_cas_algorithm(self):
        try:
            import pyezvizapi.__main__ as cli
        except ImportError:
            self.skipTest('Pinned SDK is exercised in Docker CI')
        observed = []
        def stop_before_network(endpoint, device, request, **kwargs):
            observed.append((endpoint.host, endpoint.command_port, endpoint.stream_port,
                             request.channel, device.encrypt_type, device.key, device.operation_code))
            raise RuntimeError('SYNTHETIC_STOP_BEFORE_NETWORK')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_text(json.dumps({'serial': 'HUB-CAM', 'channel': 1,
                'endpoint': {'host': '192.168.10.140', 'command_port': 9010, 'stream_port': 9020},
                'cas': {'key': '0123456789abcdef', 'operation_code': 'SYNTHETIC', 'encrypt_type': 3}}))
            path.chmod(0o600)
            with patch.object(cli, 'open_local_sdk_stream', side_effect=stop_before_network), \
                 patch.object(local_capture, 'install_lan_guard'), \
                 patch.object(local_capture.shutil, 'which', return_value='/usr/bin/ffmpeg'), \
                 patch.object(local_capture.logging, 'disable'):
                self.assertEqual(local_capture.main([str(path), 'HUB-CAM']), 23)
        self.assertEqual(observed, [('192.168.10.140', 9010, 9020, 1, 3, '0123456789abcdef', 'SYNTHETIC')])

    def test_failure_labels_do_not_echo_exception_content(self):
        for code in ('SDK_IMPORT_FAILED', 'SDK_INITIALIZATION_FAILED', 'SDK_ARGUMENT_FAILED',
                     'FFMPEG_MISSING', 'PREVIEW_FAILED', 'STREAM_SETUP_FAILED', 'MEDIA_PROCESSING_FAILED', 'MEDIA_TIMEOUT'):
            self.assertEqual(failure_code({code}, b'', None), code)
        self.assertEqual(failure_code({'TCP_CONNECT_FAILED', 'PREVIEW_FAILED'}, b'', 22), 'LAN_CONNECT_FAILED')

    def test_invalid_cas_algorithm_is_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_text('{"cas":{"encrypt_type":"PRIVATE"}}')
            with self.assertRaises(local_capture.LocalCredentialError) as error:
                local_capture.credential_encrypt_type(path)
            self.assertNotIn('PRIVATE', str(error.exception))
