"""
Does the music follow the singer? (core-path spec 15, requirement 8). Sings a made-up song with a known speed, bar
line and sections, lets Frank listen to the audio and build the music, renders it, and measures:
  - the speed and bar line Frank found, against the truth
  - where Frank's sections start, against where they were sung
  - how much of what was sung sits inside the chord playing under it
  - whether the music is bigger under the choruses than under the verses
  - whether the music lasts to the end of the singing
  venv/bin/python scripts/follow_check.py [OUT_DIR]     (writes song.wav and blend.wav there for listening)
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from accompany_songs import song  # noqa: E402
from app.services.audio import vocal_notes  # noqa: E402
from app.services.generation import accompany, beat as beat_engine  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402

SR = 44100


def sing(notes: list[accompany.Note], seconds: float) -> np.ndarray:
    y = np.zeros(int(seconds * SR), dtype=np.float32)
    for n in notes:
        t = np.arange(int((n.end - n.start) * SR)) / SR
        f = 440 * 2 ** ((n.pitch - 69) / 12) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        env = np.minimum(1, np.minimum(t / 0.04, (t[-1] - t) / 0.08).clip(0))
        seg = (0.5 * np.sin(ph) + 0.2 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * env * 0.4
        a = int(n.start * SR)
        y[a:a + seg.size] += seg[: max(0, y.size - a)]
    return y


def main(out_dir: str | None = None) -> int:
    truth_bpm, truth_start = 69.0, 3.1
    truth, starts = song(bpm=truth_bpm, start_s=truth_start, form="VCVC")
    voice = sing(truth, truth[-1].end + 3)
    heard = [accompany.Note(n.start, n.end, float(n.centre)) for n in vocal_notes.sung_notes(voice, SR)
             if n.length > 0.12 and n.centre == n.centre]
    grid = accompany.grid_from_notes(heard, "Worthy of every breath, a worship song")
    sung = accompany.sections_from_phrases(heard, grid)
    fp = fp_utils.normalize({"tempo_bpm": grid.bpm, "energy_level": 0.45, "density": 0.45})
    acc = accompany.plan(heard, grid, sung, fp)
    fp = {**fp, "key": acc.key, "mode": acc.key.split()[1], "music_start_s": grid.start_s, "follows_voice": True}
    _, music = beat_engine.render_song(acc.sections, fp, seed=7)
    music = music.astype(np.float32) / 32768.0

    print(f"speed: found {grid.bpm} (sung at {truth_bpm}); first bar line {grid.start_s:.2f}s (sung {truth_start}s)")
    t, found = grid.start_s, []
    for s in acc.sections:
        found.append((s.name, round(t, 2)))
        t += s.bars * grid.bar_s
    print("sections sung :", [(n, round(x, 2)) for n, x in starts])
    print("sections built:", found)
    # How much of the singing sits in the chord under it
    from app.services.audio import song_notes

    notes = song_notes.from_plan(acc.sections, fp, 7)
    inside = total = 0.0
    for n in heard:
        mid = (n.start + n.end) / 2
        chord = next((c.value for c in notes.chords if c.start <= mid < c.end), None)
        if chord is None:
            continue
        w = n.end - n.start
        total += w
        diatonic_step = any(((int(round(n.pitch)) + d) % 12) in chord for d in (-2, -1, 1, 2))
        inside += w if int(round(n.pitch)) % 12 in chord else (0.3 * w if diatonic_step else 0)
    print(f"singing inside the chords: {inside / total:.0%}")
    # Bigger under choruses?
    def level(a: float, b: float) -> float:
        seg = music[int((a - grid.start_s) * SR):int((b - grid.start_s) * SR)]
        return 20 * np.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-9)
    t = grid.start_s
    for s in acc.sections:
        print(f"  {s.name:7s} {level(t, t + s.bars * grid.bar_s):6.1f} dB  parts {s.layers}")
        t += s.bars * grid.bar_s
    end = grid.start_s + music.shape[0] / SR
    print(f"music ends {end:.1f}s, last sung note ends {heard[-1].end:.1f}s")
    if out_dir:
        out = pathlib.Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        pad = np.zeros((int(grid.start_s * SR), 2), dtype=np.float32)
        m = np.concatenate([pad, music])
        n = max(m.shape[0], voice.size)
        blend = np.zeros((n, 2), dtype=np.float32)
        blend[: m.shape[0]] += m * 0.5
        blend[: voice.size] += voice[:, None]
        sf.write(out / "blend.wav", blend / max(1.0, float(np.abs(blend).max())), SR)
        sf.write(out / "song.wav", voice, SR)
        print("wrote", out / "blend.wav")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
