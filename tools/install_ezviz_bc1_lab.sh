#!/bin/sh
# Install or update the separate EZVIZ BC1 Lab integration.
# Does NOT remove the existing EZVIZ add-on or custom integration.
set -eu

BASE='https://raw.githubusercontent.com/artepe/ezviz-bc1-w2h-home-assistant./main/custom_components/ezviz_bc1_lab'
TARGET='/config/custom_components/ezviz_bc1_lab'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
mkdir -p "$TMP/translations"

download() {
  path="$1"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error --retry 2 "$BASE/$path" -o "$TMP/$path"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$TMP/$path" "$BASE/$path"
  else
    echo 'ERROR: neither curl nor wget is available' >&2
    exit 1
  fi
  test -s "$TMP/$path" || { echo "ERROR: empty file: $path" >&2; exit 1; }
}

for p in manifest.json __init__.py const.py camera.py config_flow.py binary_sensor.py strings.json translations/en.json translations/fi.json
do
  echo "Downloading $p..."
  download "$p"
done

if [ -d "$TARGET" ]; then
  BACKUP="/config/ezviz_bc1_lab_backup_$(date +%Y%m%d_%H%M%S)"
  cp -R "$TARGET" "$BACKUP"
  echo "Backup: $BACKUP"
fi

mkdir -p "$TARGET/translations"
for p in manifest.json __init__.py const.py camera.py config_flow.py binary_sensor.py strings.json translations/en.json translations/fi.json
do
  cp "$TMP/$p" "$TARGET/$p"
done

echo "INSTALLED: $TARGET"
echo "Next: ha core check && ha core restart"
echo "Then: Settings > Devices & services > Add integration > EZVIZ BC1 Lab"
