import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from flight_display.app import create_app
from flight_display.config import Settings
TEST_SETTINGS=Settings(timezone="Europe/Paris",weekday_windows=((420,480),(900,1200)),weekend_windows=((420,1200),))
from flight_display.provider import MockProvider
from flight_display.service import Service
from flight_display.schedule import active, next_poll

def dt(s): return datetime.fromisoformat(s)
NOW=dt("2026-09-25T07:00:00+02:00")
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"test.sqlite3"
    def tearDown(self): self.tmp.cleanup()
    def svc(self,scenario="inbound",cap=25000):
        return Service(self.db,MockProvider(scenario),cap,settings=TEST_SETTINGS)
    def test_boundaries(self):
        for clock, expected in [("06:59",False),("07:00",True),("07:59",True),("08:00",False),("14:59",False),("15:00",True),("19:59",True),("20:00",False)]:
            self.assertEqual(active(dt(f"2026-09-25T{clock}:00+02:00"),TEST_SETTINGS),expected)
        self.assertTrue(active(dt("2026-09-26T12:00:00+02:00"),TEST_SETTINGS))
        self.assertFalse(active(dt("2026-09-26T20:00:00+02:00"),TEST_SETTINGS))
    def test_dst(self):
        for s, expected in [("2026-03-28T20:00:00+01:00","2026-03-29T05:00:00+00:00"),("2026-10-24T20:00:00+02:00","2026-10-25T06:00:00+00:00")]:
            self.assertEqual(next_poll(dt(s),TEST_SETTINGS),dt(expected))
    def test_scenarios(self):
        for scenario,status,kind in [("empty","empty",None),("inbound","ok","inbound"),("outbound","ok","outbound"),("multiple","ok","inbound"),("missing_metadata","ok","nearby"),("malformed","error",None),("busy","ok","inbound")]:
            with self.subTest(scenario=scenario):
                svc=Service(Path(self.tmp.name)/f"{scenario}.db",MockProvider(scenario),settings=TEST_SETTINGS)
                v=svc.get(NOW)
                self.assertEqual((v.status,v.category),(status,kind))
    def test_off_hours_never_calls(self):
        s=self.svc(); self.assertEqual(s.get(NOW.replace(hour=8)).status,"sleep")
        self.assertEqual(s.provider.calls,0)
    def test_concurrent_and_restart(self):
        s=self.svc()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _:s.get(NOW),range(20)))
        self.assertEqual(s.provider.calls,1)
        second=self.svc();second.get(NOW);self.assertEqual(second.provider.calls,0)
    def test_budget_and_rollover(self):
        s=self.svc(cap=120)
        self.assertEqual(s.get(NOW).status,"ok")
        self.assertEqual(s.get(NOW+timedelta(minutes=5)).status,"budget")
        self.assertEqual(s.get(dt("2026-10-01T07:00:00+02:00")).status,"ok")
        self.assertEqual(s.provider.calls,2)
    def test_failed_attempt_reserved_and_not_retried(self):
        s=self.svc("malformed",120)
        s.get(NOW);s.get(NOW)
        self.assertEqual(s.provider.calls,1)
        self.assertEqual(s.get(NOW+timedelta(minutes=5)).status,"budget")
    def test_metadata_and_geo(self):
        s=self.svc(); s.get(NOW)
        from flight_display.models import Flight
        s.provider.fetch=lambda:[Flight(id="mock-001",lat=0,lon=0.03)]
        self.assertEqual(s.get(NOW+timedelta(minutes=5)).category,"inbound")
        s.provider.fetch=lambda:[Flight(id="far",lat=40,lon=40,destination="XXX")]
        self.assertEqual(s.get(NOW+timedelta(minutes=10)).status,"empty")
    def test_contract(self):
        s=self.svc()
        class ClockService:
            def get(self): return s.get(NOW)
        with TestClient(create_app(ClockService())) as c:
            response=c.get("/api/v1/display")
            self.assertEqual(response.status_code,200)
            self.assertLess(len(response.content),1024)
            self.assertEqual(response.json()["version"],1)
            self.assertEqual(response.json()["retry_after_s"],300)
    def test_live_mode_rejected(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"FLIGHT_PROVIDER":"live", "FLIGHT_ENV_FILE":str(Path(self.tmp.name)/"absent.env")}):
            with self.assertRaises(RuntimeError): create_app()
    def test_metadata_expiry(self):
        s=self.svc();s.get(NOW)
        from flight_display.models import Flight
        s.provider.fetch=lambda:[Flight(id="mock-001",lat=0,lon=0.03)]
        self.assertEqual(s.get(NOW.replace(hour=15)).category,"nearby")
    def test_renderer(self):
        from desktop.render import render, PALETTE
        image=render(self.svc().get(NOW).model_dump(),Path(self.tmp.name)/"preview.png")
        self.assertEqual(image.size,(800,480))
        self.assertTrue(set(image.get_flattened_data()) <= PALETTE)
if __name__=="__main__": unittest.main()
