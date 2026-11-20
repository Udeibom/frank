"""
Render Frank's fixed reference song to files, so tools outside the backend (the frank-listener MCP, a Kiro CLI
listening regression, a Kiro Crew nightly job) can listen to exactly what the engine makes today.

  venv/bin/python scripts/render_reference.py [OUT_DIR]       # default ~/frank-listening/reference/<git sha>/

Writes song.wav and plan.json (the beat version params the Listener reads for section-by-section numbers) and
prints the folder. Audio never goes in the repository.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.generation import beat as beat_engine  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402
from app.services.generation.renderer import to_wav_bytes  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "reference_song.json"


def main() -> int:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "work"
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.home() / "frank-listening" / "reference" / sha
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(FIXTURE.read_text())
    fp = fp_utils.normalize(spec["fingerprint"])
    sections, fp = beat_engine.build_beat_plan(fp)
    _, full = beat_engine.render_song(sections, fp, spec["seed"])
    (out / "song.wav").write_bytes(to_wav_bytes(full))
    plan = {"sections": [s.__dict__ if hasattr(s, "__dict__") else s for s in sections], "fingerprint": fp, "seed": spec["seed"]}
    (out / "plan.json").write_text(json.dumps(plan, default=str, indent=1))
    (out / "meta.json").write_text(json.dumps({"bpm": fp["tempo_bpm"], "key": fp.get("key"), "commit": sha}))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
