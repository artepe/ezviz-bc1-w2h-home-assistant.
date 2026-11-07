"""Reject missing or unexpected platforms in the published image index."""
import json
from pathlib import Path
import sys


def check(document):
    platforms = [(entry['platform']['os'], entry['platform']['architecture'])
                 for entry in document['manifests']]
    if sorted(platforms) != [('linux', 'amd64'), ('linux', 'arm64')]:
        raise ValueError('Expected exactly linux/amd64 and linux/arm64 in the image index')


if __name__ == '__main__':
    check(json.loads(Path(sys.argv[1]).read_text()))
    print('Published image index contains both required architectures.')
