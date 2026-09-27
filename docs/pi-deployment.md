# Raspberry Pi deployment with Docker Compose

The application is a complete ARM64 container image. Python, source checkout and
build tools are not required to run it. Docker Compose supplies private runtime
configuration, persistent SQLite storage, health checks and image updates.

## Test the published sandbox image locally

From a checkout containing an ignored, owner-only `.env` with
`FR24_SANDBOX_TOKEN` and the personal profile fields:

```sh
export FLIGHT_IMAGE=ghcr.io/YOUR_GITHUB_USER/where-do-you-fly:sandbox
docker compose -f deploy/compose.local-sandbox.yaml up -d --pull always --wait
docker compose -f deploy/compose.local-sandbox.yaml ps
```

If the checkout is stored in iCloud Drive and Docker cannot mount `.env`, copy it
to a protected local path and select that path for the Compose run:

```sh
mkdir -p "$HOME/.config/where-do-you-fly"
install -m 600 .env "$HOME/.config/where-do-you-fly/sandbox.env"
export FLIGHT_ENV_FILE_HOST="$HOME/.config/where-do-you-fly/sandbox.env"
export FLIGHT_IMAGE=ghcr.io/YOUR_GITHUB_USER/where-do-you-fly:sandbox
docker compose -f deploy/compose.local-sandbox.yaml up -d --pull always --wait
```

Open http://localhost:8001. The port is bound only to local loopback. The Compose
profile imports `.env` into the private `deploy_flight-sandbox-config` volume and
stores SQLite data in `deploy_flight-sandbox-data`. It runs the published
`linux/arm64` `:sandbox` image; no local application build occurs.

Stop it without deleting its data:

```sh
docker compose -f deploy/compose.local-sandbox.yaml down
```

Add `--volumes` only when deliberately discarding the local sandbox database and
simulated credit ledger.

## Image release flow

Successful main CI builds and pushes an ARM64 candidate to GHCR, tests that exact
digest, then moves `:sandbox` and an immutable `:verified-<commit SHA>` tag to it.
Production changes only through the manual promotion workflow, which moves `:prod`
to an already verified image without rebuilding.

## Install Compose polling on the Pi

Prerequisites: Debian arm64 (`dpkg --print-architecture`), Docker Engine with
Compose v2, and Tailscale. From a reviewed checkout, run once:

```sh
sudo sh deploy/install.sh ghcr.io/YOUR_GITHUB_USER/where-do-you-fly
```

The installer copies the Compose definition and systemd units. It creates but does
not start two profiles:

| Profile | Image tag | Local port | Private application config |
| --- | --- | --- | --- |
| sandbox | `:sandbox` | 8001 | `/etc/where-do-you-fly/sandbox/.env` |
| prod | `:prod` | 8002 | `/etc/where-do-you-fly/prod/.env` |

Compose variables live in `/etc/where-do-you-fly/<profile>.compose.env`; edit them
to change the image, port or host paths. FR24 tokens stay in the separate `.env`
files mounted into the container and never enter Compose, GHCR or GitHub Actions.

Complete each private `.env` with its own token, geography, airport, timezone,
schedule and exact Tailscale origin. Preserve mode 600 and owner UID 10001.

```dotenv
FLIGHT_PROFILE=personal
FLIGHT_ENV=sandbox
FLIGHT_WEB_ORIGIN=https://your-configurable-hostname.example.ts.net
```

Use `FLIGHT_ENV=prod` and the production origin in the production file. Hostnames
are runtime configuration and can be supplied or changed later without rebuilding
the image.

Start and enable automatic sandbox updates:

```sh
sudo systemctl start flight-pull@sandbox.service
sudo systemctl enable --now flight-pull@sandbox.timer
```

Every five minutes the timer runs:

```sh
docker compose up -d --pull always --wait --wait-timeout 90
```

Compose checks the channel tag, downloads a changed image, recreates the container
while preserving mounted data, and waits for the credit-free health endpoint. If
the tag is unchanged, the service remains unchanged. The timer never calls FR24;
FR24 access still occurs only through application requests inside active windows.

Compose reports a failed health check but does not automatically restore the prior
image. For rollback, put an older `verified-<commit SHA>` tag in the profile's
`FLIGHT_IMAGE`, run the service again, and investigate before returning to the
moving channel tag. Persistent SQLite state is intentionally not rolled back.

## Tailscale-only access

Keep the application on host loopback and expose it privately with Tailscale Serve:

```sh
sudo tailscale serve --bg --https=443 http://127.0.0.1:8001
sudo tailscale serve --bg --https=8443 http://127.0.0.1:8002
```

Use Serve, not Funnel. Restrict the corresponding HTTPS ports to selected users or
devices in the tailnet policy. SSH administration is a separate permission. The
configured `FLIGHT_WEB_ORIGIN` must match the URL used by the browser, including a
non-default port. Review existing Serve configuration before claiming these ports.

Inspect operations with:

```sh
sudo systemctl status flight-pull@sandbox.service
sudo journalctl -u flight-pull@sandbox.service -n 30
docker compose --env-file /etc/where-do-you-fly/sandbox.compose.env \
  -f /opt/where-do-you-fly/deploy/compose.yaml ps
```

Sources: [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/),
[Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).
