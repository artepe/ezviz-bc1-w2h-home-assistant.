"""Only fixed labels and booleans cross the diagnostic boundary."""
MESSAGES = {
    'MISSING_CREDENTIALS': 'Private local credential file is missing. No W2H connection was attempted.',
    'INVALID_CREDENTIALS': 'Local credential file is unreadable, unsafe or malformed. No successful authorization is established.',
    'LAN_CONNECT_FAILED': 'A TCP connection attempt to the configured W2H endpoint failed.',
    'CAS_AUTH_FAILED': 'Explicit CAS authentication rejection confirmed.',
    'CHANNEL_INVALID': 'Configured channel is not an integer in 1..256. Device channel existence remains unconfirmed.',
    'MEDIA_TIMEOUT': 'Stream setup completed, but no SDK media frame arrived before the startup deadline.',
    'MPEGTS_INVALID': 'Output does not contain two complete MPEG-TS packets with valid sync spacing.',
    'UNKNOWN': 'The available evidence does not identify the failing stage.',
}
EXIT_CODES = {21: 'UNKNOWN', 22: 'UNKNOWN', 23: 'UNKNOWN', 24: 'INVALID_CREDENTIALS'}
EVENTS = frozenset({'TCP_CONNECTED', 'TCP_CONNECT_FAILED', 'PREVIEW_ACCEPTED', 'STREAM_SETUP', 'MEDIA_FRAME'})

class LocalCredentialError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])

def error_payload(code):
    return ('LOCAL_ERROR:' + (code if code in MESSAGES else 'UNKNOWN') + '\n').encode('ascii')

def explain_local_error(payload, status=503):
    if status == 409:
        return 'HTTP 409 [LOCAL_BUSY]: This camera already has a local viewer. Close it before testing again.'
    if status != 503:
        return f'HTTP {status} [UNKNOWN]: Local proxy request failed; upstream details are hidden.'
    for code, message in MESSAGES.items():
        if payload == error_payload(code):
            return f'HTTP 503 [{code}]: {message} Cloud access is disabled.'
    return 'HTTP 503 [UNKNOWN]: No recognized local diagnostic. Cloud access is disabled.'

def credential_status(path, serial):
    """Run inside the add-on; never return credential values or exceptions."""
    from local_capture import read_credentials
    try:
        path.lstat()
    except FileNotFoundError:
        return {'exists': False, 'validation': 'MISSING_CREDENTIALS'}
    except OSError:
        return {'exists': None, 'validation': 'UNKNOWN'}
    try:
        read_credentials(path, serial)
    except LocalCredentialError as error:
        return {'exists': True, 'validation': error.code}
    except Exception:
        return {'exists': True, 'validation': 'UNKNOWN'}
    return {'exists': True, 'validation': 'FORMAT_VALID'}

def read_events(source):
    import os
    # pread does not disturb the offset shared with the child writer.
    raw = os.pread(source.fileno(), 4096, 0)
    return set(raw.decode('ascii', errors='ignore').splitlines()) & EVENTS

def failure_code(events, first, exit_code, deadline_expired=False):
    if first:
        return 'MPEGTS_INVALID'
    if 'TCP_CONNECT_FAILED' in events:
        return 'LAN_CONNECT_FAILED'
    if deadline_expired and 'PREVIEW_ACCEPTED' in events and 'STREAM_SETUP' in events and 'MEDIA_FRAME' not in events:
        return 'MEDIA_TIMEOUT'
    return EXIT_CODES.get(exit_code, 'UNKNOWN')
