"""One-shot owner-authorized SDK bootstrap. Secrets travel on stdin only.

No existing cloud session files are opened, refreshed, saved or removed.
The parent imposes a deadline and discards all stderr.
"""
import json
import ipaddress
import logging
import signal
import sys


class LookupFailure(Exception):
    def __init__(self, code, diagnostic=None):
        self.code = code
        self.diagnostic = diagnostic


LAN_CODES = ('CAMERA_RECORD_MISSING', 'CONNECTION_MISSING', 'LOCAL_IP_MISSING',
             'LAN_ENDPOINT_INVALID', 'LAN_METADATA_REQUEST_FAILED')


def lan_endpoint(client, serial, use_known=False):
    """Never retain WAN addresses from cloud metadata in a local endpoint."""
    from pyezvizapi.hcnetsdk import HcNetSdkLanEndpoint
    def fail(code):
        raise LookupFailure(20, {'stage': 'lan_metadata', 'error_code': code})
    if type(use_known) is not bool:
        fail('LAN_ENDPOINT_INVALID')
    if use_known:
        return HcNetSdkLanEndpoint(serial, '192.168.10.140', command_port=9010, stream_port=9020)
    try:
        records = client.get_device_infos(serial)
    except Exception:
        fail('LAN_METADATA_REQUEST_FAILED')
    if not isinstance(records, dict) or not records:
        fail('CAMERA_RECORD_MISSING')
    record = records.get(serial, records)
    if not isinstance(record, dict) or not record:
        fail('CAMERA_RECORD_MISSING')
    connection = record.get('CONNECTION')
    if not isinstance(connection, dict) or not connection:
        fail('CONNECTION_MISSING')
    host = connection.get('localIp')
    if not isinstance(host, str) or not host.strip():
        fail('LOCAL_IP_MISSING')
    try:
        address = ipaddress.IPv4Address(host.strip())
        private = any(address in ipaddress.IPv4Network(net) for net in
                      ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
        if not private or connection.get('localCmdPort', 9010) != 9010 or connection.get('localStreamPort', 9020) != 9020:
            fail('LAN_ENDPOINT_INVALID')
    except ValueError:
        fail('LAN_ENDPOINT_INVALID')
    return HcNetSdkLanEndpoint(serial, str(address), command_port=9010, stream_port=9020)


def acquire(payload):
    from pyezvizapi.client import EzvizClient
    from pyezvizapi.exceptions import EzvizAuthVerificationCode
    from pyezvizapi.local_stream_transport import EzvizLocalSdkCredentials
    from pyezvizapi.hcnetsdk import EzvizCasDeviceInfo
    from pyezvizapi.cas import EzvizCAS, CasDeviceSession

    client = EzvizClient(payload['username'], payload['password'], url=payload['api_url'], timeout=15)
    code = payload.get('sms_code')
    try:
        client.login(sms_code=int(code) if code else None)
    except EzvizAuthVerificationCode:
        raise LookupFailure(10) from None
    except Exception:
        raise LookupFailure(11) from None
    source = 'observed_override' if payload.get('cas_serial') else 'selected_camera'
    def run(stage, code, operation):
        # Bound each stage so a stalled P2P/CAS request keeps its stage diagnostic.
        def expired(signum, frame):
            raise TimeoutError
        previous = signal.signal(signal.SIGALRM, expired)
        signal.alarm(12)
        try:
            return operation()
        except LookupFailure as error:
            error.diagnostic['cas_identity'] = source
            raise
        except Exception as error:
            # Never stringify upstream exceptions: they can contain entire responses.
            diagnostic = {'stage': stage, 'cas_identity': source, 'error_code': {
                'lan_metadata': 'LAN_METADATA_REQUEST_FAILED',
                'p2p_registration': 'P2P_REGISTRATION_FAILED', 'cas_lookup': 'CAS_REQUEST_FAILED'}[stage]}
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if type(status) is int and 100 <= status <= 599:
                diagnostic['http_status'] = status
            raise LookupFailure(code, diagnostic) from None
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    endpoint = run('lan_metadata', 20, lambda: lan_endpoint(client, payload['serial'], payload.get('use_known_w2h', False)))
    run('p2p_registration', 21, lambda: client.register_p2p_session(max_retries=1))
    response = run('cas_lookup', 22, lambda: EzvizCAS(client.export_token()).cas_get_encryption(
        payload.get('cas_serial') or payload['serial']))
    body = response.get('Response') if isinstance(response, dict) else None
    diagnostic = {'stage': 'cas_lookup', 'cas_identity': source, 'error_code': 'CAS_SESSION_INVALID'}
    if isinstance(body, dict):
        value = body.get('Result')
        if type(value) is int and -2147483648 <= value <= 2147483647:
            diagnostic['result_code'] = value
        elif isinstance(value, str) and len(value) <= 11 and value.isascii() and value.lstrip('-').isdigit():
            number = int(value)
            if -2147483648 <= number <= 2147483647:
                diagnostic['result_code'] = number
        diagnostic['session_present'] = isinstance(body.get('Session'), dict)
    try:
        session = CasDeviceSession.from_response(response)
        credentials = EzvizLocalSdkCredentials(endpoint=endpoint, device_info=EzvizCasDeviceInfo(
            serial=payload['serial'], operation_code=session.operation_code,
            key=session.key, encrypt_type=session.encrypt_type))
        return credentials.as_dict(include_media_key=False)
    except Exception:
        raise LookupFailure(22, diagnostic) from None


def main():
    logging.disable(logging.CRITICAL)
    try:
        payload = json.loads(sys.stdin.buffer.read(32769))
        result = acquire(payload)
        sys.stdout.write(json.dumps(result))
        return 0
    except LookupFailure as error:
        if error.diagnostic is not None:
            sys.stdout.write(json.dumps(error.diagnostic))
        return error.code
    except Exception:
        # Upstream exceptions can contain keys, tokens and account details.
        return 1



def safe_failure(exit_code, raw):
    """Validate the child boundary before rendering any diagnostic in ingress."""
    stages = {20: 'lan_metadata', 21: 'p2p_registration', 22: 'cas_lookup'}
    stage = stages[exit_code]
    try:
        data = json.loads(raw) if len(raw) <= 2048 else {}
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict) or data.get('stage') != stage:
        data = {}
    result = {'ok': False, 'stage': stage, 'exit_code': exit_code}
    message = f'EZVIZ acquisition failed at {stage} (exit {exit_code}).'
    allowed = {'lan_metadata': LAN_CODES, 'p2p_registration': ('P2P_REGISTRATION_FAILED',),
               'cas_lookup': ('CAS_REQUEST_FAILED', 'CAS_SESSION_INVALID')}
    error_code = data.get('error_code')
    if error_code in allowed[stage]:
        result['error_code'] = error_code
        message += f' Code={error_code}.'

    value = data.get('result_code')
    if type(value) is int and -2147483648 <= value <= 2147483647:
        result['result_code'] = value
        message += f' Result={value}.'
    if stage == 'cas_lookup' and data.get('session_present') is False:
        result['session_present'] = False
        message += ' CAS response is missing Session; no credentials were issued.'
    status = data.get('http_status')
    if type(status) is int and 100 <= status <= 599:
        result['http_status'] = status
        message += f' HTTP status={status}.'
    source = data.get('cas_identity')
    if source in ('selected_camera', 'observed_override'):
        result['cas_identity'] = source
        message += f' CAS DevSerial source: {source}.'
    result['message'] = message + ' No credentials were installed.'
    return result

if __name__ == '__main__':
    raise SystemExit(main())
