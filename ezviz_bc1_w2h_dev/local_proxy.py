"""HTTP MPEG-TS wrapper for a static-credential LAN SDK session only."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import threading
import time
import tempfile
from types import SimpleNamespace

from hybrid_proxy import HybridService, PROBE_SECONDS, next_bytes, terminate
from local_capture import read_credentials
from local_diagnostics import LocalCredentialError, error_payload, read_events, failure_code


class LocalService(HybridService):
    def __init__(self, serial, port):
        self.worker = SimpleNamespace(serial=serial, port=port, index=port - 8557)
        self.viewer = threading.Lock()
        self.children = set()
        self.stopping = False
        super().__init__(lambda: (self.worker,), port=port)
        self.mode = "local"
        self.hub_ip = "static_credentials"

    def local_command(self, worker, hub, cas_serial):
        path = Path(f"/data/local_camera_{worker.index}.json")
        read_credentials(path, worker.serial)
        return [sys.executable, "/app/local_capture.py", str(path), worker.serial]

    def open_cloud(self, worker):
        raise RuntimeError("Cloud is disabled in local-only mode.")

    def status(self):
        result = super().status()
        with self.lock:
            result["evidence"] = getattr(self, "evidence", {}).get(self.worker.serial)
        result["note"] = "Local-only static credentials. Live W2H video/audio remain unverified."
        return result

    def open_local(self, worker, hub, cas_serial):
        process = None
        first = b""
        valid_ts = False
        reason = "UNKNOWN"
        diagnostic = tempfile.TemporaryFile()
        try:
            command = self.local_command(worker, hub, cas_serial)
            with self.lock:
                if self.stopping:
                    return None
                process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, start_new_session=True,
                    env={key: value for key, value in os.environ.items()
                         if not key.startswith(("EZVIZ_", "SUPERVISOR_"))} | {"LOCAL_DIAGNOSTIC_FD": str(diagnostic.fileno())},
                    pass_fds=(diagnostic.fileno(),),
                )
                self.children.add(process)
            deadline = time.monotonic() + PROBE_SECONDS
            first = b""
            while len(first) < 376:
                chunk = next_bytes(process, deadline)
                if not chunk:
                    break
                first += chunk
            if len(first) >= 376 and first[0] == first[188] == 0x47:
                valid_ts = True
                return process, first
            reason = failure_code(read_events(diagnostic), first, process.poll(), time.monotonic() >= deadline)
        except LocalCredentialError as error:
            reason = error.code
        except ValueError:
            reason = "INVALID_CREDENTIALS"
        except (OSError, subprocess.SubprocessError):
            reason = "UNKNOWN"
        finally:
            self.record_evidence(worker.serial, read_events(diagnostic), valid_ts)
            diagnostic.close()
        if process is not None:
            terminate(process)
            with self.lock:
                self.children.discard(process)
        self.mark_lan_failure(worker.serial)
        self.record_source(worker.serial, reason)
        return None

    def record_evidence(self, serial, events, mpegts):
        with self.lock:
            if not hasattr(self, "evidence"):
                self.evidence = {}
            self.evidence[serial] = {
                "tcp_connected": "TCP_CONNECTED" in events,
                "preview_accepted": "PREVIEW_ACCEPTED" in events,
                "stream_setup": "STREAM_SETUP" in events,
                "media_frame_received": "MEDIA_FRAME" in events,
                "mpegts_received": mpegts,
            }

    def record_source(self, serial, source):
        # Keep the cause through the parent's generic 503 and cooldown path.
        if source != "unavailable":
            super().record_source(serial, source)

    def unavailable_payload(self, worker):
        with self.lock:
            return error_payload(self.last_result.get(worker.serial, "UNKNOWN"))

    def stream(self, handler, worker):
        if not self.viewer.acquire(blocking=False):
            handler.send_error(409, "Camera already has a local viewer")
            return
        try:
            super().stream(handler, worker)
        finally:
            with self.lock:
                self.children = {process for process in self.children if process.poll() is None}
            self.viewer.release()

    def stop_children(self):
        with self.lock:
            self.stopping = True
            children = tuple(self.children)
        for process in children:
            terminate(process)


def main():
    serial, port = sys.argv[1], int(sys.argv[2])
    service = LocalService(serial, port)
    def stop(_signum, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        service.server.serve_forever()
    finally:
        service.stop_children()
        service.server.server_close()


if __name__ == "__main__":
    main()
