import contextlib
from dataclasses import replace
from datetime import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from flight_display.config import Settings
from flight_display.provider import MockProvider
from flight_display.service import Service
from flight_display.app import create_app
from scripts.security_check import scan, private_values

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.env=self.root/"config.env"
    def tearDown(self):self.temp.cleanup()
    def write_env(self,text):
        self.env.write_text(text);self.env.chmod(0o600)
    def test_synthetic_defaults_without_local_file(self):
        s=Settings.load(self.env,environ={})
        self.assertEqual((s.center_lat,s.center_lon,s.airport,s.timezone),(0,0,"XXX","UTC"))
    def test_private_env_and_environment_precedence(self):
        self.write_env("FLIGHT_CENTER_LAT=12.25\nFLIGHT_CENTER_LON=34.75\nFLIGHT_AIRPORT=ZZZ\n")
        s=Settings.load(self.env,environ={"FLIGHT_AIRPORT":"YYY"})
        self.assertEqual((s.center_lat,s.center_lon,s.airport),(12.25,34.75,"YYY"))
    def test_no_env_interpolation(self):
        self.write_env("FR24_API_KEY=${NOT_A_REAL_KEY}\n")
        s=Settings.load(self.env,environ={})
        self.assertEqual(s.api_key,"${NOT_A_REAL_KEY}")
        self.assertNotIn(s.api_key,repr(s))
    def test_invalid_private_values_never_echo(self):
        for value in ["nan","999","private-invalid-value"]:
            self.write_env("FLIGHT_CENTER_LAT="+value)
            with self.assertRaises(ValueError) as error:Settings.load(self.env,environ={})
            self.assertNotIn(value,str(error.exception))
    def test_incomplete_personal_profile_rejected(self):
        self.write_env("FLIGHT_PROFILE=personal")
        with self.assertRaises(ValueError):Settings.load(self.env,environ={})
    def test_unsafe_env_permissions_rejected(self):
        self.write_env("FLIGHT_PROFILE=demo")
        self.env.chmod(0o644)
        with self.assertRaises(ValueError):Settings.load(self.env,environ={})
    def test_env_symlink_rejected(self):
        real=self.root/"real";real.write_text("FLIGHT_PROFILE=demo");real.chmod(0o600)
        self.env.symlink_to(real)
        with self.assertRaises(ValueError):Settings.load(self.env,environ={})
    def test_invalid_schedules_rejected(self):
        for spans in ["25:00-26:00","10:00-09:00","09:01-10:00",""]:
            self.write_env("FLIGHT_WEEKDAY_WINDOWS="+spans)
            with self.assertRaises(ValueError):Settings.load(self.env,environ={})
    def test_private_geography_used_but_not_serialized(self):
        settings=Settings(center_lat=12.25,center_lon=34.75,airport="ZZZ",api_key="unit"+"test-private-key")
        svc=Service(self.root/"test.db",MockProvider("multiple",settings),settings=settings)
        result=svc.get(datetime.fromisoformat("2026-09-25T10:00:00+00:00"))
        self.assertEqual(result.category,"inbound")
        self.assertEqual(result.flight.destination,"ZZZ")
        encoded=result.model_dump_json()
        for forbidden in ["12.25","34.75",settings.api_key,"center_lat",'"lat"','"lon"']:
            self.assertNotIn(forbidden,encoded)
        class ClockService:
            def get(self):return result
        with TestClient(create_app(ClockService())) as client:
            self.assertNotIn(settings.api_key,client.get("/openapi.json").text)
    def test_configuration_changes_ranking_and_filtering(self):
        settings=Settings(center_lat=12.25,center_lon=34.75,airport="ZZZ",radius_km=1)
        svc=Service(self.root/"small.db",MockProvider("inbound",settings),settings=settings)
        self.assertEqual(svc.get(datetime.fromisoformat("2026-09-25T10:00:00+00:00")).status,"empty")

class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        subprocess.run(["git","init","-q",str(self.root)],check=True)
        (self.root/".gitignore").write_text(".private/\n.env*\n")
        (self.root/".private/tools").mkdir(parents=True)
        # Tests use the same checksum-verified scanner as the installed local hook.
        repository=Path(__file__).resolve().parents[2]
        scanner=repository/".private/tools/gitleaks"
        self.has_scanner=scanner.exists()
        if self.has_scanner:(self.root/".private/tools/gitleaks").symlink_to(scanner)
        (self.root/".gitleaks.toml").write_text((repository/".gitleaks.toml").read_text())
    def tearDown(self):self.temp.cleanup()
    def stage(self,name):subprocess.run(["git","add","-f","--",name],cwd=self.root,check=True)
    def run_scan(self,staged=False):
        output=io.StringIO()
        with patch.dict(os.environ,{"FLIGHT_ENV_FILE":str(self.root/".env")}),contextlib.redirect_stdout(output):
            code=scan(self.root,staged)
        return code,output.getvalue()
    def test_forced_env_file_blocked(self):
        (self.root/".env.production").write_text("NOT_A_KEY=private")
        self.stage(".env.production")
        self.assertEqual(self.run_scan(True)[0],1)
    def test_staged_blob_checked_even_if_worktree_cleaned(self):
        marker="private"+"-sentinel-value"
        (self.root/".private/privacy-values.json").write_text(json.dumps([marker]))
        (self.root/"notes.md").write_text(marker);self.stage("notes.md")
        (self.root/"notes.md").write_text("now safe")
        code,out=self.run_scan(True)
        self.assertEqual(code,1);self.assertNotIn(marker,out)
    def test_ignored_private_values_do_not_fail_safe_candidates(self):
        if not self.has_scanner:self.skipTest("Install verified scanner for integration test")
        (self.root/".env").write_text("FR24_API_KEY="+"unit"+"test-only-private-value")
        (self.root/"README.md").write_text("Synthetic mock only")
        self.assertEqual(self.run_scan()[0],0)
    def test_nonempty_provider_key_is_detected_and_not_printed(self):
        if not self.has_scanner:self.skipTest("Install verified scanner for integration test")
        marker="unit"+"test"+"0123456789abcdef"
        (self.root/"bad.txt").write_text("FR24_API_KEY="+marker)
        self.stage("bad.txt")
        code,out=self.run_scan(True)
        self.assertEqual(code,1);self.assertNotIn(marker,out)
    def test_missing_scanner_fails_closed(self):
        (self.root/".private/tools/gitleaks").unlink(missing_ok=True)
        (self.root/"README.md").write_text("Synthetic mock only")
        self.assertEqual(self.run_scan()[0],1)
    def test_personal_url_blocked_without_local_denylist(self):
        (self.root/"notes.md").write_text("https://"+"example-private"+".atlassian.net")
        self.assertEqual(self.run_scan()[0],1)
    def test_private_file_symlink_blocked(self):
        (self.root/".private/note").write_text("private")
        (self.root/"notes.md").symlink_to(self.root/".private/note")
        self.assertEqual(self.run_scan()[0],1)
