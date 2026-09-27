"""Local startup: python -m flight_display.run --env sandbox."""
import argparse
import os
import uvicorn
from .config import Settings

def main():
    parser = argparse.ArgumentParser(description="Start local flight calibration")
    parser.add_argument("--env", choices=["mock", "sandbox", "prod"])
    parser.add_argument("--env-file", help="Private dotenv file; defaults to FLIGHT_ENV_FILE or .env")
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8001")))
    args = parser.parse_args()
    if args.env:
        os.environ["FLIGHT_ENV"] = args.env
    if args.env_file:
        os.environ["FLIGHT_ENV_FILE"] = args.env_file
    try:
        settings = Settings.load()
    except (ValueError, OSError):
        parser.exit(2, "Cannot start: check the selected environment token, private file permissions and settings.\n")
    print(f"Starting {settings.environment} calibration on localhost:{args.port}")
    uvicorn.run("flight_display.calibration:create_app", factory=True, host="127.0.0.1",
                port=args.port, access_log=False, proxy_headers=False)

if __name__ == "__main__":
    main()
