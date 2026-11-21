"""
Live check of Frank's two Spaces (frankenstein spec 14): call every endpoint once and print what came back.

  venv/bin/python scripts/check_spaces.py [ears|hands|all] [CLIP.mp3] [VOICE.wav]

Uses the same client the backend uses (services/remote), so a pass here means the deployed app can reach them.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.remote import organs, spaces  # noqa: E402


def run(tests: list) -> int:
    bad = 0
    for name, fn in tests:
        t = time.time()
        try:
            r = fn()
            print(f"OK   {name:14} {time.time() - t:5.0f}s  {json.dumps(r, default=str)[:260]}", flush=True)
        except spaces.RemoteUnavailable as e:
            bad += 1
            print(f"FAIL {name:14} {time.time() - t:5.0f}s  {e.plain} | {str(e)[:500]}", flush=True)
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"ERR  {name:14} {repr(e)[:500]}", flush=True)
    return bad


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    clip = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/slice.mp3").read_bytes()
    voice = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/sung.wav").read_bytes()
    ears = [
        ("health", lambda: spaces.call("ears", "/health", timeout=240)),
        ("embed_text", lambda: len(organs.embed_text(["late night drive"])[0])),
        ("embed_audio", lambda: len(organs.embed_audio(clip))),
        ("labels", lambda: organs.labels(clip)),
        ("aesthetics", lambda: organs.aesthetics(clip)),
        ("chords", lambda: organs.chords(clip)[:4]),
        ("emotions", lambda: organs.emotions(["I walk alone till the morning comes"])),
        ("pitch", lambda: len(organs.pitch(voice, "wav")["hz"])),
        ("structure", lambda: organs.structure(clip).get("sections")),
        ("denoise", lambda: len(organs.denoise(voice))),
        ("separate", lambda: [len(x) for x in organs.separate(clip)]),
        ("match_master", lambda: len(organs.match_master(voice, clip, "wav", "mp3"))),
    ]
    notes = [{"note": n, "start": i * 1.0, "duration": 0.9, "velocity": 90} for i, n in enumerate([60, 62, 64, 65, 67, 65, 64, 62])]
    hands = [
        ("health", lambda: spaces.call("hands", "/health", timeout=240)),
        ("speak", lambda: len(organs.speak("The chorus feels bigger now. Have a listen."))),
        ("accompany", lambda: [(p["program"], len(p["notes"])) for p in organs.accompany(notes, 90, 8)]),
        ("ambience", lambda: len(organs.ambience("rain on a window at night", 10))),
        ("timbre", lambda: len(organs.timbre(voice, "violin"))),
        ("sing_layout", lambda: str(spaces.call("hands", "/sing_layout", timeout=900))[:300]),
        ("sing", lambda: len(spaces.read_file(spaces.call("hands", "/sing", json.dumps(
            {"notes": [{"note": n["note"], "start": n["start"], "duration": n["duration"]} for n in notes],
             "phonemes": [["l", "ah"]] * 8, "bpm": 90, "lead_s": 0.0}), timeout=900)))),
    ]
    tests = (ears if which in ("ears", "all") else []) + (hands if which in ("hands", "all") else [])
    return 1 if run(tests) else 0


if __name__ == "__main__":
    sys.exit(main())
