# Flight Display POC

A mock-only, hardware-independent foundation for an ESP32-S3 flight display. Eventual output: 800×480 white/black/red/yellow e-paper. No hardware purchase or live provider is needed.

## Set up

Python 3.12+:
```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 scripts/install_security.py
# New clone only: preserve an existing personal .env rather than overwriting it.
cp -n .env.example .env
chmod 600 .env
PYTHONPATH=backend:. python -m unittest discover -s backend/tests -v
PYTHONPATH=backend uvicorn flight_display.app:create_app --factory --host 127.0.0.1 --port 8000
```

The example environment is synthetic. Enter private deployment settings only in an ignored env file. The backend loads `.env` automatically, with process environment taking precedence. See [SECURITY.md](SECURITY.md) before adding actual credentials, especially in a cloud-synced checkout.

```sh
curl http://127.0.0.1:8000/api/v1/display > artifacts/display.json
python desktop/render.py artifacts/display.json artifacts/preview.png
```

Outside configured active windows the API returns `sleep`. There is no schedule-bypass endpoint. Tests inject synthetic configuration and a clock; they do not read personal settings. Changing geography or airport requires a new local mock database to avoid reusing a cached selection from a prior configuration. Never reset a future live billing ledger this way.

- [Development phases](docs/dev-phases.md)
- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Firmware/Wokwi tests](firmware/test/README.md)
- [Security policy](SECURITY.md)

No live provider, e-paper driver, power circuit or enclosure is included. The renderer is a smoke preview. Private delivery tracking is configured locally, outside public source.
