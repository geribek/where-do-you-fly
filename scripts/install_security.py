"""Install a checksum-pinned scanner and this clone's pre-commit hook."""
from pathlib import Path
import hashlib
import io
import os
import platform
import subprocess
import tarfile
import urllib.request
VERSION="8.24.2"
BUILDS={
    ("Darwin","arm64"):("darwin_arm64","90d13686937ac7429b97a3acbf1e1d0ce90d92ae2d0cf46a690bd8ae5230bea0"),
    ("Linux","x86_64"):("linux_x64","fa0500f6b7e41d28791ebc680f5dd9899cd42b58629218a5f041efa899151a8e"),
}
def main():
    root=Path(__file__).resolve().parents[1]
    target=root/".private/tools/gitleaks"
    if (platform.system(),platform.machine()) not in BUILDS:
        raise SystemExit("No checksum-pinned build for this host; add a verified build before committing.")
    build,expected=BUILDS[(platform.system(),platform.machine())]
    url=f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{build}.tar.gz"
    data=urllib.request.urlopen(url,timeout=60).read()
    if hashlib.sha256(data).hexdigest()!=expected:
        raise SystemExit("Scanner download checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
        binary=archive.extractfile("gitleaks").read()
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    target.write_bytes(binary);target.chmod(0o700)
    hook=root/".githooks/pre-commit";hook.chmod(0o755)
    current=subprocess.run(["git","config","--get","core.hooksPath"],cwd=root,capture_output=True,text=True).stdout.strip()
    if current and current!=".githooks":
        raise SystemExit("Existing custom hooksPath preserved; integrate the security hook before committing.")
    subprocess.run(["git","config","--local","core.hooksPath",".githooks"],cwd=root,check=True)
    print("Verified scanner installed; local pre-commit guard enabled.")
if __name__=="__main__":main()
