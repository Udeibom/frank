"""
Reference song check (kiro-craft spec 12, requirement 2.2). After a change to the song engine, render one fixed
song (fixed feeling and seed), let the Listener find issues, and compare with the stored baseline.
A NEW "likely problem" fails the check unless it is noted in the baseline file's "accepted" list.

  venv/bin/python scripts/listen_reference.py            # check (exit 1 on a new likely problem)
  venv/bin/python scripts/listen_reference.py --update   # store the current findings as the baseline

Writes a short report to backend/.reference_report.txt (git-ignored) so a background hook leaves something to read.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.generation import beat as beat_engine  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402
from app.services.listener import findings, service  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "reference_song.json"
BASELINE = ROOT / "tests" / "fixtures" / "reference_findings.json"
REPORT = ROOT / ".reference_report.txt"


def listen() -> list[dict]:
    spec = json.loads(FIXTURE.read_text())
    sections, fp = beat_engine.build_beat_plan(fp_utils.normalize(spec["fingerprint"]))
    _, full = beat_engine.render_song(sections, fp, spec["seed"])
    import numpy as np
    import librosa

    mono = full.astype(np.float32).mean(axis=1) / 32768.0
    mono = librosa.resample(mono, orig_sr=beat_engine.SAMPLE_RATE, target_sr=service.LISTEN_SR)
    score = service.score_facts(sections, fp, spec["seed"])
    report = service.measure_audio(sections, float(fp["tempo_bpm"]), beat=mono, sr=service.LISTEN_SR, key=fp.get("key"), score=score)
    return [{"id": f.id, "severity": f.severity, "sections": f.sections, "plain": f.plain}
            for f in findings.find_issues(report).findings]


def main() -> int:
    started = time.time()
    now = listen()
    if "--update" in sys.argv:
        old = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
        BASELINE.write_text(json.dumps({"findings": now, "accepted": old.get("accepted", [])}, indent=1) + "\n")
        print(f"baseline stored: {len(now)} finding(s)")
        return 0
    base = json.loads(BASELINE.read_text())
    known = {(f["id"], tuple(f["sections"])) for f in base["findings"]}
    accepted = set(base.get("accepted", []))
    new_problems = [f for f in now if f["severity"] == "likely_problem" and (f["id"], tuple(f["sections"])) not in known
                    and f["id"] not in accepted]
    gone = [f for f in base["findings"] if (f["id"], tuple(f["sections"])) not in {(n["id"], tuple(n["sections"])) for n in now}]
    lines = [f"Reference song: {len(now)} finding(s), {time.time() - started:.0f}s"]
    lines += [f"NEW likely problem: {f['plain']}" for f in new_problems]
    lines += [f"no longer found: {f['plain']}" for f in gone]
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if new_problems else 0


if __name__ == "__main__":
    sys.exit(main())
