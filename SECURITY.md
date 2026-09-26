# Public source, private deployment

All checked-in fixtures, example settings and CI data are synthetic. The demo uses a fictional airport identifier, coordinates near zero and UTC. Real coordinates, local airport, timezone, viewing schedule, credentials, Wi-Fi details, private tracker links and machine paths must stay outside tracked files.

## Local development

Copy `.env.example` to `.env` for a new setup and immediately run `chmod 600 .env`. The backend reads this exact file from the repository working directory; set `FLIGHT_ENV_FILE` to use another path. Process environment variables override the file. Personal profiles require complete settings and invalid configuration errors never echo values. `FR24_API_KEY` is reserved for a future backend-only adapter; no key is needed now and live mode still fails closed.

An env file is plaintext, not encrypted. Owner-only permissions and Git exclusion prevent accidental sharing; they do not defend against a compromised account or device. Use OS disk encryption and, when required, a secret manager. If the repository lives in a cloud-synced folder, `.env` and `.private` may sync too: Git ignore does not prevent cloud sync. Put credentials in an owner-readable file outside the synced tree and point `FLIGHT_ENV_FILE` there, or inject them from the runtime secret manager. Never paste credentials into chat, Jira, issues, command arguments or logs.

`.private/` contains local tracking context, privacy denylist and tools. Runtime databases, generated screenshots, build output and firmware secrets are ignored. Mock fixtures are rebased to configured coordinates/airport in memory; generated output can therefore be private. Do not upload it publicly. The display API excludes position coordinates and does not serialize Settings or API keys; route labels are still needed by the device. The backend is a loopback-only POC: TLS and device authentication are required before exposing personal responses remotely.

## GitHub and deployed backend

GitHub Actions **secrets** are appropriate for credentials or sensitive deployment configuration needed by a trusted deployment workflow. Prefer environment secrets with deployment approval and narrowly scoped access; do not use plain Actions variables for private geography or airport settings. Public pull-request tests/builds use only synthetic data and receive no deployment secrets. Never run untrusted PR code with secrets (`pull_request_target` is not used).

GitHub secrets are not automatically available to the running backend. A future deployment must inject them securely into the hosting platform's runtime secret store/environment. Prefer a hosting secret manager and short-lived deployment identity via OIDC. Keep the FR24 key exclusively on the backend, never in firmware, a browser bundle, build flags or downloadable artifacts. Private Wi-Fi credentials compiled into firmware remain recoverable from the binary; never publish personalized firmware. Secure provisioning is a later physical-device gate.

No real keys have been provisioned. No GitHub secrets, branch rules or remote security settings were changed by this local hardening. The current remote was verified to have secret scanning and push protection enabled. Before publishing to another remote, verify those protections again. Require the `security` CI check where branch rules permit after it has first run. Provider-specific scanners do not reliably detect location or arbitrary proprietary tokens; local privacy checks complement them.

## Before the first commit and on every clone

```sh
python3 scripts/install_security.py
python3 scripts/security_check.py --all
```

The installer verifies the pinned Gitleaks download checksum and configures this clone's pre-commit hook. Every commit scans the entire staged snapshot, including forced-added ignored files; it does not trust unstaged edits. CI runs the same candidate scanner with no private values or secrets. CI cannot know private values absent from its environment: never upload the private denylist to CI. Review diffs as well. Hooks can be bypassed by Git flags; they are defense in depth, not a guarantee. New clones must install the hook.

The scanner prints paths and generic reasons, never matched values. Keep `.private/privacy-values.json` current with private identifiers and old coordinate variants; `.env` values are also checked locally. No exclusions for generated personal data should be added to the public allowlist.

If a real secret is ever committed or published, revoke/rotate it immediately, then remove it from history and artifacts. Removing the latest file alone is insufficient. Private-location exposure also needs history/artifact cleanup, but those values cannot be meaningfully rotated.

References: [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets), [secure workflow use](https://docs.github.com/en/actions/reference/security/secure-use), [push protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection), [Gitleaks](https://github.com/gitleaks/gitleaks).
