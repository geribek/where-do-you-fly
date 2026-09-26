import json
import math
import sqlite3
from datetime import datetime, timezone
from .models import Display, Flight, DisplayFlight
from .config import Settings
from pathlib import Path
from .schedule import active, next_poll

def distance(f, settings=Settings()):
    # Haversine from the private configured center.
    a,b,c,d = map(math.radians, (settings.center_lat,settings.center_lon,f.lat,f.lon))
    h = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371 * 2 * math.asin(min(1,math.sqrt(h)))
def category(f, settings=Settings()):
    return "inbound" if f.destination == settings.airport else "outbound" if f.origin == settings.airport else "nearby"
def rank(f, settings=Settings()):
    return ({"inbound":0,"outbound":1,"nearby":2}[category(f, settings)], distance(f, settings), f.id)

class Service:
    def __init__(self, db, provider, cap=25000, settings=Settings()):
        self.settings = settings
        Path(db).parent.mkdir(parents=True, exist_ok=True)
        if not 0 < cap <= 25000:
            raise ValueError("POC cap must be between 1 and 25000")
        self.db, self.provider, self.cap = str(db), provider, cap
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS ledger(month TEXT PRIMARY KEY, credits INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), slot INTEGER, payload TEXT);
            CREATE TABLE IF NOT EXISTS metadata(id TEXT PRIMARY KEY, expires REAL, payload TEXT);
            """)
    def connect(self):
        return sqlite3.connect(self.db, timeout=10)
    def get(self, now=None):
        now = now or datetime.now(timezone.utc)
        nxt = next_poll(now, self.settings)
        base = dict(generated_at=now.isoformat(), next_poll_at=nxt.isoformat(),
                    retry_after_s=max(1,math.ceil((nxt-now).total_seconds())))
        if not active(now, self.settings):
            return Display(status="sleep", **base)
        slot = int(now.timestamp()) // 300
        month = now.astimezone(timezone.utc).strftime("%Y-%m")
        with self.connect() as c:
            # Single transaction serializes callers and persists attempted slots across restarts.
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT slot,payload FROM state WHERE id=1").fetchone()
            if row and row[0] == slot:
                return Display.model_validate({**json.loads(row[1]), **base})
            used = c.execute("SELECT credits FROM ledger WHERE month=?",(month,)).fetchone()
            cost = self.provider.max_credits
            if (used[0] if used else 0) + cost > self.cap:
                return Display(status="budget", **base)
            # Conservative estimate: reserve full maximum, including failed/ambiguous calls.
            c.execute("INSERT INTO ledger VALUES (?,?) ON CONFLICT(month) DO UPDATE SET credits=credits+excluded.credits",(month,cost))
            result = Display(status="error", **base)
            # Commit reservation before any provider call; crashes never refund uncertain usage.
            c.execute("INSERT OR REPLACE INTO state VALUES (1,?,?)",(slot,result.model_dump_json()))
        try:
            flights = self.provider.fetch()
            with self.connect() as c:
                for f in flights:
                    cached = c.execute("SELECT payload FROM metadata WHERE id=? AND expires>?",(f.id,now.timestamp())).fetchone()
                    if cached:
                        old = json.loads(cached[0])
                        for key in ("origin","destination","aircraft","callsign"):
                            if getattr(f,key) is None:
                                setattr(f,key,old.get(key))
                    c.execute("INSERT OR REPLACE INTO metadata VALUES (?,?,?)",(f.id,now.timestamp()+21600,f.model_dump_json()))
                flights = sorted((f for f in flights if distance(f, self.settings)<=self.settings.radius_km),key=lambda f: rank(f, self.settings))
                selected = flights[0] if flights else None
                result = Display(status="ok" if selected else "empty", observed_at=now.isoformat(),
                                 flight=DisplayFlight.model_validate(selected.model_dump()) if selected else None,category=category(selected, self.settings) if selected else None,**base)
        except (ValueError, KeyError, TypeError, OSError):
            pass
        with self.connect() as c:
            c.execute("UPDATE state SET payload=? WHERE id=1 AND slot=?",(result.model_dump_json(),slot))
        return result
