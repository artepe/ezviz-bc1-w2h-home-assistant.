"""Credential import must not leak or overwrite working camera credentials."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ezviz_bc1_w2h_dev"))
from local_credentials import install, main
from local_capture import read_credentials


class ImportTests(unittest.TestCase):
    def test_import_matches_camera_and_preserves_existing_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private.json"
            data = {"serial": "HUB-CAM", "endpoint": {"host": "192.168.10.140"},
                    "cas": {"key": "test-key-1234567", "operation_code": "synthetic"},
                    "session_id": "must not copy", "media_key": "synthetic media"}
            source.write_text(json.dumps(data))
            source.chmod(0o600)
            install(source, root, "HUB-CAM", 7, 1)
            target = root / "local_camera_1.json"
            self.assertEqual(read_credentials(target, "HUB-CAM"), ("192.168.10.140", 7))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("session_id", json.loads(target.read_text()))
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                install(source, root, "HUB-CAM", 8, 1)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(list(root.glob(".local-import-*")), [])

    def test_rejections_never_print_source_secrets_or_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private.json"
            data = {"serial": "HUB-CAM", "endpoint": {"host": "192.168.10.140"},
                    "cas": {"key": "test-key-1234567", "operation_code": "SECRET"}}
            for change, mode in [({}, 0o644), ({"serial": "wrong"}, 0o600),
                                 ({"channel": 9}, 0o600), ({"cas": {"key": "SECRET"}}, 0o600)]:
                source.write_text(json.dumps(data | change))
                source.chmod(mode)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(["--source", str(source), "--directory", str(root),
                                   "--serial", "HUB-CAM", "--channel", "7", "--slot", "1"])
                self.assertEqual(result, 1)
                self.assertEqual(output.getvalue(), "LOCAL_IMPORT:INVALID_INPUT\n")
                self.assertFalse((root / "local_camera_1.json").exists())

    def test_base64_key_and_symlink_protection(self):
        import base64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private.json"
            source.write_text(json.dumps({"serial": "HUB-CAM", "endpoint": {"host": "192.168.10.140"},
                              "cas": {"key": base64.b64encode(bytes(16)).decode(), "operation_code": "synthetic"}}))
            source.chmod(0o600)
            link = root / "link.json"
            link.symlink_to(source)
            with self.assertRaises(OSError):
                install(link, root, "HUB-CAM", 7, 1)
            target = root / "local_camera_1.json"
            target.symlink_to(root / "absent")
            with self.assertRaises(FileExistsError):
                install(source, root, "HUB-CAM", 7, 1)
            target.unlink()
            install(source, root, "HUB-CAM", 7, 1)


if __name__ == "__main__":
    unittest.main()
