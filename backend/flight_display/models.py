from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
class Flight(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=64)
    callsign: str | None = Field(default=None, max_length=24)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    origin: str | None = Field(default=None, max_length=3)
    destination: str | None = Field(default=None, max_length=3)
    aircraft: str | None = Field(default=None, max_length=32)
class DisplayFlight(BaseModel):
    # Device contract omits coordinates; only the backend needs positions.
    id: str
    callsign: str | None = None
    origin: str | None = None
    destination: str | None = None
    aircraft: str | None = None
class Display(BaseModel):
    version: Literal[1] = 1
    status: Literal["ok", "empty", "sleep", "budget", "error"]
    generated_at: str
    observed_at: str | None = None
    next_poll_at: str
    retry_after_s: int
    stale: bool = False
    flight: DisplayFlight | None = None
    category: Literal["inbound", "outbound", "nearby"] | None = None
