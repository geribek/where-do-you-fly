from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from flight_display.calibration import create_app

class HostingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env=Path(self.temp.name)/'.env'
        self.env.write_text('FLIGHT_WEB_ORIGIN=https://flight.example.ts.net\n')
        self.env.chmod(0o600)
        p=patch.dict('os.environ',{},clear=True);p.start();self.addCleanup(p.stop)
        self.app=create_app(self.env)

    def test_health_has_no_provider_calls(self):
        with patch('flight_display.service.Service.get',side_effect=AssertionError('No FR24 calls')):
            with TestClient(self.app,base_url='http://localhost',client=('127.0.0.1',1)) as c:
                self.assertEqual(c.get('/healthz').json(),{'status':'ok'})

    def test_proxy_allows_exact_host_and_origin(self):
        with TestClient(self.app,base_url='http://flight.example.ts.net',client=('127.0.0.1',1)) as c:
            state=c.get('/api/config').json()
            headers={'origin':'https://flight.example.ts.net','x-calibration-token':state['token']}
            self.assertEqual(c.post('/api/snapshot',json={},headers=headers).status_code,200)
            headers['origin']='https://other.example.ts.net'
            self.assertEqual(c.post('/api/snapshot',json={},headers=headers).status_code,403)

    def test_forged_forward_headers_cannot_bypass_loopback(self):
        with TestClient(self.app,base_url='https://flight.example.ts.net',client=('192.0.2.1',1)) as c:
            self.assertEqual(c.get('/healthz',headers={'x-forwarded-for':'127.0.0.1'}).status_code,403)

    def test_arbitrary_tailnet_host_is_not_allowed(self):
        with TestClient(self.app,base_url='https://other.example.ts.net',client=('127.0.0.1',1)) as c:
            self.assertEqual(c.get('/api/config').status_code,403)
