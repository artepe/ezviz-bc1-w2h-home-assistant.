"""Small ingress-only camera manager. No credentials are sent to the browser."""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from camera_config import Camera, next_port, parse_cameras, validate_name, validate_serial
from media_probe import inspect_audio
from local_diagnostics import explain_local_error
from supervisor_client import SettingsError, SupervisorClient

STATIC = Path(__file__).with_name("static")
INGRESS_HOST = "172.30.32.2"
INGRESS_PORT = 8788
MAX_BODY = 32 * 1024


def explain_ffmpeg_error(reason: str) -> str:
    """Return only fixed FFmpeg diagnosis labels, never untrusted stderr text.

    pyEzvizApi may include full camera/cloud URLs, query credentials or
    filesystem paths in FFmpeg stderr. Inspect fixed substrings only.
    """
    if "could not launch ffmpeg" in reason or "ffmpeg: not found" in reason:
        return "HTTP 502 [FFMPEG_MISSING]: FFmpeg could not start in the EZVIZ app container."
    if "ffmpeg input writer did not stop" in reason:
        return "HTTP 502 [FFMPEG_STALLED]: FFmpeg's input writer did not stop after stream cancellation."
    if any(term in reason for term in (
        "output file #0 does not contain any stream",
        "output file does not contain any stream",
        "matches no streams",
        "does not contain any stream",
        "no video stream",
    )):
        return "HTTP 502 [FFMPEG_NO_VIDEO]: FFmpeg did not detect a usable video stream in the camera data."
    if any(term in reason for term in (
        "could not find codec parameters",
        "invalid data found when processing input",
        "error opening input file",
        "could not find stream information",
    )):
        return "HTTP 502 [FFMPEG_BAD_INPUT]: FFmpeg could not recognize the input from EZVIZ. The supplied video may be incomplete or in an unsupported format."
    if any(term in reason for term in (
        "picture size 0x0 is invalid",
        "dimensions not set",
        "width and height not set",
        "unspecified size",
        "sps unavailable",
        "non-existing pps",
        "pps id out of range",
    )):
        return "HTTP 502 [FFMPEG_VIDEO_HEADER]: Video codec headers or frame dimensions were missing from the cloud stream."
    if any(term in reason for term in (
        "non-monotonous dts",
        "non monotonically increasing dts",
        "invalid timestamps",
    )):
        return "HTTP 502 [FFMPEG_TIMESTAMPS]: The cloud video timestamps were invalid for MPEG-TS remuxing."
    if any(term in reason for term in (
        "invalid nal unit",
        "error while decoding",
        "decode_slice_header error",
        "missing picture",
        "invalid frame data",
    )):
        return "HTTP 502 [FFMPEG_BITSTREAM]: The cloud stream contained unrecognizable or damaged video frames."
    if "broken pipe" in reason:
        return "HTTP 502 [FFMPEG_PIPE]: FFmpeg lost a media pipe. Close other live viewers and test again."
    if "ffmpeg exited with status" in reason:
        return "HTTP 502 [FFMPEG_EXIT]: FFmpeg exited unsuccessfully without a recognized diagnostic. The cause needs further upstream instrumentation."
    return "HTTP 502 [FFMPEG_REMUX]: FFmpeg failed while processing the EZVIZ cloud video stream."


def explain_proxy_error(status: int, payload: bytes) -> str:
    """Classify the upstream HTTP error without exposing EZVIZ session secrets.

    pyEzvizApi embeds str(PyEzvizError) in its HTML 502 response. That text
    may contain cloud URLs, tokens, serials or other sensitive values.
    Never return or log the raw upstream message.
    """
    default = (
        f"The camera proxy returned HTTP {status}. "
        "The EZVIZ cloud video request failed; detailed upstream data is hidden."
    )
    if status != 502:
        return default
    body = payload[:8192].decode("utf-8", errors="replace")
    match = re.search(r"<p>\s*Message:\s*(.*?)</p>", body, re.I | re.S)
    if not match:
        return default
    reason = html.unescape(re.sub(r"<[^>]*>", "", match.group(1))).lower()
    if any(term in reason for term in ("expired", "unauthorized", "not authenticated", "authentication failed", "invalid session", "invalid token")):
        return "HTTP 502: EZVIZ rejected the cloud session. Check the EZVIZ account and use Sign in again."
    if "vtdu token" in reason:
        return "HTTP 502: EZVIZ could not obtain its cloud video token (VTDU). Check the account and cloud service."
    if any(term in reason for term in ("device offline", "camera offline", "hub offline", "base station offline", "device is offline")):
        return "HTTP 502 [DEVICE_OFFLINE]: EZVIZ reports the camera or W2H base station offline. Restore its Ethernet/Wi-Fi connection and confirm it is online in the EZVIZ app."
    if "vtm resource" in reason or "resource metadata" in reason:
        return "HTTP 502: EZVIZ did not provide a video resource for this camera. Check whether the camera is awake and available for live view."
    if any(term in reason for term in ("vtm server", "vtm endpoint", "vtm port", "vtm negotiation")):
        return "HTTP 502: EZVIZ cloud video server negotiation failed (VTM)."
    if "video on its video route" in reason or "routed video before startup deadline" in reason:
        return "HTTP 502 [RTP_ROUTE]: EZVIZ supplied no video on the negotiated RTP route."
    if any(term in reason for term in ("no media", "no video", "deadline", "timed out", "timeout", "no packets")):
        return "HTTP 502: EZVIZ cloud stream provided no video before the timeout. Check camera wake-up and connectivity."
    if any(term in reason for term in ("connection refused", "connection reset", "network unreachable", "dns", "socket")):
        return "HTTP 502: EZVIZ cloud stream could not establish or keep its network connection."
    # Keep these classifications specific: the old generic "media decoding"
    # result conflated encrypted VTM packets, RTP codec detection and FFmpeg.
    # Only fixed messages are returned, never text from the upstream server.
    if "received encrypted vtm stream packet" in reason:
        return "HTTP 502 [VTM_ENCRYPTED]: EZVIZ returned encrypted video packets. This proxy is not configured for media decryption; a codec restart will not resolve it."
    if "could not detect rtp video codec" in reason:
        return "HTTP 502 [RTP_CODEC]: The EZVIZ stream arrived, but no recognizable H.264/H.265 video codec was found in its RTP packets."
    if "unsupported rtp video codec" in reason:
        return "HTTP 502 [RTP_CODEC_UNSUPPORTED]: The cloud stream uses a video codec not supported by the proxy."
    if "rtp cloud stream did not contain a complete video nal unit" in reason:
        return "HTTP 502 [RTP_INCOMPLETE]: The cloud stream delivered RTP packets without a complete video frame."
    if "ffmpeg" in reason:
        return explain_ffmpeg_error(reason)
    if "mpeg" in reason:
        return "HTTP 502 [MPEG_TRANSPORT]: The cloud stream container or MPEG transport could not be handled."
    if "decrypt" in reason:
        return "HTTP 502 [MEDIA_DECRYPT]: EZVIZ video decryption failed or was unavailable."
    if "codec" in reason:
        return "HTTP 502 [MEDIA_CODEC]: The cloud video codec could not be handled."
    return default


class CameraService:
    def __init__(self, client: SupervisorClient, runtime):
        self.client = client
        self.runtime = runtime
        self.audio_test_lock = threading.Lock()
        self.credential_lock = threading.Lock()
        self.credential_directory = Path('/data')

    def local_credentials(self, port, payload):
        """Ingress + CSRF protected; never return submitted or acquired secrets."""
        if self.runtime.mode != 'local_only':
            raise ValueError('Select Local only before setting local credentials.')
        if not self.credential_lock.acquire(blocking=False):
            raise ValueError('Another credential operation is running. Wait for it to finish.')
        try:
            with self.client.lock:
                cameras = parse_cameras(self.client.raw_options())
                camera = next((c for c in cameras if c.port == port), None)
                if camera is None:
                    raise ValueError('Camera not found. Refresh this page.')
                if payload.get('action') == 'discover':
                    if payload.get('allow_cloud') is not True:
                        raise ValueError('Authorize the one-time channel metadata lookup first.')
                    region = payload.get('region', 'isgpopen.ezvizlife.com')
                    if region not in ('isgpopen.ezvizlife.com', 'iusopen.ezvizlife.com', 'open.ys7.com'):
                        raise ValueError('Choose an EZVIZ API region.')
                    try:
                        result = subprocess.run(
                            [sys.executable, str(Path(__file__).with_name('channel_discovery.py')),
                             '--directory', str(self.credential_directory), '--serial', camera.serial,
                             '--region', region], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=55, check=False,
                            env={k: v for k, v in os.environ.items() if not k.startswith(('EZVIZ_', 'SUPERVISOR_'))})
                        if result.returncode or len(result.stdout) > 65536:
                            raise ValueError
                        outcome = json.loads(result.stdout)
                        # Only fixed statuses and numeric candidates cross ingress.
                        from channel_discovery import safe_result
                        return safe_result(outcome, camera.serial)
                    except (OSError, ValueError, subprocess.SubprocessError):
                        raise ValueError('Channel lookup failed or timed out. No credentials were changed.') from None
                channel = payload.get('channel')
                if type(channel) is not int or not 1 <= channel <= 256:
                    raise ValueError('Enter the observed W2H channel (1..256). It cannot be inferred from camera order.')
                if type(payload.get('replace', False)) is not bool:
                    raise ValueError('Invalid replacement option.')
                replace = payload.get('replace') is True
                target = self.credential_directory / f'local_camera_{camera.index}.json'
                if target.exists() and not replace:
                    raise ValueError('Credentials already exist. Explicitly select Replace to overwrite them.')
                data = payload.get('credentials')
                if payload.get('action') == 'acquire':
                    if payload.get('allow_cloud') is not True:
                        raise ValueError('Authorize the one-time EZVIZ cloud login and P2P/CAS lookup first.')
                    fields = {k: payload.get(k, '') for k in ('username', 'password', 'sms_code', 'cas_serial', 'api_url')}
                    if not all(isinstance(v, str) for v in fields.values()) or not fields['username'] or not fields['password']:
                        raise ValueError('Enter your EZVIZ account and password.')
                    if fields['api_url'] not in ('apiieu.ezvizlife.com', 'apius.ezvizlife.com', 'apias.ezvizlife.com'):
                        raise ValueError('Choose an EZVIZ API region.')
                    if fields['sms_code'] and (not fields['sms_code'].isascii() or not fields['sms_code'].isdigit() or len(fields['sms_code']) > 10):
                        raise ValueError('Enter a numeric verification code.')
                    if fields['cas_serial']:
                        validate_serial(fields['cas_serial'])
                    if type(payload.get('use_known_w2h', False)) is not bool:
                        raise ValueError('Invalid known W2H endpoint consent.')
                    fields['use_known_w2h'] = payload.get('use_known_w2h', False)
                    fields['serial'] = camera.serial
                    try:
                        result = subprocess.run(
                            [sys.executable, str(Path(__file__).with_name('local_acquire.py'))],
                            input=json.dumps(fields).encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=60, check=False,
                            env={k: v for k, v in os.environ.items() if not k.startswith(('EZVIZ_', 'SUPERVISOR_'))},
                        )
                        if result.returncode in (20, 21, 22):
                            from local_acquire import safe_failure
                            return safe_failure(result.returncode, result.stdout)
                        if result.returncode in (10, 11, 12):
                            messages = {
                                10: 'EZVIZ requires verification. Enter your verification code and password, then retry; alternatively import an authorized SDK export.',
                                11: 'EZVIZ sign-in failed. Check account, password, region and verification code. No local credentials were installed.',
                                12: 'EZVIZ sign-in completed, but LAN metadata, P2P registration or CAS lookup failed. The W2H CAS mapping may be unsupported. Import an authorized SDK export if available.',
                            }
                            return {'ok': False, 'message': messages[result.returncode]}
                        if result.returncode or len(result.stdout) > 65536:
                            raise ValueError
                        data = json.loads(result.stdout)
                    except (OSError, ValueError, subprocess.SubprocessError):
                        raise ValueError('EZVIZ lookup failed or timed out. Check account, region, MFA and observed CAS serial. No credentials were installed. You can import an authorized SDK JSON export instead.') from None
                elif payload.get('action') != 'import':
                    raise ValueError('Choose Import or Fetch from EZVIZ.')
                from local_credentials import install_data
                try:
                    install_data(data, self.credential_directory, camera.serial, channel, camera.index, replace=replace)
                except FileExistsError:
                    raise ValueError('Credentials already exist. Explicitly select Replace to overwrite them.') from None
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    raise ValueError('Invalid credentials. Check serial, observed channel, private IPv4 endpoint, ports 9010/9020 and the CAS tuple. Existing credentials were retained.') from None
            self.runtime.reload.set()
            return {'ok': True, 'message': 'FORMAT_VALID: private credentials saved. W2H authentication, channel and video remain unconfirmed. Use Restart proxy, then Test video; check the picture in the player.'}
        finally:
            self.credential_lock.release()

    def change(self, operation: str, payload: dict, port: int | None = None) -> None:
        with self.client.lock:
            cameras = list(parse_cameras(self.client.raw_options()))
            if operation == "add":
                name = validate_name(payload.get("name"))
                serial = self.full_serial(payload)
                cameras.append(Camera(name, serial, next_port(cameras)))
            else:
                current = next((camera for camera in cameras if camera.port == port), None)
                if current is None:
                    raise ValueError("Camera not found. Refresh this page.")
                cameras.remove(current)
                if operation == "edit":
                    cameras.append(Camera(validate_name(payload.get("name")), self.full_serial(payload), current.port))
            self.client.save_cameras(tuple(sorted(cameras, key=lambda camera: camera.port)))
        self.runtime.reload.set()

    def set_connection(self, payload):
        self.client.save_connection_mode(payload.get("connection_mode"))
        self.runtime.reload.set()

    @staticmethod
    def full_serial(payload: dict) -> str:
        serial = validate_serial(payload.get("serial"))
        hub = payload.get("hub_serial", "")
        if not isinstance(hub, str):
            raise ValueError("Enter a valid W2H base station serial.")
        if "-" not in serial and hub.strip():
            serial = f"{validate_serial(hub)}-{serial}"
        return validate_serial(serial)

    def test(self, port: int) -> dict[str, object]:
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        camera = next((camera for camera in cameras if camera.port == port), None)
        if camera is None:
            raise ValueError("Camera not found. Refresh this page.")
        try:
            with socket.create_connection(("127.0.0.1", camera.port), timeout=1):
                pass
        except OSError:
            return {"ok": False, "message": f"The local camera proxy is not listening on port {camera.port}. Wait for startup and check the app log."}

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        request = Request(f"http://127.0.0.1:{camera.port}/{camera.serial}.ts")
        try:
            # A sleeping BC1 can take longer to wake after a W2H/network outage.
            # Do not run continuous background probes against battery cameras.
            with build_opener(NoRedirect).open(request, timeout=35) as response:
                packet = response.read(188)
                if response.status == 200 and len(packet) == 188 and packet[0] == 0x47:
                    return {"ok": True, "message": "Video transport data received. Open the go2rtc player to check the picture."}
                return {"ok": False, "message": "The proxy answered but did not return a complete MPEG-TS packet. Check the camera in the EZVIZ app."}
        except HTTPError as error:
            try:
                # Read only a bounded error response, never a video stream.
                payload = error.read(8192)
            except OSError:
                payload = b""
            finally:
                error.close()
            message = (explain_local_error(payload, error.code) if self.runtime.mode == "local_only"
                       else explain_proxy_error(error.code, payload))
            # Only a confirmed stale authentication/session response merits
            # re-login. Generic 502/no-media errors may simply be sleeping BC1s.
            if message.startswith("HTTP 502: EZVIZ rejected the cloud session"):
                if self.runtime.request_session_refresh():
                    message += " A new login is scheduled. Test video again after the refresh."
                else:
                    message += " Automatic login refresh is rate-limited to five minutes."
            return {"ok": False, "message": message}
        except (OSError, URLError):
            if self.runtime.mode == "local_only":
                return {"ok": False, "message": "The local proxy connection failed or timed out within 35 seconds. W2H CAS authorization, channel mapping and video remain unconfirmed. Cloud access is disabled."}
            return {"ok": False, "message": "No video data arrived within 35 seconds. Check that the W2H base station is online in the EZVIZ app and its network cable is connected. Wake the camera in the app; when connectivity returns, use Restart proxy and test again."}

    def deep_local(self, port):
        if self.runtime.mode != 'local_only':
            raise ValueError('Select Local only before running this test.')
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        camera = next((c for c in cameras if c.port == port), None)
        if camera is None or camera.index != 1:
            raise ValueError('Deep Local Diagnostics is available for Camera 1 only.')
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            request = Request(f'http://127.0.0.1:{camera.port}/deep-local', data=b'', method='POST')
            with build_opener(NoRedirect).open(request, timeout=55) as response:
                result = json.loads(response.read(16384))
            from local_diagnostics import DEEP_STAGES
            stages = result['stages']
            if len(stages) != len(DEEP_STAGES):
                raise ValueError
            # Rebuild the boundary from fixed labels/statuses only.
            safe = []
            for row, (label, _, _) in zip(stages, DEEP_STAGES):
                if row['label'] != label or row['status'] not in ('CONFIRMED', 'FAILED', 'NOT_TESTED'):
                    raise ValueError
                safe.append({'label': label, 'status': row['status']})
            return {'ok': any(row['label'] == 'H.264 decoded' and row['status'] == 'CONFIRMED' for row in safe), 'stages': safe,
                    'message': 'One bounded local test completed. Unconfirmed steps remain NOT_TESTED.'}
        except (OSError, URLError, ValueError, KeyError, TypeError):
            from local_diagnostics import deep_result
            return deep_result(set(), 'DIAGNOSTIC_UNAVAILABLE')

    def inspect_cloud(self, port: int) -> dict[str, object]:
        """Analyze one saved camera's cloud packet types without returning media."""
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        if not any(camera.port == port for camera in cameras):
            raise ValueError("Camera not found. Refresh this page.")
        return self.runtime.trace_cloud(port)

    def restart(self, port: int) -> dict[str, object]:
        """One-camera manual proxy recovery; never reset EZVIZ credentials."""
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        if not any(camera.port == port for camera in cameras):
            raise ValueError("Camera not found. Refresh this page.")
        if self.runtime.restart_camera(port):
            return {"ok": True, "message": "Local proxy restart requested for this camera only. Leave the W2H connected; wait briefly and run Test video again. The EZVIZ token and other camera are unchanged."}
        return {"ok": False, "message": "The proxy has not started or was restarted in the last minute. Check the W2H connection and app log before trying again."}

    def test_audio(self, port: int) -> dict[str, object]:
        with self.client.lock:
            cameras = parse_cameras(self.client.raw_options())
        camera = next((camera for camera in cameras if camera.port == port), None)
        if camera is None:
            raise ValueError("Camera not found. Refresh this page.")
        if not self.audio_test_lock.acquire(blocking=False):
            return {"ok": False, "audio": None, "message": "Another audio test is running. Wait for it to finish and try again."}
        try:
            # The browser selects a saved camera only, never an arbitrary URL.
            return inspect_audio(f"http://127.0.0.1:{camera.port}/{camera.serial}.ts")
        finally:
            self.audio_test_lock.release()


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, client, runtime, allowed_hosts=(INGRESS_HOST,)):
        self.service = CameraService(client, runtime)
        self.runtime = runtime
        self.allowed_hosts = frozenset(allowed_hosts)
        self.csrf = secrets.token_hex(32)
        super().__init__(address, CameraHandler)


class CameraHandler(BaseHTTPRequestHandler):
    server: CameraServer

    def log_message(self, *_args):
        # HTTP URLs and form bodies never belong in the app log.
        pass

    def permitted(self) -> bool:
        if self.client_address[0] not in self.server.allowed_hosts:
            self.respond(403, {"error": "Open this app through Home Assistant ingress."})
            return False
        return True

    def respond(self, status: int, body: dict | str | bytes, content_type="application/json; charset=utf-8") -> None:
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if not self.permitted():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            prefix = self.headers.get("X-Ingress-Path", "").rstrip("/")
            if not re.fullmatch(r"/[-A-Za-z0-9_/]*", prefix) or prefix.startswith("//"):
                prefix = ""
            page = (STATIC / "index.html").read_text(encoding="utf-8")
            page = page.replace("__CSRF__", self.server.csrf).replace("__BASE__", html.escape(prefix + "/", quote=True))
            self.respond(200, page, "text/html; charset=utf-8")
        elif path in ("/app.js", "/app.css"):
            self.respond(200, (STATIC / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
        elif path == "/api/state":
            self.respond(200, {"version": os.environ.get("APP_VERSION", "development"), **self.server.runtime.snapshot()})
        elif path == "/health":
            self.respond(200, {"ok": True})
        else:
            self.respond(404, {"error": "Not found."})

    def do_POST(self):
        self.mutate("add")

    def do_PATCH(self):
        self.mutate("edit")

    def do_DELETE(self):
        self.mutate("remove")

    def mutate(self, operation):
        if not self.permitted():
            return
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf):
            self.respond(403, {"error": "This page expired. Refresh it and try again."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.respond(415, {"error": "Use a JSON request."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.respond(413, {"error": "Invalid request size."})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Invalid form data.")
        except (ValueError, UnicodeError):
            self.respond(400, {"error": "Invalid form data."})
            return
        path = urlsplit(self.path).path
        match = re.fullmatch(r"/api/cameras/(\d+)(/test|/test-audio|/restart|/inspect-cloud|/local-credentials|/deep-local)?", path)
        try:
            if operation == "add" and path == "/api/connection":
                self.server.service.set_connection(payload)
            elif operation == "add" and path == "/api/cameras":
                self.server.service.change("add", payload)
            elif match and operation == "add" and match.group(2):
                if match.group(2) == '/local-credentials':
                    self.respond(200, self.server.service.local_credentials(int(match.group(1)), payload))
                    return
                action = {"/deep-local": self.server.service.deep_local, "/test": self.server.service.test,
                          "/test-audio": self.server.service.test_audio,
                          "/restart": self.server.service.restart,
                          "/inspect-cloud": self.server.service.inspect_cloud}[match.group(2)]
                self.respond(200, action(int(match.group(1))))
                return
            elif match and not match.group(2) and operation in ("edit", "remove"):
                self.server.service.change(operation, payload, int(match.group(1)))
            else:
                self.respond(404, {"error": "Not found."})
                return
        except (ValueError, SettingsError) as error:
            self.respond(400 if isinstance(error, ValueError) else 503, {"error": str(error)})
            return
        except Exception:
            self.respond(500, {"error": "The operation could not be confirmed. Refresh the page and check the app log."})
            return
        self.respond(200, {"ok": True, "message": "Saved in Home Assistant and verified. Applying camera settings."})


def start_server(client, runtime):
    server = CameraServer(("0.0.0.0", INGRESS_PORT), client, runtime)
    threading.Thread(target=server.serve_forever, daemon=True, name="camera-manager").start()
    return server
