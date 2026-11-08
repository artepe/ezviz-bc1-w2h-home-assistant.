"""One-shot owner-authorized SDK bootstrap. Secrets travel on stdin only.

No existing cloud session files are opened, refreshed, saved or removed.
The parent imposes a deadline and discards all stderr.
"""
import json
import logging
import sys


class LookupFailure(Exception):
    def __init__(self, code):
        self.code = code


def acquire(payload):
    from pyezvizapi.client import EzvizClient
    from pyezvizapi.exceptions import EzvizAuthVerificationCode
    from pyezvizapi.local_stream_transport import get_local_sdk_stream_credentials_from_client

    client = EzvizClient(payload['username'], payload['password'], url=payload['api_url'], timeout=15)
    code = payload.get('sms_code')
    try:
        client.login(sms_code=int(code) if code else None)
    except EzvizAuthVerificationCode:
        raise LookupFailure(10) from None
    except Exception:
        raise LookupFailure(11) from None
    try:
        credentials = get_local_sdk_stream_credentials_from_client(
            client, payload['serial'], cas_serial=payload.get('cas_serial') or None,
            fetch_media_key=False, register_p2p_session=True, p2p_register_max_retries=1,
        )
    except Exception:
        raise LookupFailure(12) from None
    return credentials.as_dict(include_media_key=False)


def main():
    logging.disable(logging.CRITICAL)
    try:
        payload = json.loads(sys.stdin.buffer.read(32769))
        result = acquire(payload)
        sys.stdout.write(json.dumps(result))
        return 0
    except LookupFailure as error:
        return error.code
    except Exception:
        # Upstream exceptions can contain keys, tokens and account details.
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
