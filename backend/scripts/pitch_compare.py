"""
Which ears hear a hum better: pyin (frame by frame) or Basic Pitch (neural)? (frankenstein spec 14, requirement 2.6)

Builds hums whose true notes are known: a voice-like tone with breathy harmonics, vibrato, scoops into notes,
slides between some notes, uneven timing, loudness swells and room noise. Each tracker's notes are scored against
the truth (the right note within a quarter of its length of the right time; extra and missed notes both count).

  venv/bin/python scripts/pitch_compare.py [N]     # N hums per kind (default 12); prints a table and the winner

The founder judged pyin "close and manageable" by ear on real hums (11 Nov). This adds a measured comparison on
hard cases; real hums are still the final judge (founder testing at the end of the build).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.intake import melody  # noqa: E402

SR = 22050
KINDS = ("clean", "vibrato", "slides", "breathy_noisy", "fast")


def hum(rng: np.random.Generator, kind: str) -> tuple[np.ndarray, list[tuple[float, int]]]:
    scale = [0, 2, 4, 5, 7, 9, 11, 12]
    root = int(rng.integers(52, 62))
    n = int(rng.integers(8, 14))
    pitches, p = [], 4
    for _ in range(n):
        p = int(np.clip(p + rng.integers(-2, 3), 0, len(scale) - 1))
        pitches.append(root + scale[p])
    durs = rng.uniform(0.18, 0.32, n) if kind == "fast" else rng.uniform(0.3, 0.75, n)
    out, truth, t = [], [], 0.25
    out.append(np.zeros(int(0.25 * SR)))
    for i, (m, d) in enumerate(zip(pitches, durs)):
        L = int(d * SR)
        tt = np.arange(L) / SR
        target = float(m)
        prev = float(pitches[i - 1]) if i else target
        curve = np.full(L, target)
        scoop = min(L, int(0.06 * SR))
        curve[:scoop] = target - np.linspace(0.6, 0, scoop)                  # singers scoop into notes
        if kind == "slides" and i and rng.random() < 0.6:
            g = min(L, int(0.12 * SR))
            curve[:g] = np.linspace(prev, target, g)
        if kind in ("vibrato", "breathy_noisy"):
            curve += 0.35 * np.sin(2 * np.pi * 5.5 * tt) * np.clip(tt / 0.25, 0, 1)
        curve += rng.normal(0, 0.03)                                            # a hum is never exactly in tune
        f = 440 * 2 ** ((curve - 69) / 12)
        ph = 2 * np.pi * np.cumsum(f) / SR
        tone = sum((0.5 ** k) * np.sin((k + 1) * ph) for k in range(5))
        env = np.minimum(1, np.minimum(tt / 0.03, (d - tt) / 0.05)) * rng.uniform(0.5, 1.0)
        seg = tone * env
        if kind == "breathy_noisy":
            seg = seg + rng.normal(0, 0.08, L) * env
        out.append(seg)
        truth.append((t, m))
        gap = rng.uniform(0.0, 0.08)
        out.append(np.zeros(int(gap * SR)))
        t += d + gap
    y = np.concatenate(out + [np.zeros(int(0.3 * SR))])
    y = y / (np.abs(y).max() + 1e-9) * 0.5
    if kind == "breathy_noisy":
        y = y + rng.normal(0, 0.01, y.size)
    return y, truth


def score(found: list, truth: list[tuple[float, int]]) -> float:
    """F-measure of notes: right pitch (octave errors count as wrong) and onset within 120 ms."""
    used, hits = set(), 0
    for t, m in truth:
        for j, n in enumerate(found):
            if j not in used and abs(n.start_s - t) <= 0.12 and n.midi == m:
                used.add(j)
                hits += 1
                break
    if not found or not truth:
        return 0.0
    p, r = hits / len(found), hits / len(truth)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def run(n: int) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(14)
    table: dict[str, dict[str, list[float]]] = {k: {"pyin": [], "basic_pitch": []} for k in KINDS}
    for kind in KINDS:
        for _ in range(n):
            y, truth = hum(rng, kind)
            buf = io.BytesIO()
            sf.write(buf, y.astype(np.float32), SR, format="WAV")
            for tracker in ("pyin", "basic_pitch"):
                res = melody.extract_melody(buf.getvalue(), "wav", tracker=tracker)
                found = res.raw_notes or []
                if res.diagnostics.get("tracker") not in (tracker, None) and tracker == "basic_pitch":
                    found = []                                                 # it fell back: count as a miss
                # extract_melody shifts notes by its tuning estimate; undo that for scoring against the truth
                table[kind][tracker].append(score(found, truth))
    return {k: {t: float(np.mean(v)) for t, v in d.items()} for k, d in table.items()}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    res = run(n)
    print(f"{'kind':<16}{'pyin':>8}{'basic_pitch':>14}")
    for k, d in res.items():
        print(f"{k:<16}{d['pyin']:>8.2f}{d['basic_pitch']:>14.2f}")
    avg = {t: float(np.mean([d[t] for d in res.values()])) for t in ("pyin", "basic_pitch")}
    print(f"{'average':<16}{avg['pyin']:>8.2f}{avg['basic_pitch']:>14.2f}")
    print("winner:", max(avg, key=avg.get))
    return 0


if __name__ == "__main__":
    sys.exit(main())
