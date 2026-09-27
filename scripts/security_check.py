"""Scan public candidates or the entire staged snapshot. Never print secret values."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def git(root,*args):
    return subprocess.check_output(["git",*args],cwd=root)

def private_values(root):
    values=[]
    path=root/".private/privacy-values.json"
    if path.exists(): values.extend(json.loads(path.read_text()))
    # Deliberately simple: private dotenv lines; no interpolation or execution.
    path=Path(os.environ.get("FLIGHT_ENV_FILE",root/".env"))
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" not in line or line.lstrip().startswith("#"):continue
            key,value=line.split("=",1)
            if key.strip() in {"FR24_API_KEY","FR24_SANDBOX_TOKEN","FR24_PROD_TOKEN","FLIGHT_CENTER_LAT","FLIGHT_CENTER_LON","FLIGHT_AIRPORT","FLIGHT_TIMEZONE"}:
                value=value.strip().strip("\"'")
                if value and value not in {"0","0.0","XXX","UTC"}:values.append(value)
    return [v for v in values if isinstance(v,str) and len(v)>=3]

def prohibited(path):
    p=Path(path)
    return (any(part in {".private",".pio","__pycache__",".venv"} for part in p.parts)
        or (any(part.startswith(".env") for part in p.parts) and path!=".env.example")
        or (p.parts[0]=="artifacts" and path!="artifacts/.gitkeep")
        or p.name.startswith("secrets.") or p.name.startswith("credentials")
        or p.suffix.lower() in {".pem",".key",".p12",".pfx",".db",".sqlite",".sqlite3",".bin",".elf",".log"})

def collect(root,staged):
    if staged:
        for entry in git(root,"ls-files","--stage","-z").split(b"\0"):
            if not entry:continue
            meta,name=entry.split(b"\t",1);mode,oid,stage=meta.split()
            path=name.decode()
            if stage!=b"0" or mode not in {b"100644",b"100755"}:
                yield path,None
            else:yield path,git(root,"cat-file","blob",oid.decode())
    else:
        paths=git(root,"ls-files","--cached","--others","--exclude-standard","-z").split(b"\0")
        for name in sorted(set(paths)):
            if not name:continue
            path=name.decode();p=root/path
            if not p.exists():continue
            yield path,None if p.is_symlink() or not p.is_file() else p.read_bytes()

def scan(root,staged=False):
    denied=private_values(root)
    failures=[]
    personal_patterns=[r"https?://[a-zA-Z0-9-]+\.atlassian\.net",r"/Users/[A-Za-z0-9_.-]+/",r"/home/[A-Za-z0-9_.-]+/"]
    with tempfile.TemporaryDirectory(prefix="public-scan-") as tmp:
        snapshot=Path(tmp)
        for path,data in collect(root,staged):
            if prohibited(path) or data is None or len(data)>2_000_000:
                failures.append((path,"private path, unsupported entry or oversized file"));continue
            content=data.decode("utf-8",errors="replace")
            if any(re.search(r"(?<!\w)"+re.escape(v)+r"(?!\w)",content,re.IGNORECASE) for v in denied):
                failures.append((path,"matches private local configuration"));continue
            if any(re.search(pattern,content) for pattern in personal_patterns):
                failures.append((path,"contains personal URL or machine path"));continue
            dest=snapshot/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        if failures:
            for path,reason in failures:print(f"BLOCKED: {path}: {reason}")
            return 1
        scanner=root/".private/tools/gitleaks"
        if not scanner.exists():
            print("BLOCKED: install the scanner with python3 scripts/install_security.py")
            return 1
        # Scan exactly the chosen snapshot, including a forced-added ignored file.
        # Keep findings off stdout/stderr even if a vendor redaction rule misses a format.
        result=subprocess.run([str(scanner),"dir",str(snapshot),"--config",str(root/".gitleaks.toml"),"--redact","--no-banner"],capture_output=True)
        if result.returncode:
            print("BLOCKED: credential scanner reported a finding or could not complete. Inspect locally with redaction; do not publish.")
            return 1
    print("Public-file privacy and credential checks passed.")
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged",action="store_true")
    group.add_argument("--all",action="store_true")
    args=parser.parse_args()
    raise SystemExit(scan(ROOT,args.staged))
