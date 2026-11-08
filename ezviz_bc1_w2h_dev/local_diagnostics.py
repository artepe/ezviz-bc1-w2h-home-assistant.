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
MESSAGES.update({
    'PROCESS_START_FAILED': 'The local Python child could not be launched.',
    'SDK_IMPORT_FAILED': 'A required SDK Python module could not be imported.',
    'SDK_INITIALIZATION_FAILED': 'SDK initialization failed before its stream handler.',
    'SDK_ARGUMENT_FAILED': 'SDK command line parsing failed before connection.',
    'PREVIEW_FAILED': 'The preview exchange failed; CAS rejection is not established.',
    'STREAM_SETUP_FAILED': 'The stream setup exchange failed.',
    'SDK_FAILED': 'The SDK handler failed; consult confirmed stage flags.',
    'STARTUP_TIMEOUT': 'The startup deadline expired; consult confirmed stage flags.',
    'FFMPEG_MISSING': 'FFmpeg executable is unavailable.',
    'MEDIA_RECEIVE_FAILED': 'SDK media reception failed after stream setup; no media frame was confirmed.',
    'MEDIA_PROCESSING_FAILED': 'Media processing failed after a received SDK frame; conversion failure is not yet isolated.',
})
EXIT_CODES = {21: 'UNKNOWN', 22: 'UNKNOWN', 23: 'UNKNOWN', 24: 'INVALID_CREDENTIALS'}
EXIT_CODES.update({30: 'SDK_IMPORT_FAILED', 31: 'SDK_INITIALIZATION_FAILED', 32: 'SDK_ARGUMENT_FAILED', 33: 'FFMPEG_MISSING'})
EVENTS = frozenset({'PREVIEW_REJECTED', 'STREAM_SETUP_REJECTED', 'PREVIEW_SENT', 'PREVIEW_RESPONSE', 'STREAM_SETUP_SENT', 'STREAM_SETUP_ACCEPTED', 'TCP_9010_CONNECTED', 'TCP_9020_CONNECTED', 'TCP_9010_FAILED', 'TCP_9020_FAILED'}) | frozenset(MESSAGES) | frozenset({'PROCESS_STARTED', 'CREDENTIALS_READ', 'SDK_READY', 'HANDLER_STARTED', 'PREVIEW_REQUESTED', 'STREAM_SETUP_REQUESTED', 'TCP_CONNECTED', 'TCP_CONNECT_FAILED', 'PREVIEW_ACCEPTED', 'STREAM_SETUP', 'MEDIA_FRAME'})

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
    if 'TCP_CONNECT_FAILED' in events:
        return 'LAN_CONNECT_FAILED'
    for code in ('SDK_IMPORT_FAILED', 'SDK_INITIALIZATION_FAILED', 'SDK_ARGUMENT_FAILED', 'FFMPEG_MISSING', 'INVALID_CREDENTIALS', 'PREVIEW_FAILED', 'STREAM_SETUP_FAILED', 'MEDIA_PROCESSING_FAILED', 'MEDIA_RECEIVE_FAILED', 'MEDIA_TIMEOUT', 'SDK_FAILED'):
        if code in events:
            return code
    if first:
        return 'MPEGTS_INVALID'
    if deadline_expired and 'PREVIEW_ACCEPTED' in events and 'STREAM_SETUP' in events and 'MEDIA_FRAME' not in events:
        return 'MEDIA_TIMEOUT'
    if deadline_expired:
        return 'STARTUP_TIMEOUT'
    return EXIT_CODES.get(exit_code, 'UNKNOWN')


DEEP_STAGES = (
    ('Credentials loaded', 'CREDENTIALS_READ', ('MISSING_CREDENTIALS', 'INVALID_CREDENTIALS', 'CHANNEL_INVALID')),
    ('SDK process started', 'PROCESS_STARTED', ('PROCESS_START_FAILED',)),
    ('TCP 9010 connected', 'TCP_9010_CONNECTED', ('TCP_9010_FAILED',)),
    ('Preview request sent', 'PREVIEW_SENT', ()),
    ('Preview response 0x2012 received', 'PREVIEW_RESPONSE', ()),
    ('Preview accepted', 'PREVIEW_ACCEPTED', ('PREVIEW_REJECTED',)),
    ('Stream setup request sent', 'STREAM_SETUP_SENT', ()),
    ('Stream setup response 0x3106 received', 'STREAM_SETUP', ()),
    ('Stream setup accepted', 'STREAM_SETUP_ACCEPTED', ('STREAM_SETUP_REJECTED',)),
    ('TCP 9020 connected', 'TCP_9020_CONNECTED', ('TCP_9020_FAILED',)),
    ('Media packets received', 'MEDIA_FRAME', ()),
    ('MPEG-TS valid', 'MPEGTS_VALID', ('MPEGTS_INVALID',)),
    ('H.264 decoded', 'H264_DECODED', ('H264_DECODE_FAILED',)),
    ('Audio packets detected', 'AUDIO_PACKETS', ()),
)


def deep_result(events, reason):
    return {'ok': 'H264_DECODED' in events,
            'message': 'One local test completed: ' + reason,
            'stages': [{'label': label, 'status': 'CONFIRMED' if event in events else
                        'FAILED' if any(code in events for code in failures) else 'NOT_TESTED'}
                       for label, event, failures in DEEP_STAGES]}
