from pathlib import Path
from typing import Protocol
import json
from .models import Flight
from .config import Settings
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
