# Balcony calibration helper

A local browser tool for choosing an observer location, target airport and radius. Mock is the default. See [environments](environments.md) to start FR24 sandbox or production and understand the limits of each mode.

## Start

From the repository root with backend requirements installed:
```sh
PYTHONPATH=backend uvicorn flight_display.calibration:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log --no-proxy-headers
```
Open http://127.0.0.1:8001. Keep the helper bound to loopback; it rejects nonlocal clients and hostnames. Use `FLIGHT_ENV_FILE` for an owner-readable private `.env` or `.env.*` file outside a cloud-synced directory if preferred. Public `.env.example` is never a writable destination.

## Practice the workflow

1. Click **Use my location**, grant permission if desired, and check the reported accuracy. Manual latitude/longitude also work. Browser geolocation may use the browser/OS location service; the app loads no third-party map, analytics or assets.
2. Enter a three-letter target airport and click **Update viewpoint**. This sets a preference, not a verified airport lookup. Changing the viewpoint clears prior observations.
3. Start with a wider radius. The north-up diagram and list show distance and bearing. Drag the radius inward; no upstream request or FR24 credit is used.
4. Practice marking **Seen** or **Not seen**. **Next demo sample** advances the synthetic positions. Feedback records the distance at observation time; changing radius does not rewrite old observations. Airport-only filter changes clear the samples to avoid mixed feedback.
5. Review the suggested cutoff. It sits just inside the closest not-seen sample, if both seen and not-seen evidence exist. Conflicting observations are explicitly flagged. There is no guarantee of visibility; nearby aircraft may be obscured while farther aircraft are visible.
6. To keep a deliberately chosen configuration, acknowledge the practice-mode warning and click **Save settings privately**. Only coordinates, target airport and radius are replaced atomically; other env settings, comments and credentials are preserved. The file stays owner-only. Restart the display backend to apply. Existing cached display output can remain until the next scheduled poll; budget state is never reset. Process-env overrides are reported and must be updated separately.

Observations stay in page memory only. Closing/reloading the page discards them. Config requests are same-origin, no-store and contain no API key. Writes require an unpredictable session token and reject stale versions; no personal values go into URL query strings or validation errors. Other local processes have the same access as the local user; this helper is not a remotely authenticated service.

## Network snapshots

Sandbox/prod use **Refresh snapshot** to read the backend's shared candidate snapshot, with schedule and budget protection. Radius movements never fetch data. The default single-result cap constrains discovery; sandbox positions may be outside your view. Fetch age is displayed, and old snapshots must be refreshed before relying on observations. Broader discovery competes with the result/credit limit and needs explicit budgeting.

Once live is approved, repeat sessions at different times and conditions. Record visible/not-seen distance, direction and quality of the sighting; distinguish absence of a sighting from proof of invisibility. If nearby unseen and farther seen samples overlap, investigate a viewing sector, altitude/elevation or obstacles rather than claiming radius alone solves it. Altitude/elevation are deferred until a trustworthy live altitude datum and observer elevation are available.

## Verification

```sh
PYTHONPATH=backend:. python -m unittest discover -s backend/tests -v
node --test calibration/tests/*.test.mjs
python3 scripts/security_check.py --all
```

Browser acceptance: manual location, geolocation denial fallback, radius/filter changes, conflicting feedback, fresh/stale snapshot label, private save and mobile layout. Automated server tests cover loopback/origin/token restrictions, error redaction, preserved secrets, owner permissions and concurrent/external config updates. All checked-in test data is synthetic.
