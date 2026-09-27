# Raspberry Pi pull deployment

Status: repository setup; on-device installation and acceptance still required.
This version targets Debian **arm64** (`dpkg --print-architecture`). A Pi with
32-bit userspace needs an arm/v7 image build added before installation.

## Release flow

PR checks run tests, secret scanning, firmware compilation and a credential-free
container smoke test on GitHub-hosted runners. After successful **main push**
checks, `publish.yml` builds an ARM64 image, pushes a candidate to GHCR, tests that
exact digest under emulation, then publishes `verified-<commit SHA>` and `sandbox`.
Production changes only when an operator runs **Promote tested image to production**
with a full verified commit SHA. It retags the tested image; it does not rebuild.

Configure the GitHub `production` environment to require a reviewer and restrict
deployment to main before enabling the Pi production timer. Merely naming the
environment in YAML does not configure its protection. Require the PR checks on
main and restrict workflow/package writes to trusted maintainers.

GHCR packages may initially be private. Make the application package public for
anonymous Pi pulls (the image contains public code only), or configure a narrowly
scoped read-packages credential in root's Docker credential store on the Pi.
No FR24 token or Tailscale credential is required by CI. Neither GitHub nor GHCR
needs inbound access to the Pi. The Pi checks GHCR via outbound HTTPS.

## Install on the Pi

Prerequisites: 64-bit Debian, Docker Engine with Compose v2 supporting `up --wait`,
Python 3, and Tailscale installed and enrolled. Reserve UID/GID 10001 for the app;
check it does not belong to an unrelated account. Build jobs run on GitHub, not
on the Pi. Obtain a reviewed checkout containing this deployment setup.

From that checkout:

```sh
dpkg --print-architecture
sudo sh deploy/install.sh ghcr.io/OWNER/IMAGE
```

Replace the repository argument with the lower-case GHCR image repository.
The installer preserves existing configuration and does not start timers.
It installs these independently configurable profiles:

| Profile | Local port | Private config | Deployment config |
| --- | --- | --- | --- |
| sandbox | 8001 | `/etc/where-do-you-fly/sandbox/.env` | `/etc/where-do-you-fly/sandbox.json` |
| prod | 8002 | `/etc/where-do-you-fly/prod/.env` | `/etc/where-do-you-fly/prod.json` |

Each JSON file controls image repository, channel, port, config, data and updater
state directories. Only root should edit them; they control Docker operations.
The updater and Compose files stay root-owned under `/opt/where-do-you-fly/deploy`.
Updates pull images only, never scripts from the registry or remote shell code.

Edit each `.env` privately. Put only its own FR24 token in each profile, and set
the actual location, airport, timezone and active windows. Use personal profile
validation. Preserve owner 10001 and mode 600 after editing. The example is
synthetic; do not enable production against unreviewed demo settings.

## Hostname configuration and Tailscale access

No hostname is embedded in the image, workflow or pull updater. Once the Pi's
Tailscale DNS name is known, put its exact HTTPS origin in each private `.env`:

```dotenv
# Synthetic examples: replace with your actual private hostname.
FLIGHT_WEB_ORIGIN=https://flight.example.ts.net
```

Use the same host with `:8443` for the production profile if using the example
ports below. Origin means scheme + hostname + optional port, with no trailing slash.
It can be changed later without rebuilding the image; restart the corresponding
container to load the new origin.

Configure tailnet grants to permit only your selected user/devices to the Pi's
HTTPS ports (443 for sandbox, 8443 for production). Review/remove any broader
allow rules that would also grant access. SSH administration is a separate grant.
The application delegates remote access authorization to those network rules.
All allowed UI clients can view and edit the calibration settings.

On the Pi, after each service is healthy:

```sh
sudo tailscale serve --bg --https=443 http://127.0.0.1:8001
sudo tailscale serve --bg --https=8443 http://127.0.0.1:8002
```

Use **Serve**, not Funnel. Inspect existing Serve configuration before using its
ports; these examples assume they are free. Backend sockets stay loopback-only
using Linux host networking. The backend accepts the configured Host/origin only
from a loopback peer, ignores forwarded client headers and keeps session-token
checks for POST requests. The proxy supplies TLS; no public/LAN port is published.
Local processes on the Pi remain trusted, as with the desktop helper.

## First deployment and enablement

After the corresponding GHCR channel exists and configuration is ready:

```sh
sudo systemctl start flight-pull@sandbox.service
sudo systemctl status flight-pull@sandbox.service
sudo systemctl enable --now flight-pull@sandbox.timer
```

After manual production promotion and private production configuration, use the
same commands with `prod`. Each timer checks about every five minutes plus jitter.
Timers do not poll FR24. The application still fetches only on a snapshot/display
request inside its active window; unattended flight collection is not introduced.

## Update, recovery and operations

The updater locks per profile, pulls the channel image, resolves its immutable
digest, and does nothing when unchanged. It uses SQLite's online backup before
activation. Compose recreates the service and waits for `/healthz`, which never
calls FR24. Successful activation stores the new and previous digest atomically.

Failure restores the previous image when available and marks the failed digest
so it is not repeatedly deployed. An interrupted update is recovered on the next
run before considering another release. First installation has no previous image
to roll back to. Offline/registry failure leaves the running release intact.
Systemd reports failure and logs a generic diagnostic; there is no external alert
delivery yet. Inspect status and private `release.json` for state. Stop a timer to
pause updates; it does not stop the running app.

```sh
sudo journalctl -u flight-pull@sandbox.service -n 30
sudo systemctl stop flight-pull@sandbox.timer
# Explicitly retry a previously failed digest after fixing configuration:
sudo python3 /opt/where-do-you-fly/deploy/pull.py /etc/where-do-you-fly/sandbox.json --retry
```

For a deliberate production rollback, promote an older verified revision through
the same workflow. Persistent SQLite, private env files and credit reservations
are never rolled back or deleted. Schema changes must remain compatible with the
previous image; destructive migrations need a separate operator migration plan.
The local backup retains one pre-update snapshot and is not a disaster-recovery
backup. Copy backups off-device through your private backup process; never restore
an old credit ledger without accounting for requests since that backup.

Acceptance on actual hardware: reboot recovery, fresh installation, repeated
unchanged polls, rejected image rollback, offline polling, tailnet allowed/denied
clients, and proof that health checks leave FR24 reservations unchanged.

Sources: [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve),
[Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve),
[ARM builds](https://docs.docker.com/build/ci/github-actions/multi-platform/).
