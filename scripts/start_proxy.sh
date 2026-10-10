#!/usr/bin/env bash
set -euo pipefail

# Start the verified pyEzvizApi cloud-to-MPEG-TS proxy.
# Environment variables:
#   EZVIZ_SERIAL='YOUR_HUB_SERIAL-YOUR_CAMERA_SERIAL'
#   EZVIZ_TOKEN_FILE="$HOME/ezviz-lab/ezviz_token.json"
#   EZVIZ_LISTEN_HOST="$(ipconfig getifaddr en0)"  # macOS
#   bash scripts/start_proxy.sh

if ! command -v pyezvizapi >/dev/null 2>&1; then
  echo 'Missing pyezvizapi. Activate your Python virtual environment first.' >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo 'Missing ffmpeg. Install FFmpeg before starting the proxy.' >&2
  exit 1
fi

: "${EZVIZ_SERIAL:?Set EZVIZ_SERIAL to your BC1 device serial from devices status.}"
: "${EZVIZ_TOKEN_FILE:?Set EZVIZ_TOKEN_FILE to your private ezviz_token.json path.}"
: "${EZVIZ_LISTEN_HOST:=127.0.0.1}"
: "${EZVIZ_LISTEN_PORT:=8558}"

if [[ ! -f "$EZVIZ_TOKEN_FILE" ]]; then
  echo "Token file not found: $EZVIZ_TOKEN_FILE" >&2
  exit 1
fi

if [[ "$EZVIZ_LISTEN_HOST" != "127.0.0.1" && "$EZVIZ_LISTEN_HOST" != "localhost" ]]; then
  echo 'WARNING: proxy has no built-in authentication. Trusted LAN only.' >&2
fi

printf 'Starting EZVIZ BC1/W2H proxy at http://%s:%s/%s.ts\n' \
  "$EZVIZ_LISTEN_HOST" "$EZVIZ_LISTEN_PORT" "$EZVIZ_SERIAL"

exec pyezvizapi --token-file "$EZVIZ_TOKEN_FILE" stream proxy \
  --serial "$EZVIZ_SERIAL" \
  --listen-host "$EZVIZ_LISTEN_HOST" \
  --listen-port "$EZVIZ_LISTEN_PORT"
