#!/usr/bin/env bash
# Restore first verified macOS cloud proxy, without modifying Home Assistant.
# Pins pyEzvizApi to the original known-working revision from October 2026.
set -euo pipefail
umask 077
PIN="6df75d95a2ee6a68fb71446ee74a55572e2014ea"
ROOT="$HOME/ezviz-original-cloud"
VENV="$ROOT/.venv"
OLD_TOKEN="$HOME/ezviz-lab/ezviz_token.json"
TOKEN="$ROOT/ezviz_token.json"
CAMERA="G23915155-G28068598"
W2H="192.168.10.138"
PORT=8558

if [[ "$(uname -s)" != Darwin ]]; then
  echo "Run this on the Mac, not in Home Assistant Terminal."
  exit 2
fi
for cmd in git ffmpeg python3.12; do
  if ! command -v "$cmd" >/dev/null; then
    echo "Missing $cmd. Check existing Homebrew packages."
    exit 2
  fi
done

mkdir -p "$ROOT"
chmod 700 "$ROOT"
if [[ ! -e "$VENV/bin/python" ]]; then
  python3.12 -m venv "$VENV"
fi
if [[ ! -f "$ROOT/installed-revision" ]] ||
    [[ "$(cat "$ROOT/installed-revision")" != "$PIN" ]]; then
  echo "Installing the exact original pyEzvizApi revision..."
  PIP_NO_CACHE_DIR=1 "$VENV/bin/python" -m pip install --no-cache-dir \
    "git+https://github.com/RenierM26/pyEzvizApi.git@$PIN"
  printf '%s\n' "$PIN" > "$ROOT/installed-revision"
fi

if [[ ! -s "$TOKEN" ]]; then
  if [[ -s "$OLD_TOKEN" ]]; then
    cp "$OLD_TOKEN" "$TOKEN"
    chmod 600 "$TOKEN"
  else
    echo "The original saved EZVIZ token does not exist."
    echo "See the documented login in docs/INSTALL_EN.md."
    echo "Save a fresh token in $TOKEN and retry."
    exit 3
  fi
fi

IFACE="$(route -n get "$W2H" 2>/dev/null | awk '/interface:/{print $2;exit}')"
LAN_IP=""
if [[ -n "$IFACE" ]]; then
  LAN_IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
fi
if [[ -z "$LAN_IP" ]]; then
  echo "Could not identify Mac LAN IP for W2H $W2H."
  exit 4
fi

echo "TEST: original cloud-proxy pyEzvizApi revision $PIN"
echo "Mac IP: $LAN_IP"
echo "STREAM: http://$LAN_IP:$PORT/$CAMERA.ts"
echo "This legacy test uses EZVIZ cloud; it is NOT offline LAN streaming."
echo "UNAUTHENTICATED proxy: use only on a trusted LAN; never forward port $PORT."
echo "Keep this Terminal open until the Home Assistant stream test ends."
exec "$VENV/bin/pyezvizapi" --token-file "$TOKEN" stream proxy \
  --serial "$CAMERA" \
  --listen-host "$LAN_IP" \
  --listen-port "$PORT"
