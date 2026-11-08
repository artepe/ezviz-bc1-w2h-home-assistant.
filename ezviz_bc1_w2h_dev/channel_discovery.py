"""Read-only channel candidates from an existing authorized session.

Open Platform accessToken and consumer session_id are distinct credentials.
Never log responses, refresh/login, infer channels from order, or prove SDK mapping.
"""
import argparse
from contextlib import suppress
import json
import logging
from pathlib import Path
import sys

OPEN_HOSTS = {host: 'https://' + host for host in
              ('isgpopen.ezvizlife.com', 'iusopen.ezvizlife.com', 'open.ys7.com')}


def candidates(data, serial, source):
    hub, ipc = serial.split('-', 1)
    found = set()

    def walk(value, matched=False):
        if isinstance(value, list):
            for item in value:
                walk(item, matched)
        elif isinstance(value, dict):
            # Explicit IPC identity takes precedence over an enclosing record.
            identity = value.get('ipcSerial')
            device = value.get('deviceSerial')
            if identity is not None:
                matched = identity in (ipc, serial) and device in (None, hub, serial)
            elif device is not None:
                matched = device == serial
            fields = ('channelNo',) if source == 'Open Platform channelNo' else ('channelNo', 'channel', 'channelId')
            for field in fields:
                number = value.get(field)
                if matched and type(number) is int and 1 <= number <= 256:
                    found.add(number)
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    walk(child, matched or key == serial)
    walk(data)
    return [{'channel': number, 'source': source, 'verified': False} for number in sorted(found)]


def discover(token_path, serial, region, open_token_path=None):
    result = {'ok': True, 'serial': serial, 'candidates': [], 'status': [],
              'sdk_mapping_verified': False}
    # Optional Open Platform token is provisioned privately, never supplied in URLs/UI.
    if open_token_path is not None and open_token_path.is_file():
        try:
            import requests
            token = json.loads(open_token_path.read_text())['accessToken']
            if not isinstance(token, str) or not token:
                raise ValueError
            response = requests.post(OPEN_HOSTS[region] + '/api/lapp/device/camera/list',
                                     data={'accessToken': token, 'deviceSerial': serial.split('-', 1)[0]},
                                     timeout=12, allow_redirects=False)
            response.raise_for_status()
            body = response.json()
            if str(body.get('code')) != '200':
                raise ValueError
            result['candidates'] += candidates(body.get('data'), serial, 'Open Platform channelNo')
            result['status'].append('OPEN_OK')
        except Exception:
            result['status'].append('OPEN_LOOKUP_FAILED')
    else:
        result['status'].append('OPEN_TOKEN_MISSING')
    client = None
    try:
        token = json.loads(token_path.read_text())
        if not isinstance(token, dict) or not token.get('session_id'):
            raise ValueError
        from pyezvizapi.client import EzvizClient
        class ExistingSessionClient(EzvizClient):
            def login(self, *args, **kwargs):
                raise ValueError('Session renewal disabled')

            def _login(self, *args, **kwargs):
                raise ValueError('Session renewal disabled')

        client = ExistingSessionClient(token=token, timeout=12)
        # Do not invoke login or refresh; metadata calls use this saved owner session.
        metadata = client.get_device_infos()
        result['candidates'] += candidates(metadata, serial, 'pyEzvizApi device metadata')
        result['status'].append('METADATA_OK')
        try:
            managed = client.get_managed_device_ipcs(serial.split('-', 1)[0], max_retries=0)
            result['candidates'] += candidates(managed, serial, 'pyEzvizApi managed IPC metadata')
            result['status'].append('MANAGED_OK')
        except Exception:
            result['status'].append('MANAGED_LOOKUP_FAILED')
    except FileNotFoundError:
        result['status'].append('SESSION_MISSING')
    except Exception:
        result['status'].append('METADATA_LOOKUP_FAILED')
    finally:
        if client is not None:
            with suppress(Exception):
                client.close_session()
    numbers = {item['channel'] for item in result['candidates']}
    result['conflict'] = len(numbers) > 1
    return result


def safe_result(outcome, serial):
    statuses = {'OPEN_OK', 'OPEN_LOOKUP_FAILED', 'OPEN_TOKEN_MISSING', 'METADATA_OK',
                'MANAGED_OK', 'MANAGED_LOOKUP_FAILED', 'SESSION_MISSING',
                'METADATA_LOOKUP_FAILED', 'LOOKUP_FAILED'}
    sources = {'Open Platform channelNo', 'pyEzvizApi device metadata', 'pyEzvizApi managed IPC metadata'}
    items = [{'channel': x['channel'], 'source': x['source'], 'verified': False}
             for x in outcome.get('candidates', []) if isinstance(x, dict)
             and type(x.get('channel')) is int and 1 <= x['channel'] <= 256
             and x.get('source') in sources]
    return {'ok': True, 'serial': serial, 'candidates': items,
            'status': [x for x in outcome.get('status', []) if x in statuses],
            'conflict': len({x['channel'] for x in items}) > 1,
            'sdk_mapping_verified': False}


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--region', choices=OPEN_HOSTS, default='isgpopen.ezvizlife.com')
    args = parser.parse_args()
    try:
        result = discover(args.directory / 'ezviz_token.json', args.serial, args.region,
                          args.directory / 'ezviz_open_token.json')
    except Exception:
        result = {'ok': False, 'status': ['LOOKUP_FAILED']}
    sys.stdout.write(json.dumps(result))


if __name__ == '__main__':
    main()
