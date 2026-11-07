"""HTTP MPEG-TS wrapper for a static-credential LAN SDK session only."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from hybrid_proxy import HybridService, PROBE_SECONDS, next_bytes, terminate
from local_capture import read_credentials


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
        result["note"] = "Local-only static credentials. Live W2H video/audio remain unverified."
        return result

    def open_local(self, worker, hub, cas_serial):
        process = None
        try:
            command = self.local_command(worker, hub, cas_serial)
            with self.lock:
                if self.stopping:
                    return None
                process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, start_new_session=True,
                    env={key: value for key, value in os.environ.items()
                         if not key.startswith(("EZVIZ_", "SUPERVISOR_"))},
                )
                self.children.add(process)
            first = next_bytes(process, time.monotonic() + PROBE_SECONDS)
            if first and first[0] == 0x47:
                return process, first
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        if process is not None:
            terminate(process)
            with self.lock:
                self.children.discard(process)
        self.mark_lan_failure(worker.serial)
        return None

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
