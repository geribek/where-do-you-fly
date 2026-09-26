from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .config import Settings

def active(now: datetime, settings: Settings = Settings()) -> bool:
    if now.tzinfo is None:
        raise ValueError("aware datetime required")
    t = now.astimezone(ZoneInfo(settings.timezone))
    minute = t.hour * 60 + t.minute
    spans = settings.weekend_windows if t.weekday() >= 5 else settings.weekday_windows
    return any(a <= minute < b for a,b in spans)

def next_poll(now: datetime, settings: Settings = Settings()) -> datetime:
    t = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    t += timedelta(minutes=5 - t.minute % 5)
    while not active(t, settings):
        t += timedelta(minutes=5)
    return t
