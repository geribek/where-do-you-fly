# Local environments

One private `.env` holds shared location/schedule settings and separate credentials.
It stays ignored by Git and owner-only (`chmod 600 .env`). It is plaintext; use
`--env-file /private/location/.env` outside cloud sync when desired.

```dotenv
FLIGHT_ENV=mock
FR24_SANDBOX_TOKEN=
FR24_PROD_TOKEN=
FR24_RESULT_LIMIT=1
```

Populate the sandbox and production token fields locally. Never put a token in a
startup command, browser field, issue, commit or screenshot. No cross-environment
credential fallback is allowed. A missing selected token prevents startup.

## Start and switch

With Python 3.12+ and requirements installed, run from the repository root:

```sh
PYTHONPATH=backend python -m flight_display.run --env mock
PYTHONPATH=backend python -m flight_display.run --env sandbox
PYTHONPATH=backend python -m flight_display.run --env prod
```

Run one at a time, stop with Ctrl-C before switching, then reload
http://127.0.0.1:8001. Select **Refresh snapshot** for sandbox/prod. The browser
does not choose credentials or contact FR24. Nothing is fetched merely by starting
the server. Radius movements filter the current browser sample without requests.

The command-line selector overrides process `FLIGHT_ENV`, which overrides `.env`.
Omit `--env` to use the process/file selection; if absent, mock is the default.
Legacy `FLIGHT_PROVIDER` is superseded by `FLIGHT_ENV`; it cannot enable live mode.
An optional `--env-file` overrides `FLIGHT_ENV_FILE`. Other process settings override
file settings. Use `--port 8002` for another local instance.

Example alternate private profile:

```sh
PYTHONPATH=backend python -m flight_display.run --env sandbox --env-file /private/location/.env
```

The file must be named `.env` or `.env.*` for calibration saves. Profile files can
hold different locations, but keep the same production `FLIGHT_DB` base across
profiles so the production spending ledger is shared. Never delete/change that
database to bypass a budget block. Tokens and environment selection require a
server restart. Saved geography also requires restart; the previous five-minute
snapshot can remain until the next poll.

## Behavior and limits

| Environment | Source | Credential | Persistent state |
| --- | --- | --- | --- |
| mock | Local synthetic fixtures/browser demo | None | Original DB path |
| sandbox | FR24 static test responses | Sandbox token only | DB path + `.sandbox` |
| prod | FR24 real aircraft | Production token only | DB path + `.prod` |

FR24 uses the same official HTTPS API URL for both network environments; the
token determines the remote environment. Keep each token in the correct field.
Sandbox ignores query filters, including bounds and limit, and returns fixed
positions. A successful response may therefore yield **empty** locally when no
sample lies near your observer. This does not indicate a failed connection and
cannot prove balcony visibility. No sandbox credit is consumed; its local ledger
simulates cost reservations for testing guard behavior.

Both network modes enforce configured active windows, at most one attempted
request per five-minute slot (including failures/restarts), and no automatic
retries or enrichment. The provider rechecks the schedule immediately before HTTP.
The full-position endpoint provides route fields for airport ranking and costs
8 credits per returned flight. The default limit of one reserves at most 8 per
attempt, including uncertain failures and empty results. Empty queries cost 1
upstream, so local reservations deliberately overestimate. Increasing the limit
increases spend and can stop collection sooner.

Production also checks a 25,000-credit cap across the preceding 32 days, alongside
the existing calendar-month cap. This conservative window avoids relying on a
particular subscription renewal date. This is a local reservation ledger, not
account-wide reconciliation: usage from other apps is not counted. No billing or
top-up action is taken. Production has not been tested with an actual production token.

The API result limit constrains discovery: ranking applies only to returned
candidates, not every aircraft nearby. Default one-result mode may miss a more
interesting flight. Evaluate broader discovery/budget tradeoffs separately.
UI age is time since retrieval, not an independently verified aircraft position
timestamp. Sandbox samples are static regardless of that age.

The display API can use the same environment configuration via
`flight_display.app:create_app`; its compact contract still omits coordinates.
The loopback calibration snapshot includes positions for the local radar only.

Sources: [FR24 sandbox](https://fr24api.flightradar24.com/docs/sandbox-environment),
[credit overview](https://fr24api.flightradar24.com/docs/credit-overview).
