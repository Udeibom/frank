"""
The Listener on audio files (kiro-craft spec 12, requirement 3; Listener requirement 4.2). Same functions as the
product: `service.measure_audio`, `findings.find_issues`, `service.compare`. Prints JSON.

  venv/bin/python scripts/listen_file.py measure song.mp3 [--as mix|beat|vocal] [--bpm 90] [--key "A minor"] [--plan params.json]
  venv/bin/python scripts/listen_file.py issues  song.mp3 [--concern "the chorus doesn't lift"] [...]
  venv/bin/python scripts/listen_file.py compare before.mp3 after.mp3 [...]

Without a plan (a saved beat version's params), the whole file is measured as one stretch of music: loudness,
peaks, noise and colour work; section-by-section findings need the plan.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.generation import beat as beat_engine  # noqa: E402
from app.services.listener import findings, service  # noqa: E402
from app.services.listener.service import LISTEN_SR  # noqa: E402


def _sections(audio_seconds: float, bpm: float, plan: str | None) -> tuple[list, dict]:
    if plan:
        params = json.loads(pathlib.Path(plan).read_text())
        sections, fp = beat_engine.sections_from_params(params)
        return sections, fp
    bars = max(1, int(round(audio_seconds / (4 * 60.0 / bpm))))
    return [beat_engine.SectionPlan(index=0, name="verse", label="Whole file", bars=bars, energy=0.5, density=0.5, layers=[])], {}


def measure(path: str, kind: str, bpm: float, key: str | None, plan: str | None):
    audio = service.decode(pathlib.Path(path).read_bytes(), LISTEN_SR)
    sections, fp = _sections(audio.size / LISTEN_SR, bpm, plan)
    bpm = float(fp.get("tempo_bpm", bpm)) if fp else bpm
    return service.measure_audio(sections, bpm, sr=LISTEN_SR, key=key or fp.get("key"), **{kind: audio})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["measure", "issues", "compare"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--as", dest="kind", default="mix", choices=["mix", "beat", "vocal"])
    ap.add_argument("--bpm", type=float, default=90.0)
    ap.add_argument("--key", default=None)
    ap.add_argument("--plan", default=None)
    ap.add_argument("--concern", default=None)
    a = ap.parse_args()
    if a.command == "compare":
        if len(a.files) != 2:
            ap.error("compare needs two files")
        before, after = (measure(f, a.kind, a.bpm, a.key, a.plan) for f in a.files)
        out = {"differences": [d.model_dump() for d in service.compare(before, after)]}
    else:
        report = measure(a.files[0], a.kind, a.bpm, a.key, a.plan)
        out = report.model_dump() if a.command == "measure" else findings.find_issues(report, a.concern).model_dump()
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
