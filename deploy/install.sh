#!/bin/sh
# Run from a reviewed checkout on the Pi. Does not start timers or change Tailscale.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run this installer with sudo'; exit 1; }
[ "$(dpkg --print-architecture)" = arm64 ] || { echo 'This release targets arm64 userspace'; exit 1; }
docker compose version >/dev/null
REPOSITORY=${1:?Usage: sudo sh deploy/install.sh ghcr.io/OWNER/IMAGE}
python3 - "$REPOSITORY" <<'PY'
import re, sys
if not re.fullmatch(r'ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+', sys.argv[1]):
    raise SystemExit('Invalid image repository')
PY
install -d -m 755 /opt/where-do-you-fly/deploy
install -m 644 deploy/pull.py deploy/compose.yaml /opt/where-do-you-fly/deploy/
install -m 644 deploy/flight-pull@.service deploy/flight-pull@.timer /etc/systemd/system/
for channel in sandbox prod; do
  install -d -m 700 -o 10001 -g 10001 "/etc/where-do-you-fly/$channel" "/var/lib/where-do-you-fly/$channel/data"
  install -d -m 700 "/var/lib/where-do-you-fly/$channel/deploy"
  if [ ! -e "/etc/where-do-you-fly/$channel/.env" ]; then
    install -m 600 -o 10001 -g 10001 .env.example "/etc/where-do-you-fly/$channel/.env"
  fi
done
python3 - "$REPOSITORY" <<'PY'
import json, os, sys
from pathlib import Path
os.umask(0o077)
for channel, port in [('sandbox', 8001), ('prod', 8002)]:
    path = Path('/etc/where-do-you-fly') / (channel+'.json')
    if path.exists(): continue
    path.write_text(json.dumps({
        'repository': sys.argv[1], 'channel':channel, 'port':port,
        'compose':'/opt/where-do-you-fly/deploy/compose.yaml',
        'config_dir':'/etc/where-do-you-fly/'+channel,
        'data_dir':'/var/lib/where-do-you-fly/'+channel+'/data',
        'state_dir':'/var/lib/where-do-you-fly/'+channel+'/deploy'
    }, indent=2)+'\n')
PY
systemctl daemon-reload
echo 'Installed; timers remain disabled. Complete the private configuration in docs/pi-deployment.md.'
