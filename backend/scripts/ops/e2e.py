"""
End-to-end check over real HTTP (ship-it spec 13): a throwaway account goes project -> feel -> lyrics -> beat ->
vocal take -> mix -> listen -> export -> download, against FRANK_API (default: the deployed backend).
The account is deleted at the end; the project stays (projects are never deleted) and is titled "E2E song".

  FRANK_API=http://localhost:8000 python scripts/ops/e2e.py
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import time
import uuid

import httpx
import numpy as np
import soundfile as sf
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV = dotenv_values(ROOT / ".env")
FENV = dotenv_values(ROOT.parent / "frontend" / ".env.local")
SB, SRK, ANON = ENV["SUPABASE_URL"], ENV["SUPABASE_SERVICE_ROLE_KEY"], FENV["NEXT_PUBLIC_SUPABASE_ANON_KEY"]
API = os.environ.get("FRANK_API", "https://frank-api-pzjo.onrender.com")
ADMIN = {"apikey": SRK, "Authorization": f"Bearer {SRK}"}
c = httpx.Client(timeout=180)


def login() -> tuple[str, dict]:
    email, pw = f"e2e-{uuid.uuid4().hex[:8]}@example.com", "E2e-pass-12345"
    r = c.post(f"{SB}/auth/v1/admin/users", headers=ADMIN, json={"email": email, "password": pw, "email_confirm": True})
    r.raise_for_status()
    tok = c.post(f"{SB}/auth/v1/token?grant_type=password", headers={"apikey": ANON}, json={"email": email, "password": pw}).json()["access_token"]
    return r.json()["id"], {"Authorization": f"Bearer {tok}"}


def call(h: dict, method: str, path: str, **kw):
    for attempt in range(30):
        try:
            r = c.request(method, API + path, headers=h, **kw)
        except httpx.HTTPError:
            time.sleep(15)                              # this machine's network dropped, not the server
            continue
        if r.status_code in (502, 503) and attempt < 2:
            time.sleep(20)                              # server restarting: say so in the output and try again
            print("  (server unavailable, retrying)", method, path)
            continue
        if r.status_code >= 400:
            print("FAIL", method, path, r.status_code, r.text[:300])
            sys.exit(1)
        return r.json() if r.content else None


def job(h: dict, job_id: str, label: str) -> dict:
    t = time.time()
    while True:
        j = call(h, "GET", f"/jobs/{job_id}/status")
        if j["status"] in ("complete", "failed"):
            print(f"  {label}: {j['status']} in {time.time() - t:.0f}s", j.get("error") or "")
            if j["status"] == "failed":
                sys.exit(1)
            return j["result"]
        time.sleep(3)


def sung_take() -> bytes:
    sr = 44100
    segs = []
    for n in [57, 60, 64, 62, 60, 57, 59, 57]:
        t = np.arange(int(0.9 * sr)) / sr
        f = 440 * 2 ** ((n + 12 - 69) / 12)
        y = sum(a * np.sin(2 * np.pi * f * k * t + 0.4 * np.sin(2 * np.pi * 5 * t)) for k, a in ((1, .5), (2, .25), (3, .1)))
        segs += [y * np.hanning(t.size) * 0.5, np.zeros(int(0.25 * sr))]
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(segs).astype(np.float32), sr, format="WAV")
    return buf.getvalue()


def main() -> None:
    uid, h = login()
    started = time.time()
    try:
        pid = call(h, "POST", "/projects", json={"title": "E2E song"})["id"]
        print("project", pid)
        fp = {"tempo_bpm": 88, "key": "A minor", "mode": "minor", "energy_level": 0.55, "density": 0.45, "brightness": 0.35,
              "warmth": 0.7, "tempo_feel": "steady", "genre_proximity": ["soul"], "instrumentation_hints": ["piano"]}
        call(h, "POST", f"/projects/{pid}/feel/fingerprint", json={"fingerprint": fp, "conversation_summary": "warm and slow"})
        call(h, "POST", f"/projects/{pid}/lyrics", json={"content": "I walk alone down the quiet road\nThe lights are low and the night is cold\nBut I will sing until the morning comes", "label": "v1"})
        res = job(h, call(h, "POST", f"/projects/{pid}/beat/generate", json={"fingerprint": fp})["job_id"], "beat")
        print("  beat", {k: v for k, v in res.items() if k != "render_url"})
        up = call(h, "POST", f"/projects/{pid}/voice/takes", files={"file": ("take.wav", sung_take(), "audio/wav")})
        tid = up.get("id") or (up.get("take") or {}).get("id")
        call(h, "POST", f"/projects/{pid}/voice/active", json={"vocal_id": tid, "vocal_type": "take"})
        time.sleep(8)
        mixid = job(h, call(h, "POST", f"/projects/{pid}/mix/render", json={"mix_params": {}, "quality": "full"})["job_id"], "mix")["mix_version_id"]
        listened = job(h, call(h, "POST", f"/projects/{pid}/listen", json={"concern": "the chorus doesn't lift"})["job_id"], "listen")
        for f in listened["findings"]["findings"]:
            print("   -", f["severity"], f["plain"])
        job(h, call(h, "POST", f"/projects/{pid}/export", json={"mix_version_id": mixid, "apply_mastering": True})["job_id"], "export")
        dl = call(h, "GET", f"/projects/{pid}/export")[0]
        mp3 = c.get(dl["audio_url"]).content
        print("  downloaded", len(mp3), "bytes", dl["format"], dl["quality"])
        print(f"E2E OK in {time.time() - started:.0f}s")
    finally:
        c.delete(f"{SB}/auth/v1/admin/users/{uid}", headers=ADMIN)


if __name__ == "__main__":
    main()
