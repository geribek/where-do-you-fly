from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import httpx
from flight_display.config import Settings
from flight_display.provider import FR24Provider
from flight_display.service import Service

NOW = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)
ROW = {"fr24_id":"synthetic-id", "callsign":"DEMO", "lat":0.01, "lon":0.01,
       "orig_iata":"AAA", "dest_iata":"XXX", "type":"TEST"}

class Environments(unittest.TestCase):
    def load(self, env):
        with tempfile.TemporaryDirectory() as directory:
            return Settings.load(Path(directory)/"absent", environ=env)

    def test_tokens_do_not_fall_back(self):
        for mode, other in [("prod", "FR24_SANDBOX_TOKEN"), ("sandbox", "FR24_PROD_TOKEN")]:
            with self.assertRaises(ValueError): self.load({"FLIGHT_ENV":mode, other:"test-token"})

    def test_environment_selection_and_isolation(self):
        for mode in ["mock", "sandbox", "prod"]:
            s = self.load({"FLIGHT_ENV":mode, "FR24_SANDBOX_TOKEN":"sandbox-test", "FR24_PROD_TOKEN":"prod-test"})
            self.assertEqual(s.environment, mode)
            self.assertNotIn("test", repr(s))
            if mode != "mock":
                self.assertEqual(s.api_key, mode+"-test")
                self.assertTrue(s.runtime_db.endswith("."+mode))
        with self.assertRaises(ValueError): self.load({"FLIGHT_ENV":"production-typo"})

    def provider(self, handler, mode="sandbox", clock=lambda: NOW):
        return FR24Provider(Settings(environment=mode, provider="fr24", api_key="synthetic-token"),
                            transport=httpx.MockTransport(handler), clock=clock)

    def test_request_and_mapping(self):
        def handler(request):
            self.assertEqual(request.url.host, "fr24api.flightradar24.com")
            self.assertEqual(request.url.path, "/api/live/flight-positions/full")
            self.assertEqual(request.headers["Authorization"], "Bearer synthetic-token")
            self.assertEqual(request.url.params["limit"], "1")
            self.assertNotIn("token", str(request.url))
            return httpx.Response(200,json={"data":[ROW]})
        self.assertEqual(self.provider(handler).fetch()[0].destination,"XXX")

    def test_errors_are_redacted_and_not_retried(self):
        for status, body in [(401, {"message":"synthetic-token"}), (429, {}), (200, {"data":[{}]}), (200,{})]:
            calls=[]
            def handler(request):
                calls.append(request)
                return httpx.Response(status,json=body)
            with self.assertRaises(OSError) as caught: self.provider(handler).fetch()
            self.assertNotIn("synthetic-token", str(caught.exception))
            self.assertEqual(len(calls),1)

    def test_network_boundary_schedule_check(self):
        def handler(request): self.fail("Off-window request")
        with self.assertRaises(OSError):
            self.provider(handler, clock=lambda: NOW.replace(hour=23)).fetch()

    def test_reservation_cache_and_rolling_cap(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={"data":[ROW]})
        p=self.provider(handler,mode="prod")
        with tempfile.TemporaryDirectory() as directory:
            service=Service(Path(directory)/"db",p,cap=8,settings=p.settings)
            self.assertEqual(service.get(NOW).status,"ok")
            self.assertEqual(service.get(NOW).status,"ok")
            self.assertEqual(len(calls),1)
            self.assertEqual(service.get(NOW.replace(month=10,day=1)).status,"budget")
            self.assertEqual(len(calls),1)

    def test_sandbox_ignores_limit_but_prod_does_not(self):
        handler=lambda request:httpx.Response(200,json={"data":[ROW,ROW]})
        self.assertEqual(len(self.provider(handler).fetch()),2)
        with self.assertRaises(OSError): self.provider(handler,mode="prod").fetch()
