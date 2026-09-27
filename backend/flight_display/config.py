"""Deployment configuration. Never serialize settings or include values in errors."""
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo
import math
import os
import re
from urllib.parse import urlsplit
from dotenv import dotenv_values

def windows(value):
    result = []
    for part in value.split(","):
        match = re.fullmatch(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", part)
        if not match:
            raise ValueError("invalid schedule configuration")
        h1,m1,h2,m2 = map(int, match.groups())
        if h1>23 or h2>23 or m1>59 or m2>59:
            raise ValueError("invalid schedule configuration")
        start,end = h1*60+m1,h2*60+m2
        if start >= end or start%5 or end%5:
            raise ValueError("windows must increase and align to five minutes")
        result.append((start,end))
    return tuple(result)

@dataclass(frozen=True, repr=False)
class Settings:
    # All defaults describe a synthetic demo, never the owner's location.
    center_lat: float = 0
    center_lon: float = 0
    radius_km: float = 50
    airport: str = "XXX"
    timezone: str = "UTC"
    weekday_windows: tuple = ((540,1020),)
    weekend_windows: tuple = ((540,1020),)
    provider: str = "mock"
    scenario: str = "inbound"
    db: str = ".private/flight-display.sqlite3"
    api_key: str = field(default="", repr=False)
    environment: str = "mock"
    result_limit: int = 1
    web_origin: str = ""
    allow_container_proxy: bool = False

    @property
    def runtime_db(self):
        # Keep the original mock database; never mix production spend with test data.
        return self.db if self.environment == "mock" else self.db + "." + self.environment

    def __repr__(self):
        return "Settings(<redacted>)"

    def __post_init__(self):
        try:
            if not (math.isfinite(self.center_lat) and -90 <= self.center_lat <= 90): raise ValueError()
            if not (math.isfinite(self.center_lon) and -180 <= self.center_lon <= 180): raise ValueError()
            if not (math.isfinite(self.radius_km) and 0 < self.radius_km <= 500): raise ValueError()
            if not re.fullmatch(r"[A-Z]{3}", self.airport): raise ValueError()
            ZoneInfo(self.timezone)
            for spans in (self.weekday_windows,self.weekend_windows):
                if not (spans and all(0 <= a < b <= 1440 and a%5==0 and b%5==0 for a,b in spans)): raise ValueError()
        except Exception:
            raise ValueError("invalid private deployment configuration") from None
        if self.environment not in {"mock", "sandbox", "prod"}:
            raise ValueError("invalid flight environment")
        if self.provider not in {"mock", "fr24"} or (self.provider == "fr24") != (self.environment != "mock"):
            raise ValueError("provider must match environment")
        if self.environment != "mock" and not self.api_key.strip():
            raise ValueError("selected environment requires its own FR24 token")
        if not 1 <= self.result_limit <= 10:
            raise ValueError("result limit must be between 1 and 10")
        if self.web_origin:
            origin = urlsplit(self.web_origin)
            tailnet = origin.scheme == "https" and origin.hostname and origin.hostname.endswith(".ts.net")
            local = origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}
            if (not (tailnet or local) or origin.username or origin.password or origin.path
                    or origin.query or origin.fragment):
                raise ValueError("Web origin must be an exact local or Tailscale origin")

    @classmethod
    def load(cls, env_file=None, environ=None):
        env = dict(os.environ if environ is None else environ)
        path = Path(env_file if env_file is not None else env.get("FLIGHT_ENV_FILE", ".env"))
        values = {}
        if path.exists():
            if path.is_symlink() or (os.name == "posix" and path.stat().st_mode & 0o077):
                raise ValueError("private env file must be owner-readable only (chmod 600)")
            values.update(dotenv_values(path, interpolate=False))
        values.update(env)  # Explicit runtime environment overrides local files.
        if values.get("FLIGHT_PROVIDER", "mock") != "mock" and "FLIGHT_ENV" not in values:
            raise RuntimeError("Select an explicit FLIGHT_ENV instead of the legacy provider setting")
        environment = values.get("FLIGHT_ENV", "mock")
        if environment not in {"mock", "sandbox", "prod"}:
            raise ValueError("FLIGHT_ENV must be mock, sandbox or prod")
        # Do not fall back between credentials: a missing token must fail closed.
        token_name = {"mock":"FR24_API_KEY", "sandbox":"FR24_SANDBOX_TOKEN", "prod":"FR24_PROD_TOKEN"}[environment]
        if values.get("FLIGHT_PROFILE", "demo") not in {"demo","personal"}:
            raise ValueError("invalid configuration profile")
        required=("FLIGHT_CENTER_LAT","FLIGHT_CENTER_LON","FLIGHT_AIRPORT","FLIGHT_TIMEZONE","FLIGHT_WEEKDAY_WINDOWS","FLIGHT_WEEKEND_WINDOWS")
        if values.get("FLIGHT_PROFILE") == "personal" and any(not values.get(k) for k in required):
            raise ValueError("personal profile requires complete deployment settings")
        try:
            return cls(center_lat=float(values.get("FLIGHT_CENTER_LAT",0)),
                       center_lon=float(values.get("FLIGHT_CENTER_LON",0)),
                       radius_km=float(values.get("FLIGHT_RADIUS_KM",50)),
                       airport=values.get("FLIGHT_AIRPORT","XXX"),
                       timezone=values.get("FLIGHT_TIMEZONE","UTC"),
                       weekday_windows=windows(values.get("FLIGHT_WEEKDAY_WINDOWS","09:00-17:00")),
                       weekend_windows=windows(values.get("FLIGHT_WEEKEND_WINDOWS","09:00-17:00")),
                       provider="mock" if environment == "mock" else "fr24",
                       environment=environment,
                       result_limit=int(values.get("FR24_RESULT_LIMIT", "1")),
                       web_origin=values.get("FLIGHT_WEB_ORIGIN", ""),
                       allow_container_proxy=values.get("FLIGHT_ALLOW_CONTAINER_PROXY", "false").lower() == "true",
                       scenario=values.get("MOCK_SCENARIO","inbound"),
                       db=values.get("FLIGHT_DB",".private/flight-display.sqlite3"),
                       api_key=values.get(token_name, "") or "")
        except RuntimeError:
            raise
        except Exception:
            raise ValueError("invalid private deployment configuration") from None
