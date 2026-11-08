"""Check Supervisor/tag alignment and the published multiarch contract."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_metadata import metadata
from check_dev_manifest import check


class ReleaseTests(unittest.TestCase):
    def test_supervisor_and_ci_read_same_image_and_version(self):
        release = metadata(ROOT, 'ezviz_bc1_w2h_dev')
        self.assertEqual(release, {'version': '0.3.7', 'image': 'ghcr.io/artepe/ezviz-bc1-w2h'})
        stable = metadata(ROOT)
        self.assertNotEqual(stable['version'], release['version'])
        config = (ROOT / 'ezviz_bc1_w2h_dev/config.yaml').read_text()
        self.assertIn('slug: "ezviz_bc1_w2h_dev"', config)
        self.assertIn('host_network: true', config)
        self.assertFalse((ROOT / 'ezviz_bc1_w2h_dev/build.yaml').exists())
        self.assertFalse((ROOT / 'ezviz_bc1_w2h_dev/build.yml').exists())

    def test_index_requires_exactly_the_two_supported_architectures(self):
        def index(arches):
            return {'manifests': [{'platform': {'os': 'linux', 'architecture': arch}} for arch in arches]}
        check(index(['arm64', 'amd64']))
        for arches in ([], ['amd64'], ['arm64'], ['amd64', 'amd64'], ['amd64', 'arm64', 'unknown']):
            with self.subTest(arches=arches), self.assertRaises(ValueError):
                check(index(arches))


if __name__ == '__main__':
    unittest.main()
