"""Check the default s6 -> run.sh -> runner startup using synthetic env values.

Unlike the module/FFmpeg checks, this must not override the image entrypoint.
The container has no network, camera options, published ports or real secrets.
"""

import argparse
import json
import subprocess
import uuid


PROBE = r'''
import json
from pathlib import Path
import time

deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            command = (directory / 'cmdline').read_bytes().split(b'\0')
            if b'/app/runner.py' not in command:
                continue
            environment = dict(
                entry.split(b'=', 1)
                for entry in (directory / 'environ').read_bytes().split(b'\0')
                if b'=' in entry
            )
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        print(json.dumps({
            'runner_started': True,
            'supervisor_token_forwarded': environment.get(b'SUPERVISOR_TOKEN') == b'ezviz-startup-test-token',
            'app_version_forwarded': environment.get(b'APP_VERSION') == b'environment-smoke-test',
        }))
        raise SystemExit(0)
    time.sleep(0.2)
raise SystemExit('The runner did not start through the default s6 entrypoint')
'''


def check(image: str, report_only: bool = False) -> None:
    name = 'ezviz-startup-' + uuid.uuid4().hex[:12]
    try:
        subprocess.run([
            'docker', 'run', '--detach', '--platform', 'linux/arm64',
            '--name', name, '--network', 'none', '--tmpfs', '/data:mode=700',
            '--env', 'SUPERVISOR_TOKEN=ezviz-startup-test-token',
            '--env', 'APP_VERSION=environment-smoke-test', image,
        ], check=True, stdout=subprocess.DEVNULL, timeout=120)
        probe = subprocess.run([
            'docker', 'exec', '-i', name, '/opt/ezviz-venv/bin/python', '-',
        ], input=PROBE, text=True, capture_output=True, timeout=30, check=True)
        result = json.loads(probe.stdout)
        print(json.dumps({'image': image, **result}), flush=True)
        if not report_only and not all(result.values()):
            raise RuntimeError('The default container startup lost Supervisor/app environment values')
    except Exception:
        subprocess.run(['docker', 'logs', '--tail', '30', name], check=False, timeout=10)
        raise
    finally:
        subprocess.run(['docker', 'rm', '--force', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=15)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    check(args.image, args.report_only)
