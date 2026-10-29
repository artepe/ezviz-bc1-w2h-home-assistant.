"""Offline safety and failover contract tests for optional hybrid endpoint."""
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "ezviz_bc1_w2h"
spec = importlib.util.spec_from_file_location("hybrid_proxy", ROOT / "hybrid_proxy.py")
hybrid = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hybrid
spec.loader.exec_module(hybrid)


class HybridTests(unittest.TestCase):
    def test_private_ipv4_only(self):
        self.assertEqual(hybrid.local_ipv4("192.168.10.138"), "192.168.10.138")
        for address in ("", "127.0.0.1", "169.254.1.2", "8.8.8.8", "not-an-ip", None):
            self.assertEqual(hybrid.local_ipv4(address), "")

    def test_local_command_does_not_leak_or_add_account_password(self):
        class Worker:
            token = Path("/tmp/nonexistent-should-not-exist-token")
            serial = "G23915155-G28068598"
        worker = Worker()
        with patch.object(hybrid.Path, "is_file", return_value=True), patch.object(hybrid, "lan_client_address", return_value="192.168.10.10"):
            service = object.__new__(hybrid.HybridService)
            command = service.local_command(worker, "192.168.10.138", "")
        self.assertIn("--fetch-cas", command)
        self.assertEqual(command[command.index("--cas-serial")+1], "G23915155")
        self.assertEqual(command[command.index("--inner-address")+1], "192.168.10.10")
        self.assertNotIn("--password", command)
        self.assertNotIn("--save-token", command)

    def test_cloud_source_is_only_loopback_to_existing_worker(self):
        class Worker:
            port = 8558
            serial = "G23915155-G28068598"
        class Response:
            def read(self, _size):
                return bytes([0x47]) + b"data"
        with patch.object(hybrid, "urlopen", return_value=Response()) as opener:
            service = object.__new__(hybrid.HybridService)
            stream = service.open_cloud(Worker())
        self.assertEqual(stream[1][0], 0x47)
        self.assertEqual(opener.call_args.args[0], "http://127.0.0.1:8558/G23915155-G28068598.ts")

    def test_local_failure_cooldown(self):
        service = object.__new__(hybrid.HybridService)
        import threading
        service.lock = threading.RLock()
        service.cooldowns = {}
        service.last_result = {}
        service.mark_lan_failure("G28068598")
        self.assertGreater(service.cooldowns["G28068598"], hybrid.time.monotonic()+250)
        self.assertEqual(service.last_result["G28068598"], "local_unavailable")


if __name__ == "__main__":
    unittest.main()
