import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from deploy.pull import Deployment, atomic_json, image_ref

OLD = image_ref('ghcr.io/example/flight', 'sha256:'+'1'*64)
NEW = image_ref('ghcr.io/example/flight', 'sha256:'+'2'*64)

class PullTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d=Deployment({'repository':'ghcr.io/example/flight','channel':'sandbox','port':8001,
                           'state_dir':self.temp.name,'data_dir':self.temp.name,
                           'config_dir':self.temp.name,'compose':'deploy/compose.yaml'})
        self.resolve=patch.object(self.d,'resolve',return_value=NEW).start()
        self.activate=patch.object(self.d,'activate').start()
        self.backup=patch.object(self.d,'backup').start()
        self.addCleanup(patch.stopall)

    def state(self): return json.loads(self.d.path.read_text())

    def test_healthy_deployment(self):
        atomic_json(self.d.path,{'current':OLD})
        self.d.run()
        self.assertEqual(self.state(),{'current':NEW,'previous':OLD})
        self.activate.assert_called_once_with(NEW)
        self.backup.assert_called_once()

    def test_same_digest_is_noop(self):
        atomic_json(self.d.path,{'current':NEW})
        self.d.run()
        self.activate.assert_not_called()
        self.backup.assert_not_called()

    def test_failure_rolls_back_and_suppresses_retry(self):
        atomic_json(self.d.path,{'current':OLD})
        self.activate.side_effect=[subprocess.CalledProcessError(1,'docker'),None]
        with self.assertRaises(RuntimeError): self.d.run()
        self.assertEqual([c.args[0] for c in self.activate.call_args_list],[NEW,OLD])
        self.assertEqual(self.state()['failed'],NEW)
        self.activate.reset_mock()
        self.d.run()
        self.activate.assert_not_called()

    def test_interrupted_update_recovers_before_check(self):
        atomic_json(self.d.path,{'current':OLD,'pending':NEW})
        self.d.run()
        self.activate.assert_called_once_with(OLD)
        self.assertEqual(self.state()['failed'],NEW)
        self.assertNotIn('pending',self.state())

    def test_offline_preserves_current(self):
        atomic_json(self.d.path,{'current':OLD})
        self.resolve.side_effect=subprocess.TimeoutExpired('docker',30)
        with self.assertRaises(subprocess.TimeoutExpired): self.d.run()
        self.assertEqual(self.state(),{'current':OLD})
        self.activate.assert_not_called()

    def test_explicit_retry(self):
        atomic_json(self.d.path,{'current':OLD,'failed':NEW})
        self.d.run(retry=True)
        self.assertEqual(self.state()['current'],NEW)

    def test_rollback_failure_keeps_pending_for_recovery(self):
        atomic_json(self.d.path,{'current':OLD})
        self.activate.side_effect=subprocess.CalledProcessError(1,'docker')
        with self.assertRaises(subprocess.CalledProcessError): self.d.run()
        self.assertEqual(self.state()['pending'],NEW)

    def test_rejects_foreign_registry_and_mutable_digest(self):
        with self.assertRaises(ValueError): image_ref('attacker.example/flight','sha256:'+'1'*64)
        with self.assertRaises(ValueError): image_ref('ghcr.io/example/flight','latest')

    def test_backup_preserves_live_ledger(self):
        import sqlite3
        from deploy.pull import Deployment
        db=Path(self.temp.name)/'flights.sqlite3.prod'
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE ledger(credits INTEGER)')
            c.execute('INSERT INTO ledger VALUES (123)')
        Deployment.backup(self.d)
        with sqlite3.connect(Path(self.temp.name)/'backup'/db.name) as c:
            self.assertEqual(c.execute('SELECT credits FROM ledger').fetchone()[0],123)
        with sqlite3.connect(db) as c:
            self.assertEqual(c.execute('SELECT credits FROM ledger').fetchone()[0],123)
