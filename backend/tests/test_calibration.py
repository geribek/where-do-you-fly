import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from dotenv import dotenv_values
from flight_display.calibration import create_app

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/".env"
        # Public synthetic marker: never load real credentials into this fixture.
        self.fixture_marker="unit-test-not-a-real-key"
        self.path.write_text("# preserve this comment\nFLIGHT_PROFILE=demo\nFLIGHT_AIRPORT=XXX\nFR24_API_KEY"+"="+self.fixture_marker+"\nFLIGHT_WEEKDAY_WINDOWS=09:00-17:00\n")
        self.path.chmod(0o600)
        self.environment=patch.dict(os.environ,{},clear=True);self.environment.start()
        self.client=TestClient(create_app(self.path),base_url="http://localhost",client=("127.0.0.1",50000))
        self.state=self.client.get('/api/config').json()
    def tearDown(self):self.client.close();self.environment.stop();self.tmp.cleanup()
    def payload(self):return {"latitude":12.25,"longitude":34.75,"airport":"ZZZ","radius_km":8.5,"revision":self.state['revision']}
    def save(self,payload=None,**kwargs):return self.client.post('/api/config',json=payload or self.payload(),headers={"x-calibration-token":self.state['token']},**kwargs)
    def test_config_only_exposes_allowed_fields_and_no_secrets(self):
        self.assertEqual(set(self.state),{'latitude','longitude','airport','radius_km','revision','token','mode','environment_overrides'})
        self.assertNotIn(self.fixture_marker,json.dumps(self.state))
        self.assertEqual(self.state['mode'],'mock')
    def test_snapshot_requires_same_origin_session_token(self):
        self.assertEqual(self.client.post('/api/snapshot',json={}).status_code,403)
        response=self.client.post('/api/snapshot',json={},headers={'x-calibration-token':self.state['token']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['mode'],'mock')
        self.assertNotIn(self.fixture_marker,response.text)
    def test_private_save_preserves_other_settings_and_permissions(self):
        result=self.save();self.assertEqual(result.status_code,200)
        data=dotenv_values(self.path)
        self.assertEqual(data['FR24_API_KEY'],self.fixture_marker)
        self.assertEqual(data['FLIGHT_WEEKDAY_WINDOWS'],'09:00-17:00')
        self.assertEqual(data['FLIGHT_AIRPORT'],'ZZZ')
        self.assertEqual(data['FLIGHT_RADIUS_KM'],'8.5')
        self.assertIn('# preserve this comment',self.path.read_text())
        self.assertEqual(self.path.stat().st_mode&0o777,0o600)
    def test_remote_client_and_host_blocked(self):
        for host,client in [('http://localhost',('192.0.2.1',123)),('http://example.com',('127.0.0.1',123))]:
            with TestClient(create_app(self.path),base_url=host,client=client) as c:self.assertEqual(c.get('/api/config').status_code,403)
    def test_explicit_container_proxy_allows_configured_local_origin(self):
        self.path.write_text(self.path.read_text()+"FLIGHT_WEB_ORIGIN=http://localhost:8001\nFLIGHT_ALLOW_CONTAINER_PROXY=true\n")
        with TestClient(create_app(self.path),base_url='http://localhost:8001',client=('172.18.0.2',123)) as client:
            self.assertEqual(client.get('/api/config').status_code,200)
            self.assertEqual(client.get('/api/config',headers={'host':'127.0.0.1:8001'}).status_code,403)
    def test_cross_origin_and_missing_token_cannot_write(self):
        before=self.path.read_bytes()
        self.assertEqual(self.client.post('/api/config',json=self.payload()).status_code,403)
        response=self.client.post('/api/config',json=self.payload(),headers={'x-calibration-token':self.state['token'],'Origin':'https://example.com'})
        self.assertEqual(response.status_code,403);self.assertEqual(before,self.path.read_bytes())
    def test_invalid_input_is_not_reflected(self):
        for changes in [{'latitude':999},{'airport':'private-invalid-input'},{'radius_km':0},{'extra':'private-invalid-input'}]:
            response=self.save({**self.payload(),**changes})
            self.assertEqual(response.status_code,422)
            self.assertEqual(response.json(),{'detail':'Invalid calibration settings'})
    def test_stale_revision_rejected(self):
        self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.save().status_code,409)
    def test_external_edit_requires_reload(self):
        self.path.write_text(self.path.read_text()+'OTHER_VALUE=preserve\n')
        self.assertEqual(self.save().status_code,409)
        self.state=self.client.get('/api/config').json()
        self.assertEqual(self.save().status_code,200)
        self.assertIn('OTHER_VALUE=preserve',self.path.read_text())
    def test_private_headers_and_static_assets(self):
        for path in ['/','/api/config','/assets/app.mjs','/assets/style.css','/assets/model.mjs']:
            response=self.client.get(path);self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertIn("frame-ancestors 'none'",response.headers['content-security-policy'])
        self.assertEqual(self.client.get('/assets/config.py').status_code,404)
    def test_example_and_symlink_destinations_rejected(self):
        with self.assertRaises(ValueError):create_app(Path(self.tmp.name)/'.env.example')
        link=Path(self.tmp.name)/'.env.link';link.symlink_to(self.path)
        with self.assertRaises(ValueError):create_app(link)
    def test_environment_override_is_reported(self):
        with patch.dict(os.environ,{'FLIGHT_RADIUS_KM':'10'}):
            response=self.client.get('/api/config').json()
            self.assertEqual(response['radius_km'],10)
            self.assertEqual(response['environment_overrides'],['FLIGHT_RADIUS_KM'])
    def test_helper_never_invokes_mock_or_live_provider(self):
        with patch('flight_display.provider.MockProvider.fetch',side_effect=AssertionError('provider forbidden')):
            self.assertEqual(self.client.get('/').status_code,200)
            self.assertEqual(self.client.get('/api/config').status_code,200)
            self.assertEqual(self.save().status_code,200)
