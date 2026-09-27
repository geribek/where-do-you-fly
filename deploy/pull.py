"""Root-owned Pi updater. Never executes downloaded scripts or prints env/logs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

def image_ref(repository, digest):
    if not re.fullmatch(r"ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+", repository):
        raise ValueError("Invalid registry repository")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("Invalid image digest")
    return repository + "@" + digest

def atomic_json(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w") as f:
        json.dump(value, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

class Deployment:
    def __init__(self, config):
        self.config = config
        self.repository = config["repository"]
        image_ref(self.repository, "sha256:" + "0"*64)
        if config["channel"] not in {"sandbox", "prod"}:
            raise ValueError("Invalid release channel")
        if not 1024 <= int(config["port"]) <= 65535:
            raise ValueError("Invalid local port")
        self.state_dir = Path(config["state_dir"])
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.state_dir / "release.json"

    def command(self, args, env=None, timeout=300):
        return subprocess.run(args, env=env, check=True, capture_output=True,
                              text=True, timeout=timeout).stdout.strip()

    def resolve(self):
        tag = self.repository + ":" + self.config["channel"]
        self.command(["docker", "pull", tag], timeout=900)
        digests = json.loads(self.command(["docker", "image", "inspect", tag, "--format", "{{json .RepoDigests}}"] ))
        for ref in digests or []:
            if ref.startswith(self.repository + "@"):
                return image_ref(self.repository, ref.split("@",1)[1])
        raise ValueError("Image has no repository digest")

    def activate(self, ref):
        image_ref(self.repository, ref.split("@",1)[1])
        env = dict(os.environ, FLIGHT_IMAGE=ref, FLIGHT_CHANNEL=self.config["channel"],
                   APP_PORT=str(self.config["port"]), CONFIG_DIR=self.config["config_dir"],
                   DATA_DIR=self.config["data_dir"])
        self.command(["docker", "compose", "--project-name", "flight-"+self.config["channel"],
                      "-f", self.config["compose"], "up", "-d", "--wait", "--wait-timeout", "90", "--pull", "never"], env=env)

    def backup(self):
        # Online SQLite backup, not a file copy. Never automatically restore spend state.
        backups = self.state_dir / "backup"
        backups.mkdir(exist_ok=True, mode=0o700)
        for path in Path(self.config["data_dir"]).glob("flights.sqlite3*"):
            if path.name.endswith(("-wal", "-shm", "-journal")): continue
            with sqlite3.connect(str(path)) as source, sqlite3.connect(str(backups/path.name)) as target:
                source.backup(target)

    def run(self, retry=False):
        state = json.loads(self.path.read_text()) if self.path.exists() else {}
        previous = state.get("current")
        if state.get("pending"):
            # Recover an interrupted activation before considering any new release.
            if previous: self.activate(previous)
            state["failed"] = state.pop("pending")
            atomic_json(self.path, state)
        candidate = self.resolve()
        if candidate == state.get("failed") and not retry:
            print("Failed release suppressed; operator retry or new release required")
            return
        if candidate == previous:
            print("Already on approved release")
            return
        self.backup()
        state["pending"] = candidate
        atomic_json(self.path, state)
        try:
            self.activate(candidate)
        except (subprocess.SubprocessError, OSError, ValueError):
            if previous: self.activate(previous)
            state.pop("pending")
            state["failed"] = candidate
            atomic_json(self.path, state)
            raise RuntimeError("Release failed; previous release restored if available") from None
        atomic_json(self.path, {"current":candidate, "previous":previous})
        print("Approved release healthy")

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--retry", action="store_true")
    args=parser.parse_args()
    try:
        deployment=Deployment(json.loads(Path(args.config).read_text()))
        with (deployment.state_dir / "lock").open("w") as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return
            deployment.run(args.retry)
    except Exception:
        # Docker output can contain deployment paths/config; keep system journal generic.
        print("Deployment failed; inspect private state locally. No secrets logged.")
        raise SystemExit(1) from None

if __name__ == "__main__": main()
