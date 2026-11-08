"""One private, bounded LAN capture; decode only its saved bytes, never a URL."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from hybrid_proxy import next_bytes, terminate
from local_diagnostics import LocalCredentialError, deep_result, failure_code, read_events

MAX_MEDIA = 8 * 1024 * 1024


def inspect_saved(path, events):
    """A track declaration alone proves neither packets nor decoded pictures."""
    try:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-f', 'mpegts',
            '-show_streams', '-count_packets', '-of', 'json', str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
        if probe.returncode or len(probe.stdout) > 65536:
            events.add('MPEGTS_INVALID')
            return
        streams = json.loads(probe.stdout).get('streams', [])
        if not streams:
            events.add('MPEGTS_INVALID')
            return
        events.add('MPEGTS_VALID')
        if any(s.get('codec_type') == 'audio' and int(s.get('nb_read_packets', 0)) > 0 for s in streams):
            events.add('AUDIO_PACKETS')
        video = next((s for s in streams if s.get('codec_name') == 'h264' and int(s.get('nb_read_packets', 0)) > 0), None)
        if video is None:
            return
        decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
            '-f', 'mpegts', '-i', str(path), '-map', f"0:{int(video['index'])}", '-an',
            '-frames:v', '1', '-f', 'framemd5', 'pipe:1'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
        frames = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b'#')]
        events.add('H264_DECODED' if decoded.returncode == 0 and frames else 'H264_DECODE_FAILED')
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return


def capture_once(service):
    events = set()
    reason = 'UNKNOWN'
    process = None
    # Temporary files are mode 0600 and removed even on deadline/error.
    with tempfile.TemporaryDirectory(prefix='ezviz-local-') as directory, tempfile.TemporaryFile() as diagnostic:
        path = Path(directory) / 'capture.ts'
        size = 0
        try:
            command = service.local_command(service.worker, '', '') + ['12']
            with service.lock:
                if service.stopping:
                    return deep_result(events, 'STOPPING')
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
                    env={k: v for k, v in os.environ.items() if not k.startswith(('EZVIZ_', 'SUPERVISOR_'))}
                        | {'LOCAL_DIAGNOSTIC_FD': str(diagnostic.fileno())},
                    pass_fds=(diagnostic.fileno(),))
                service.children.add(process)
            deadline = time.monotonic() + 25
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
                while size < MAX_MEDIA:
                    chunk = next_bytes(process, deadline)
                    if not chunk:
                        break
                    chunk = chunk[:MAX_MEDIA-size]
                    output.write(chunk)
                    size += len(chunk)
        except LocalCredentialError as error:
            events.add(error.code)
            reason = error.code
        except (OSError, subprocess.SubprocessError, ValueError):
            reason = 'PROCESS_START_FAILED' if process is None else 'SDK_FAILED'
            events.add(reason)
        finally:
            if process is not None:
                terminate(process)
                if process.stdout:
                    process.stdout.close()
                with service.lock:
                    service.children.discard(process)
            events.update(read_events(diagnostic))
        if path.exists():
            with path.open('rb') as source:
                first = source.read(188 * 3)
            # Check transport-error flag and adaptation-field-control as well as sync.
            if len(first) >= 188 * 3 and all(first[i] == 0x47 and not first[i+1] & 0x80
                    and first[i+3] & 0x30 for i in (0, 188, 376)):
                inspect_saved(path, events)
            elif first:
                events.add('MPEGTS_INVALID')
            if reason == 'UNKNOWN':
                reason = ('H264_DECODED' if 'H264_DECODED' in events else
                    'H264_NOT_CONFIRMED' if 'MPEGTS_VALID' in events else failure_code(
                    events, first, process.returncode if process is not None else None,
                    process is not None and time.monotonic() >= deadline))
        service.record_evidence(service.worker.serial, events, 'MPEGTS_VALID' in events)
    return deep_result(events, reason)
