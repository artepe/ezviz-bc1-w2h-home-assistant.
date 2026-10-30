#!/command/with-contenv bash
set -euo pipefail
umask 077
cd /data
exec /opt/ezviz-venv/bin/python /app/runner.py
