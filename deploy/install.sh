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
install -m 644 deploy/compose.yaml /opt/where-do-you-fly/deploy/
install -m 644 deploy/flight-pull@.service deploy/flight-pull@.timer /etc/systemd/system/
for channel in sandbox prod; do
  install -d -m 700 -o 10001 -g 10001 "/etc/where-do-you-fly/$channel" "/var/lib/where-do-you-fly/$channel/data"
  if [ ! -e "/etc/where-do-you-fly/$channel/.env" ]; then
    install -m 600 -o 10001 -g 10001 .env.example "/etc/where-do-you-fly/$channel/.env"
  fi
done
if [ ! -e /etc/where-do-you-fly/sandbox.compose.env ]; then
  printf '%s\n' \
    "FLIGHT_IMAGE=$REPOSITORY:sandbox" \
    'FLIGHT_CHANNEL=sandbox' \
    'APP_PORT=8001' \
    'CONFIG_DIR=/etc/where-do-you-fly/sandbox' \
    'DATA_DIR=/var/lib/where-do-you-fly/sandbox/data' \
    > /etc/where-do-you-fly/sandbox.compose.env
  chmod 600 /etc/where-do-you-fly/sandbox.compose.env
fi
if [ ! -e /etc/where-do-you-fly/prod.compose.env ]; then
  printf '%s\n' \
    "FLIGHT_IMAGE=$REPOSITORY:prod" \
    'FLIGHT_CHANNEL=prod' \
    'APP_PORT=8002' \
    'CONFIG_DIR=/etc/where-do-you-fly/prod' \
    'DATA_DIR=/var/lib/where-do-you-fly/prod/data' \
    > /etc/where-do-you-fly/prod.compose.env
  chmod 600 /etc/where-do-you-fly/prod.compose.env
fi
systemctl daemon-reload
echo 'Installed; timers remain disabled. Complete the private configuration in docs/pi-deployment.md.'
