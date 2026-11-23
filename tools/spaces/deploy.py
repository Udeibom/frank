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
    if which == "ears":
        worker(api, repo)
    try:
        api.request_space_hardware(repo, "zero-a10g")
    except Exception as e:  # noqa: BLE001
        print("hardware request:", e)
    print("uploaded", repo, api.get_space_runtime(repo).stage)
    return 0


# The job worker (core-path spec 15) runs the backend's own code on frank-ears. Only code goes up: never .env,
# tests, local assets or environments. Secrets are set as Space secrets, read from backend/.env here.
WORKER_FILES = ["app/*.py", "app/**/*.py", "app/services/generation/styles/*.json", "requirements.txt",
                "scripts/fetch_soundfont.sh", "scripts/fetch_samples.sh", "scripts/build_words_db.py"]
WORKER_SECRETS = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "FREESOUND_API_KEY",
                  "JAMENDO_CLIENT_ID", "EXA_API_KEY", "FIRECRAWL_API_KEY"]


def _env() -> dict[str, str]:
    out = {}
    for line in (ROOT / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def worker(api: HfApi, repo: str) -> None:
    api.upload_folder(folder_path=str(ROOT / "backend"), repo_id=repo, repo_type="space", path_in_repo="worker",
                      allow_patterns=WORKER_FILES, ignore_patterns=["**/__pycache__/**", "**/.env*"],
                      commit_message="Worker code from github.com/Udeibom/frank backend")
    env = _env()
    for k in WORKER_SECRETS:
        if env.get(k):
            api.add_space_secret(repo, k, env[k])
    # The worker calls frank-ears and frank-hands too, with the read token the API uses.
    spaces_token = env.get("SPACES_TOKEN") or env.get("HF_TOKEN")
    if spaces_token:
        api.add_space_secret(repo, "SPACES_TOKEN", spaces_token)
    api.add_space_variable(repo, "ENVIRONMENT", "production")
    print("worker code and", len(WORKER_SECRETS), "secrets set on", repo)


if __name__ == "__main__":
    sys.exit(main())
