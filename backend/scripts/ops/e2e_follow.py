"""
Live check: the music plays to the singer (core-path spec 15, requirement 8). A song sung without music (verse,
chorus, verse, chorus at 69, first bar line at 3.1 s) is recorded on the deployed site; Frank should build the music
around it by itself, at the singer's speed, with sections where they were sung, as long as the singing.
  python scripts/ops/run_on_kaggle.py e2e_follow.py
"""
from __future__ import annotations

import sys
import time

from core_audio import sung_song
from e2e import ADMIN, SB, c, login
from e2e_core import CHECKS, LYRICS, call, check, job, seconds_of


def main() -> None:
    uid, h = login()
    pid = None
    try:
        pid = call(h, "POST", "/projects", json={"title": "Follow run"})["id"]
        p = f"/projects/{pid}"
        call(h, "POST", f"{p}/lyrics", json={"content": LYRICS, "label": "v1"})
        call(h, "POST", f"{p}/feel/fingerprint", json={"fingerprint": {"energy_level": 0.45, "density": 0.45, "tempo_bpm": 96},
                                                         "conversation_summary": "worship, full of wonder"})
        job(h, call(h, "POST", f"{p}/beat/generate", json={"fingerprint": {"energy_level": 0.45, "density": 0.45, "tempo_bpm": 96}}), "first music")
        wav, truth = sung_song()
        up = call(h, "POST", f"{p}/voice/takes", files={"file": ("song.wav", wav, "audio/wav")})
        analysis = job(h, {"job_id": up.get("analysis_job_id")}, "check the recording")
        music_job = analysis.get("music_job_id")
        check("8.1 music is built around the recording without being asked", bool(music_job), str(analysis)[:160])
        built = job(h, {"job_id": music_job}, "music around the singing", 1200) if music_job else {}
        versions = call(h, "GET", f"{p}/beat/versions")
        v = next((x for x in versions if x.get("id") == built.get("beat_version_id")), {}) if isinstance(versions, list) else {}
        params = v.get("params") or {}
        fp = params.get("fingerprint") or {}
        check("8.1 it is a new version, the earlier music kept", len(versions) >= 2 and bool(v), f"{len(versions)} versions")
        bpm = float(fp.get("tempo_bpm") or 0)
        check("8.2 the music moves at the singer's speed", abs(bpm - 69) < 0.7 or abs(bpm - 138) < 1.4, f"speed {bpm}")
        start = float(params.get("start_s") or 0)
        bar = 240.0 / (bpm or 1)
        off = ((start - 3.1) / bar) % 1.0
        check("8.2 its bar lines fall where the singer's do", min(off, 1 - off) * 4 < 0.3, f"first bar line {start:.2f}s")
        t, built_at = start, []
        for s in params.get("sections") or []:
            built_at.append((s["name"], round(t, 2)))
            t += s["bars"] * bar
        changes_sung = [x for (n, x), (m, _) in zip(truth[1:], truth[:-1]) if n != m]
        changes_built = [x for (n, x), (m, _) in zip(built_at[1:], built_at[:-1]) if n != m and n != "outro" and m != "intro"]
        near = all(any(abs(a - b) < 60.0 / (bpm or 1) * 1.01 for a in changes_built) for b in changes_sung)
        check("8.3 the music changes where the singing changes", near, f"sung {truth} | built {built_at}")
        check("8.5 no competing tune in the music", all("melody" not in (s.get("layers") or []) for s in params.get("sections") or []))
        mix = job(h, call(h, "POST", f"{p}/mix/render", json={"mix_params": {}, "quality": "preview"}), "blend", 900)
        if mix.get("render_url"):
            secs = seconds_of(mix["render_url"])
            check("8.5 the blend carries on to the end of the singing", secs >= truth[-1][1] + 27, f"blend {secs:.0f}s")
            after = call(h, "GET", f"{p}/beat/versions")
            check("3.2 music built from the singing is not lengthened again", isinstance(after, list) and len(after) == len(versions),
                  f"{len(versions)} versions before the blend, {len(after) if isinstance(after, list) else after} after; blend {secs:.0f}s")
        ops = job(h, call(h, "POST", f"{p}/beat/operations", json={"operations": [{"op": "slower"}]}), "slower on following music")
        check("8.6 a speed change is refused plainly", "__error__" in ops and "your speed" in str(ops.get("__error__")), str(ops)[:200])
    finally:
        print("\nPROJECT", pid)
        print("SUMMARY")
        for n, ok, _ in CHECKS:
            print(f"  {'PASS' if ok else 'FAIL'}  {n}")
        if uid:
            c.delete(f"{SB}/auth/v1/admin/users/{uid}", headers=ADMIN)
    sys.exit(0 if CHECKS and all(ok for _, ok, _ in CHECKS) else 1)


if __name__ == "__main__":
    main()
