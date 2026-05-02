#!/bin/sh
set -e

echo "[INFO] Starting MTG Collection Manager..."

export OPTIONS_PATH="/data/options.json"
export DATA_DIR="/data"
export INGRESS_PORT="8099"
export INGRESS_ENTRY="/"

# Read ingress info from Supervisor API if available
if [ -n "${SUPERVISOR_TOKEN}" ]; then
  ADDON_INFO=$(python3 -c "
import urllib.request, json, os
req = urllib.request.Request(
    'http://supervisor/addons/self/info',
    headers={'Authorization': 'Bearer ' + os.environ['SUPERVISOR_TOKEN']}
)
try:
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())['data']
    print(data.get('ingress_entry', '/'))
    print(data.get('ingress_port', 8099))
except Exception as e:
    print('/')
    print(8099)
" 2>/dev/null)
  INGRESS_ENTRY=$(echo "${ADDON_INFO}" | head -1)
  INGRESS_PORT=$(echo "${ADDON_INFO}" | tail -1)
  export INGRESS_ENTRY INGRESS_PORT
fi

echo "[INFO] Ingress entry: ${INGRESS_ENTRY}"
echo "[INFO] Ingress port: ${INGRESS_PORT}"

cd /app

exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${INGRESS_PORT}" \
  --log-level info \
  --no-access-log
