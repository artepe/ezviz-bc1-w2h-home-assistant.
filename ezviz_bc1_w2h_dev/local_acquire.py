"""One-shot owner-authorized SDK bootstrap. Secrets travel on stdin only.

No existing cloud session files are opened, refreshed, saved or removed.
The parent imposes a deadline and discards all stderr.
"""
import json
import logging
import sys


class LookupFailure(Exception):
    def __init__(self, code, diagnostic=None):
        self.code = code
        self.diagnostic = diagnostic


def acquire(payload):
    from pyezvizapi.client import EzvizClient
    from pyezvizapi.exceptions import EzvizAuthVerificationCode
    from pyezvizapi._local_stream import _local_sdk_endpoint_from_client
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
        try:
            return operation()
        except Exception as error:
            # Never stringify upstream exceptions: they can contain entire responses.
            diagnostic = {'stage': stage, 'cas_identity': source}
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if type(status) is int and 100 <= status <= 599:
                diagnostic['http_status'] = status
            raise LookupFailure(code, diagnostic) from None

    endpoint = run('lan_metadata', 20, lambda: _local_sdk_endpoint_from_client(client, payload['serial']))
    run('p2p_registration', 21, lambda: client.register_p2p_session(max_retries=1))
    response = run('cas_lookup', 22, lambda: EzvizCAS(client.export_token()).cas_get_encryption(
        payload.get('cas_serial') or payload['serial']))
    body = response.get('Response') if isinstance(response, dict) else None
    diagnostic = {'stage': 'cas_lookup', 'cas_identity': source}
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
    except Exception:
        raise LookupFailure(22, diagnostic) from None
    credentials = EzvizLocalSdkCredentials(endpoint=endpoint, device_info=EzvizCasDeviceInfo(
        serial=payload['serial'], operation_code=session.operation_code,
        key=session.key, encrypt_type=session.encrypt_type))
    return credentials.as_dict(include_media_key=False)


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
