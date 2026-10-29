#!/bin/bash
# EZVIZ BC1/W2H: isolated experimental P2P trial for macOS.
# Uses a pinned third-party go2rtc fork. NOT proven with BC1/W2H.
# Does not change Home Assistant or the installed go2rtc add-on.
set -euo pipefail
umask 077
export HISTFILE=/dev/null

LAB="$HOME/ezviz_p2p_lab"
SRC="$LAB/go2rtc-source"
BINARY="$LAB/go2rtc-ezviz-p2p"
CONF="$LAB/private-config.json"
LOG="$LAB/private-run.log"
CAPTURE="$LAB/trial-stream.ts"
FORK="https://github.com/pedropaulovc/go2rtc.git"
REF="feat/ezviz-p2p-transport"
PIN="c6bcd20b26231695ba76dd8c032b711390822b5c"
PID=""

cleanup() {
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -f "$CONF" "$LOG"
}
trap cleanup EXIT INT TERM

echo "=== EZVIZ BC1 experimental P2P trial ==="
echo "Does not change Home Assistant or the normal go2rtc."
echo "Third-party proof-of-concept, not a verified BC1 implementation."

if ! command -v git >/dev/null || ! command -v go >/dev/null || ! command -v python3 >/dev/null || ! command -v curl >/dev/null; then
  echo "Missing git, Go, Python 3 or curl."
  echo "With enough disk space you can install Go using: brew install go"
  exit 2
fi
AVAIL_KB="$(df -Pk "$HOME" | awk 'END {print $4}')"
if [ "$AVAIL_KB" -lt 3145728 ]; then
  echo "Less than 3 GiB disk space free. No build attempted."
  exit 2
fi

mkdir -p "$LAB"
chmod 700 "$LAB"

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --single-branch --branch "$REF" "$FORK" "$SRC"
fi

ORIGIN="$(git -C "$SRC" remote get-url origin)"
HEAD="$(git -C "$SRC" rev-parse HEAD)"
if [ "$ORIGIN" != "$FORK" ] || [ "$HEAD" != "$PIN" ]; then
  echo "Third-party source differs from the pinned reviewed revision."
  echo "Nothing will be built or started."
  exit 3
fi
echo "Pinned source revision verified."

echo "Building an isolated macOS binary..."
(cd "$SRC" && GOTOOLCHAIN=auto go build -o "$BINARY" .)
chmod 700 "$BINARY"

printf "EZVIZ login email: "
IFS= read -r ACCOUNT
printf "EZVIZ login password (hidden): "
IFS= read -r -s PASSWORD
printf "\n"
if [ -z "$ACCOUNT" ] || [ -z "$PASSWORD" ]; then
  echo "No login credentials entered. Nothing started."
  exit 4
fi

# Credentials are not passed in argv, written to shell history or committed.
printf "%s\0%s\0" "$ACCOUNT" "$PASSWORD" |
  python3 -c '
import json,sys
from urllib.parse import quote
raw=sys.stdin.buffer.read().split(b"\0")
account=raw[0].decode()
password=raw[1].decode()
serial="G23915155-G28068598"
source="ezviz://"+quote(account,safe="")+":"+quote(password,safe="")+"@apiieu.ezvizlife.com/"+serial+"?channel=1&subtype=main"
config={
  "api":{"listen":"127.0.0.1:1985"},
  "rtsp":{"listen":"127.0.0.1:8556"},
  "webrtc":{"listen":""},
  "streams":{"ezviz_p2p_lab":source}
}
with open(sys.argv[1],"w") as f:
  json.dump(config,f)
' "$CONF"
unset ACCOUNT PASSWORD

echo "Testing one camera. This fork requires EZVIZ cloud P2P bootstrap."
"$BINARY" -c "$CONF" > "$LOG" 2>&1 &
PID="$!"
READY=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24; do
  if curl --silent --fail --max-time 1 \
      "http://127.0.0.1:1985/api/streams" >/dev/null; then
    READY=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then break; fi
  sleep 0.5
done

if [ "$READY" != 1 ]; then
  echo "TEST: independent P2P server did not start."
  exit 5
fi

RESULT="$(curl --silent --max-time 40 --connect-timeout 5 \
    -o "$CAPTURE" --write-out 'HTTP=%{http_code} BYTES=%{size_download}' \
    'http://127.0.0.1:1985/api/stream.ts?src=ezviz_p2p_lab' 2>/dev/null || true)"
echo "RESULT: $RESULT"

# Fork logging may contain auth URLs. Only print fixed classification labels.
python3 - "$LOG" <<'PY'
from pathlib import Path
import sys
data=Path(sys.argv[1]).read_text(errors="replace").lower()
labels={
    "login failed": "LOGIN_REJECTED",
    "login decode": "LOGIN_RESPONSE_UNRECOGNIZED",
    "p2p config failed": "P2P_DEVICE_INFO_REJECTED",
    "no p2p servers": "P2P_DEVICE_NOT_FOUND",
    "no kms entry": "P2P_KMS_MISSING",
    "no connection entry": "P2P_ENDPOINT_MISSING",
    "p2p secret failed": "P2P_SESSION_KEY_REJECTED",
    "srt data session did not start": "UDP_SRT_HANDSHAKE_UNAVAILABLE",
    "probe:": "MEDIA_CODEC_OR_FRAMING_UNSUPPORTED",
    "connection refused": "NETWORK_CONNECTION_REFUSED",
    "no such host": "DNS_LOOKUP_FAILED",
}
found=[v for k,v in labels.items() if k in data]
print("CLASSIFICATION:", ", ".join(found) if found else "UNDETERMINED")
print("No account passwords, tokens or raw upstream errors are printed.")
PY

if [ -s "$CAPTURE" ]; then
  if command -v ffprobe >/dev/null; then
    ffprobe -v error -show_entries stream=codec_type,codec_name,width,height \
      -of json "$CAPTURE" 2>/dev/null || true
  fi
  echo "Private test media: $CAPTURE"
else
  rm -f "$CAPTURE"
fi
echo "Experiment finished. Credential config and private logs deleted."
