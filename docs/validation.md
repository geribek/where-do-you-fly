# Validation — 2026-09-26

- 12 Python unittest tests passed in the existing Python 3.12 environment and a clean temporary environment installed from requirements.txt.
- Coverage: weekday/weekend boundary behavior, both DST transitions, all seven fixtures, geographic exclusion, metadata reuse/expiry, concurrent polling and restart persistence, budget exhaustion/month rollover, failed-attempt reservation, live-mode rejection, API response and 800×480 four-color output.
- PlatformIO 6.2.0: `pio run -d firmware -e esp32-s3` succeeded with pinned Espressif 6.10.0 and ArduinoJson 7.3.1. Static RAM 45,280 bytes; flash 871,013 bytes. These are build sizes, not runtime heap or energy measurements.
- Generated and visually inspected artifacts/preview.png; sample response in artifacts/display.json. These generated outputs are ignored by Git.
- Clean dependency install emitted a Starlette deprecation warning for its httpx-based TestClient; all tests passed. Direct dependencies are pinned; transitive dependencies are not fully locked.
- Wokwi runtime, physical ESP32, battery, e-paper and enclosure gates were not executed.
- No live FR24 adapter or network access to FR24 was implemented. No secrets were added. No hardware was purchased or selected beyond the generic S3 emulator target.

## Public-repository hardening

- Private deployment configuration now loads from an owner-readable ignored env file; public defaults and fixtures are synthetic. Configuration is validated and sensitive values are excluded from error/repr output. The display payload omits coordinates.
- Private delivery-tracker references were moved outside public candidates. Their automatic-update instructions remain available locally.
- A checksum-verified Gitleaks scanner plus project-specific privacy checks protects the full staged snapshot through a local pre-commit hook. CI includes the same credential scanner with synthetic tests and no deployment secrets.
- 29 tests passed, including configuration precedence/validation, geography-driven ranking, response redaction, forced-added env files, staged-vs-working-tree leaks and scanner failure behavior.
- At the pre-publication audit, no Git commit or push had been made. The configured GitHub repository was verified public with secret scanning and push protection already enabled. Runtime/deployment secrets remain unprovisioned; CI and branch-required checks cannot be validated remotely until the first push.
