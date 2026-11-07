"""Exercise the built image without network access or device credentials."""
import argparse
import json
import subprocess


def check(image, version, arch):
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    labels = info['Config']['Labels']
    assert info['Architecture'] == {'aarch64': 'arm64', 'amd64': 'amd64'}[arch]
    assert labels['io.hass.arch'] == arch
    assert labels['io.hass.version'] == version
    assert labels['org.opencontainers.image.version'] == version
    commands = [
        ['/opt/ezviz-venv/bin/python', '-m', 'pip', 'check'],
        ['/opt/ezviz-venv/bin/pyezvizapi', '--help'],
        ['/opt/ezviz-venv/bin/pyezvizapi', 'stream', 'local-sdk-dump', '--help'],
        ['/usr/bin/ffmpeg', '-version'],
        ['/usr/bin/ffprobe', '-version'],
        ['/opt/ezviz-venv/bin/python', '-c', '''
import sys
from pathlib import Path
sys.path.insert(0, '/app')
import camera_config, connection, runner, web, supervisor_client
import cloud_inspect, local_capture, local_proxy, media_probe, hybrid_proxy
import requests, xmltodict, cryptography, Crypto.Cipher.AES, paho.mqtt.client
from pyezvizapi.cloud_stream import open_cloud_stream
from pyezvizapi.stream_transport import summarize_vtm_packet
from pyezvizapi.local_stream_transport import open_local_sdk_stream
assert all(callable(function) for function in (open_cloud_stream, summarize_vtm_packet, open_local_sdk_stream))
assert connection.connection_mode({'connection_mode': 'local_only'}) == 'local_only'
assert 'connection-mode' in Path('/app/static/index.html').read_text()
'''],
    ]
    for command in commands:
        subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                        '--entrypoint', command[0], image, *command[1:]],
                       check=True, timeout=120)
    print(f'Container smoke tests passed: {image}, {arch}, version {version}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('version')
    parser.add_argument('arch', choices=('aarch64', 'amd64'))
    args = parser.parse_args()
    check(args.image, args.version, args.arch)
