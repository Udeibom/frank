"""
Run the live checks from a Kaggle kernel instead of this machine.

Why: on 21 Nov this machine's network began dropping any request to Render larger than about 700 bytes (a signed-in
request carries a ~1 KB token), while the same requests from Kaggle reached Render normally. The checks still run
against the deployed site; only where they run from changes.

What leaves this machine: the check scripts, the public anon key, and the email and password of a throwaway
account created here. The account is deleted here when the kernel finishes, whatever happens. The service role key
never leaves this machine.

  python scripts/ops/run_on_kaggle.py e2e_frankenstein.py e2e.py
Needs KAGGLE_KEY in backend/.env and the kaggle CLI from tools/spaces/.venv.
"""
from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid
import httpx
from dotenv import dotenv_values
OPS = pathlib.Path(__file__).resolve().parent
ROOT = OPS.parents[1]
ENV = dotenv_values(ROOT / ".env")
FENV = dotenv_values(ROOT.parent / "frontend" / ".env.local")
SB, SRK, ANON = ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"], FENV["NEXT_PUBLIC_SUPABASE_ANON_KEY"]
ADMIN = {"apikey": SRK, "Authorization": f"Bearer {SRK}"}
KAGGLE = str(ROOT.parent / "tools" / "spaces" / ".venv" / "bin" / "kaggle")
KERNEL = "calebudeibom/frank-live-checks"
RUNNER = '''
import os, subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "python-dotenv", "soundfile", "httpx", "numpy"], check=False)
os.environ.update(%(env)r)
for name, src in %(sources)r.items():
    open(name, "w").write(src)
failed = 0
for name in %(order)r:
    print("=" * 30, name, flush=True)
    failed += subprocess.run([sys.executable, "-u", name]).returncode != 0
print("=" * 30, "ALL DONE", "failures:", failed)
'''
def main(scripts: list[str]) -> int:
    email, pw = f"kaggle-{uuid.uuid4().hex[:8]}@example.com", f"K-{uuid.uuid4().hex}"
    r = httpx.post(f"{SB}/auth/v1/admin/users", headers=ADMIN, json={"email": email, "password": pw, "email_confirm": True}, timeout=60)
    r.raise_for_status()
    uid = r.json()["id"]
    print("throwaway account", email)
    try:
        sources = {"e2e.py": (OPS / "e2e.py").read_text(), "core_audio.py": (OPS / "core_audio.py").read_text(),
                   "e2e_core.py": (OPS / "e2e_core.py").read_text()}
        sources.update({s: (OPS / s).read_text() for s in scripts})
        env = {"SUPABASE_URL": SB, "SUPABASE_ANON_KEY": ANON, "FRANK_EMAIL": email, "FRANK_PASSWORD": pw,
               "E2E_SING": os.environ.get("E2E_SING", "1")}
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "run.py").write_text(RUNNER % {"env": env, "sources": sources, "order": scripts})
            pathlib.Path(d, "kernel-metadata.json").write_text(json.dumps({
                "id": KERNEL, "title": "frank-live-checks", "code_file": "run.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_internet": True,
                "dataset_sources": [], "competition_sources": [], "kernel_sources": []}))
            kenv = {**os.environ, "KAGGLE_API_TOKEN": ENV["KAGGLE_KEY"]}
            subprocess.run([KAGGLE, "kernels", "push", "-p", d], check=True, env=kenv)
            while True:
                time.sleep(30)
                st = subprocess.run([KAGGLE, "kernels", "status", KERNEL], capture_output=True, text=True, env=kenv).stdout
                if "COMPLETE" in st or "ERROR" in st or "CANCEL" in st:
                    break
            print(st.strip())
            subprocess.run([KAGGLE, "kernels", "output", KERNEL, "-p", d, "--file-pattern", r".*\.log"],
                           capture_output=True, env=kenv)
            logs = list(pathlib.Path(d).glob("*.log"))
            text = "".join(e.get("data", "") for e in json.loads(logs[0].read_text())) if logs else "(no log)"
        out = pathlib.Path.home() / "frank-listening" / f"kaggle-checks-{time.strftime('%Y%m%d-%H%M')}.log"
        out.write_text(text)
        print(text[-6000:])
        print("full log:", out)
        return 0 if "failures: 0" in text else 1
    finally:
        httpx.delete(f"{SB}/auth/v1/admin/users/{uid}", headers=ADMIN, timeout=60)
        print("throwaway account deleted")
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["e2e_frankenstein.py", "e2e.py"]))
