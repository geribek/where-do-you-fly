from pathlib import Path
from typing import Protocol
import json
import math
from datetime import datetime, timezone
import httpx
from .models import Flight
from .config import Settings
from .schedule import active
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fr24"
class Provider(Protocol):
    max_credits: int
    def fetch(self) -> list[Flight]: ...
class MockProvider:
    # Synthetic all-candidate fixture cost, not a claim about a live endpoint.
    max_credits = 120
    def __init__(self, scenario="inbound", settings=Settings()):
        self.settings = settings
        if scenario not in {"empty", "inbound", "outbound", "multiple", "missing_metadata", "malformed", "busy"}:
            raise ValueError("unknown mock scenario")
        self.scenario = scenario
        self.calls = 0
    def fetch(self):
        self.calls += 1
        raw = json.loads((FIXTURES / f"{self.scenario}.json").read_text())
        flights = [Flight.model_validate(x) for x in raw["data"]]
        # Rebase synthetic fixtures at runtime; never save personal fixture copies.
        return [Flight.model_validate({**f.model_dump(),
                    "lat": max(-90, min(90, f.lat + self.settings.center_lat)),
                    "lon": (f.lon + self.settings.center_lon + 180) % 360 - 180,
                    "origin": self.settings.airport if f.origin == "XXX" else f.origin,
                    "destination": self.settings.airport if f.destination == "XXX" else f.destination})
                for f in flights]

class FR24Provider:
    """The token selects FR24 sandbox or production; URLs are never user supplied."""
    url = "https://fr24api.flightradar24.com/api/live/flight-positions/full"

    def __init__(self, settings, transport=None, clock=None):
        self.settings = settings
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        # Full positions includes routes, required for airport ranking.
        self.max_credits = 8 * settings.result_limit

    def fetch(self):
        s = self.settings
        lat_delta = math.degrees(s.radius_km / 6371)
        north, south = min(90, s.center_lat+lat_delta), max(-90, s.center_lat-lat_delta)
        if north == 90 or south == -90:
            west, east = -180, 180
        else:
            lon_delta = math.degrees(math.asin(min(1, math.sin(s.radius_km/6371)/math.cos(math.radians(s.center_lat)))))
            west, east = s.center_lon-lon_delta, s.center_lon+lon_delta
            if west < -180 or east > 180:
                west, east = -180, 180
        try:
            with httpx.Client(transport=self.transport, timeout=8, follow_redirects=False, trust_env=False) as client:
                # Recheck at the actual network boundary, including after lock waits.
                if not active(self.clock(), s):
                    raise OSError("Outside configured active window")
                response = client.get(self.url,
                    params={"bounds":f"{north},{south},{west},{east}", "limit":s.result_limit},
                    headers={"Authorization":"Bearer " + s.api_key, "Accept":"application/json", "Accept-Version":"v1"})
                response.raise_for_status()
                rows = response.json()["data"]
                if not isinstance(rows, list):
                    raise ValueError()
                # Sandbox ignores the limit parameter; production must honor it.
                if s.environment == "prod" and len(rows) > s.result_limit:
                    raise ValueError()
                return [Flight.model_validate({
                    "id": row["fr24_id"], "callsign":row.get("callsign") or row.get("flight"),
                    "lat":row["lat"], "lon":row["lon"], "origin":row.get("orig_iata"),
                    "destination":row.get("dest_iata"), "aircraft":row.get("type")
                }) for row in rows]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # No URL, response body, credential or original exception in app errors.
            raise OSError("FR24 request failed; check credentials and provider availability") from None

def make_provider(settings):
    return MockProvider(settings.scenario, settings) if settings.environment == "mock" else FR24Provider(settings)
