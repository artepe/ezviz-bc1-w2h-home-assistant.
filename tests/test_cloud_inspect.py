"""Cloud diagnostics must start the actual media stream without exporting bodies."""

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ezviz_bc1_w2h"))
from cloud_inspect import collect_packet_metadata


class CloudPacketProbeTests(unittest.TestCase):
    def test_starts_real_stream_and_keeps_media_bytes_out_of_metadata(self):
        stream = Mock()
        stream.iter_packets.return_value = [
            SimpleNamespace(body=b"PRIVATE_VIDEO", encrypted=False),
            SimpleNamespace(body=b"PRIVATE_TOKEN", encrypted=True),
        ]
        cloud = ModuleType("pyezvizapi.cloud_stream")
        cloud.open_cloud_stream = Mock(return_value=stream)
        transport = ModuleType("pyezvizapi.stream_transport")
        def summarize(packet, *, index):
            return SimpleNamespace(as_dict=lambda: {
                "index": index,
                "channel_name": "STREAM",
                "transport": "RTP" if index == 0 else "UNKNOWN",
                "encrypted": packet.encrypted,
            })
        transport.summarize_vtm_packet = summarize
        package = ModuleType("pyezvizapi")
        package.__path__ = []
        with patch.dict(sys.modules, {
            "pyezvizapi": package,
            "pyezvizapi.cloud_stream": cloud,
            "pyezvizapi.stream_transport": transport,
        }):
            result = collect_packet_metadata(Mock(), "TEST-CAM")
        stream.start.assert_called_once()
        stream.iter_packets.assert_called_once()
        stream.close.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertNotIn("PRIVATE_VIDEO", repr(result))
        self.assertNotIn("PRIVATE_TOKEN", repr(result))
        self.assertEqual(result[1]["encrypted"], True)

    def test_closes_stream_after_failure(self):
        stream = Mock()
        stream.start.side_effect = RuntimeError("SECRET_URL")
        cloud = ModuleType("pyezvizapi.cloud_stream")
        cloud.open_cloud_stream = Mock(return_value=stream)
        transport = ModuleType("pyezvizapi.stream_transport")
        transport.summarize_vtm_packet = lambda packet, index: None
        package = ModuleType("pyezvizapi")
        package.__path__ = []
        with patch.dict(sys.modules, {
            "pyezvizapi": package,
            "pyezvizapi.cloud_stream": cloud,
            "pyezvizapi.stream_transport": transport,
        }), self.assertRaises(RuntimeError):
            collect_packet_metadata(Mock(), "TEST-CAM")
        stream.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
