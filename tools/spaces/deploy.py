"""
Deploy Frank's Spaces (frankenstein spec 14, sections D and E).

  tools/spaces/.venv/bin/python tools/spaces/deploy.py ears|hands [--status] [--logs]

Creates the Space if needed (Gradio, ZeroGPU hardware), uploads spaces/frank-<name>/, and prints the build stage.
The token comes from SPACES_TOKEN, else HUGGINGFACE_API_KEY in backend/.env (it needs write access to repos).
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

from huggingface_hub import HfApi

ROOT = pathlib.Path(__file__).resolve().parents[2]
OWNER = "Udeibom"


def token() -> str:
    for k in ("SPACES_TOKEN", "HUGGINGFACE_API_KEY"):
        if os.environ.get(k):
            return os.environ[k]
    for line in (ROOT / "backend" / ".env").read_text().splitlines():
        for k in ("SPACES_TOKEN=", "HUGGINGFACE_API_KEY="):
            if line.startswith(k) and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    sys.exit("no Hugging Face token with write access found")


def main() -> int:
    which = sys.argv[1]
    repo = f"{OWNER}/frank-{which}"
    api = HfApi(token=token())
    if "--status" in sys.argv or "--logs" in sys.argv:
        rt = api.get_space_runtime(repo)
        print(rt.stage, rt.hardware, getattr(rt, "requested_hardware", None), rt.raw.get("errorMessage"))
        if "--logs" in sys.argv:
            import httpx

            for kind in ("build", "run"):
                try:
                    with httpx.stream("GET", f"https://huggingface.co/api/spaces/{repo}/logs/{kind}",
                                      headers={"Authorization": f"Bearer {token()}"}, timeout=20) as r:
                        lines = []
                        start = time.time()
                        for line in r.iter_lines():
                            if line.startswith("data:"):
                                lines.append(line[5:].strip())
                            if time.time() - start > 15:
                                break
                    print(f"--- {kind} log (last 40)"); print("\n".join(lines[-40:]))
                except Exception as e:  # noqa: BLE001
                    print(kind, "log unavailable:", e)
        return 0
    api.create_repo(repo, repo_type="space", space_sdk="gradio", exist_ok=True, space_hardware="zero-a10g")
    api.upload_folder(folder_path=str(ROOT / "spaces" / f"frank-{which}"), repo_id=repo, repo_type="space",
                      commit_message="Deploy from github.com/Udeibom/frank", ignore_patterns=["__pycache__/*", "*.pyc"])
    try:
        api.request_space_hardware(repo, "zero-a10g")
    except Exception as e:  # noqa: BLE001
        print("hardware request:", e)
    print("uploaded", repo, api.get_space_runtime(repo).stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
