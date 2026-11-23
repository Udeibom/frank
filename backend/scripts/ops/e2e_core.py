"""
The founder's path of 22 Nov, live (core-path spec 15, requirement 7): a slow worship song from a hum, "too
fast", "try something different", a 4-minute recording, the blend, listening, atmosphere and the finish, against
the deployed site. Every step is tried and reported; the summary ends with PASS/FAIL per requirement.
  python scripts/ops/run_on_kaggle.py e2e_core.py      (this machine's network drops large requests to Render)
Needs core_audio.py beside it.
"""
from __future__ import annotations

import io
import json
import sys
import time

import numpy as np
import soundfile as sf

from core_audio import long_take, slow_hum
from e2e import ADMIN, API, SB, c, login

CHECKS: list[tuple[str, bool, str]] = []
REGION = {"X-Frank-Region": "NG"}
LYRICS = ("Worthy of every breath we could ever breathe\nWorthy of every song we could ever sing\n"
          "Open up my eyes in wonder\nShow me who you are")


def check(name: str, ok: bool, note: str = "") -> bool:
    CHECKS.append((name, ok, note))
    print(("PASS " if ok else "FAIL ") + name + (": " + note[:300] if note else ""), flush=True)
    return ok


def call(h: dict, method: str, path: str, **kw):
    for attempt in range(10):
        try:
            r = c.request(method, API + path, headers={**h, **REGION}, timeout=180, **kw)
        except Exception as e:  # noqa: BLE001
            print("  (network, retrying)", type(e).__name__)
            time.sleep(10)
            continue
        if r.status_code in (502, 503, 504) and attempt < 9:
            print("  (server unavailable, retrying)", path)
            time.sleep(20)
            continue
        if r.status_code >= 400:
            return {"__error__": r.status_code, "detail": r.text[:400]}
        return r.json() if r.content else {}
    return {"__error__": "unreachable"}


def job(h: dict, started: dict, label: str, limit: float = 900) -> dict:
    if "job_id" not in (started or {}):
        print("  could not start", label, started)
        return {"__error__": started}
    t = time.time()
    waited = set()
    while time.time() - t < limit:
        j = call(h, "GET", f"/jobs/{started['job_id']}/status")
        if j.get("waiting") and j["waiting"] not in waited:
            waited.add(j["waiting"])
            print("   waiting:", j["waiting"])
        if j.get("status") in ("complete", "failed"):
            print(f"  {label}: {j['status']} in {time.time() - t:.0f}s", j.get("error") or "")
            return j.get("result") or {} if j["status"] == "complete" else {"__error__": j.get("error")}
        time.sleep(4)
    return {"__error__": f"still running after {limit:.0f}s"}


def seconds_of(url: str) -> float:
    y, sr = sf.read(io.BytesIO(c.get(url, timeout=120).content), always_2d=True)
    return len(y) / sr


def level(url: str, at: list[float]) -> list[float]:
    y, sr = sf.read(io.BytesIO(c.get(url, timeout=120).content), always_2d=True)
    y = y.mean(1)
    return [round(float(np.sqrt(np.mean(y[int(a * sr):int((a + 4) * sr)] ** 2))) if a * sr < len(y) else 0.0, 3) for a in at]


def main() -> None:
    uid, h = login()
    started = time.time()
    pid = None
    try:
        pid = call(h, "POST", "/projects", json={"title": "Core path run"})["id"]
        print("project", pid)
        p = f"/projects/{pid}"
        call(h, "POST", f"{p}/lyrics", json={"content": LYRICS, "label": "v1"})

        # Requirement 2.1: a slow worship hum is counted at a gentle speed
        hum = job(h, call(h, "POST", f"{p}/intake/hum", files={"file": ("hum.wav", slow_hum(69), "audio/wav")}), "hum")
        vid = hum.get("version_id")
        conf = call(h, "POST", f"{p}/intake/melody/{vid}/confirm") if vid else {}
        heard_bpm = (hum.get("sketch") or {}).get("tempo_bpm")
        bpm = (conf.get("fingerprint_hints") or {}).get("tempo_bpm") or ((conf.get("version") or {}).get("content") or {}).get("tempo_bpm")
        check("2.1 hum counted at a gentle speed", bool(bpm) and 55 <= float(bpm) <= 85, f"hum read at {heard_bpm}, song speed {bpm}")

        # Requirement 6.2: a reaction is not kept as the description
        said = call(h, "POST", f"{p}/feel/conversation", json={"message": "That one isn't quite it.", "fingerprint": {}, "history": []})
        intent = call(h, "GET", f"{p}/finish/intent")
        check("6.2 a reaction is not the song's description", "isn't quite it" not in json.dumps(intent), json.dumps(intent)[:200])

        # Requirement 4.1: "Try something different" sounds different
        fp = {**(conf.get("fingerprint_hints") or {}), "energy_level": 0.35, "density": 0.4, "tempo_feel": "floating"}
        t1 = job(h, call(h, "POST", f"{p}/feel/texture", json={"fingerprint": fp}), "direction 1")
        diff = call(h, "POST", f"{p}/feel/conversation", json={"message": "Try something quite different.", "fingerprint": fp, "history": []})
        fp2 = {**fp, **(diff.get("fingerprint_update") or {})}
        t2 = job(h, call(h, "POST", f"{p}/feel/texture", json={"fingerprint": fp2}), "direction 2")
        check("4.1 a different direction is a different sound",
              bool(t1.get("audio_url")) and bool(t2.get("audio_url")) and t1.get("texture_id") != t2.get("texture_id") and not t2.get("cached"),
              f"palette {fp.get('texture_palette')} -> {fp2.get('texture_palette')}, cached={t2.get('cached')}")
        call(h, "POST", f"{p}/feel/fingerprint", json={"fingerprint": fp2, "conversation_summary": "slow worship, full of wonder"})

        # Requirement 1: the music, then "too fast" -> really slower
        beat = job(h, call(h, "POST", f"{p}/beat/generate", json={"fingerprint": fp2}), "beat")
        versions = call(h, "GET", f"{p}/beat/versions")
        v1 = next((v for v in versions if v.get("id") == beat.get("beat_version_id")), {}) if isinstance(versions, list) else {}
        bpm1 = ((v1.get("params") or {}).get("fingerprint") or {}).get("tempo_bpm")
        check("2.1 the music is built at the gentle speed", bool(bpm1) and float(bpm1) <= 85, f"beat speed {bpm1}")
        reply = call(h, "POST", f"{p}/beat/conversation", json={"message": "It is too fast and random.", "beat_state": {}, "history": []})
        ops = [o for a in reply.get("actions", []) if a.get("type") == "beat_operations" for o in a["params"].get("operations", [])]
        check("2.3 'too fast' becomes a real slower change", any(o.get("op") == "slower" for o in ops), f"{reply.get('message')} | {ops}")
        slower = job(h, call(h, "POST", f"{p}/beat/operations", json={"operations": ops or [{"op": "slower"}]}), "slower")
        versions = call(h, "GET", f"{p}/beat/versions")
        v2 = next((v for v in versions if v.get("id") == slower.get("beat_version_id")), {}) if isinstance(versions, list) else {}
        bpm2 = ((v2.get("params") or {}).get("fingerprint") or {}).get("tempo_bpm")
        check("2.2 slower really changes the speed", bool(bpm2) and bpm1 and float(bpm2) < float(bpm1), f"{bpm1} -> {bpm2}; {slower.get('changes')}")

        # Requirement 1.5 and 3: a four-minute recording, analysed, then the blend lasts as long as the voice
        up = call(h, "POST", f"{p}/voice/takes", files={"file": ("take.wav", long_take(240, float(bpm2 or 60)), "audio/wav")})
        take = up.get("take") or {}
        check("5.2 a new recording is called a recording", (take.get("label") or "").startswith("Recording"), take.get("label") or "")
        analysis = job(h, {"job_id": up.get("analysis_job_id")}, "check the recording", 900) if up.get("analysis_job_id") else {"__error__": up}
        check("1.5 a 4-minute recording is checked without failing", "__error__" not in analysis, str(analysis)[:200])
        mix = job(h, call(h, "POST", f"{p}/mix/render", json={"mix_params": {}, "quality": "preview"}), "blend", 1200)
        ok_mix = "__error__" not in mix and bool(mix.get("render_url"))
        check("1.5 the blend of a 4-minute recording finishes", ok_mix, str(mix)[:200])
        if ok_mix:
            secs = seconds_of(mix["render_url"])
            lv = level(mix["render_url"], [30, 120, 200, 232])
            check("3.2 the music lasts as long as the voice", secs >= 238, f"blend {secs:.0f}s, levels {lv}; {mix.get('changes')}")
            versions = call(h, "GET", f"{p}/beat/versions")
            longest = max((v for v in versions if isinstance(v, dict)), key=lambda v: v.get("created_at") or "", default={})
            if longest.get("render_url"):
                bs = seconds_of(longest["render_url"])
                check("3.1 the music itself is as long as the singing", bs >= 238, f"music {bs:.0f}s")
        lis = job(h, call(h, "POST", f"{p}/listen", json={"concern": "does it feel like worship?"}), "listen", 1200)
        check("1.5 Frank listens to a 4-minute song", "__error__" not in lis, str((lis.get("findings") or {}).get("findings"))[:200])
        atm = job(h, call(h, "POST", f"{p}/mix/atmosphere", json={"source": "recorded", "words": ["rain"]}), "atmosphere (recorded)", 1200)
        check("1.5 a real sound is added under a 4-minute song", "__error__" not in atm, str(atm)[:160])
        atg = job(h, call(h, "POST", f"{p}/mix/atmosphere", json={"source": "generated", "words": ["warm", "wonder"]}), "atmosphere (made)", 1200)
        check("1.5 a made sound is added (or says plainly why not)", "__error__" not in atg or "helper" in str(atg) or "quota" not in str(atg).lower(), str(atg)[:160])
        mixes = call(h, "GET", f"{p}/mix/versions")
        last = mixes[0] if isinstance(mixes, list) and mixes else {}
        if last.get("id"):
            exp = job(h, call(h, "POST", f"{p}/export", json={"mix_version_id": last["id"], "apply_mastering": True}), "finish", 1200)
            fin = exp.get("finish") or {}
            check("1.5 the finished song is made", "__error__" not in exp, json.dumps(fin)[:200])
            check("finish reaches streaming loudness", bool(fin.get("on_target")), json.dumps(fin)[:200])
    finally:
        print("\nPROJECT", pid)
        print(f"SUMMARY ({time.time() - started:.0f}s)")
        for n, ok, note in CHECKS:
            print(f"  {'PASS' if ok else 'FAIL'}  {n}")
        if uid:
            c.delete(f"{SB}/auth/v1/admin/users/{uid}", headers=ADMIN)
    sys.exit(0 if CHECKS and all(ok for _, ok, _ in CHECKS) else 1)


if __name__ == "__main__":
    main()
