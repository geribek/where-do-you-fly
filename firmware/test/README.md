# Firmware build and simulation gate

Install PlatformIO Core, then from `firmware/` run:
```sh
pio run -e esp32-s3
```
Open this directory in VS Code with Wokwi, enable its private IoT gateway, and start the simulator. `wokwi.toml` points to the built S3 artifacts. Start the backend on port 8000. `host.wokwi.internal` reaches the host through the gateway; public browser simulation cannot directly reach host localhost. Consult current Wokwi gateway availability/licensing; no purchase is required for the delivered scaffold.

Default Wi-Fi is Wokwi-GUEST; use ignored `include/secrets.h` for real-board Wi-Fi/backend URL. Never add FR24 credentials or endpoints. `SerialDisplay` implements the display interface; no e-paper library or pin assignment exists.

Manual acceptance matrix (not yet executed):
- Each of seven mock scenarios: expected status/category and readable fallback metadata.
- Active boundary to sleep and next wake, including DST tests driven by backend clock injection in tests.
- Disconnect Wi-Fi and stop/restart backend: bounded 60-second retries, no busy loop, previous output retained.
- Invalid/oversized JSON, HTTP 500 and unsupported version: no screen replacement.
- Multiple simulated clients: one backend reservation per slot.
- 24-hour simulation: no reboot, heap growth or unexpected fetch loop.

The Python contract tests verify the shared API but do not substitute for firmware compilation or simulation. Before production, replace buffered getString with a bounded reader, validate all status/flight fields, add firmware parser unit tests, TLS/auth and deep-sleep wake support. Deep sleep is intentionally deferred until physical power measurements.
