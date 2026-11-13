"""
Baseline audit of Frank's procedural engine.

Renders beats from very different fingerprints WITHOUT touching Supabase or the
LLM, writes MP3s you can listen to, and prints measurements that test specific
claims about the engine (variation, dead fingerprint fields, melody vs chords,
section dynamics).

Run from backend/:
    venv/bin/python scripts/baseline_audit.py [output_dir]
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.generation import beat as beat_svc  # noqa: E402
from app.services.generation import composer, renderer, theory  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402

SR = renderer.SAMPLE_RATE

FINGERPRINTS: dict[str, dict] = {
    "01_sad_slow_soul": {
        "tempo_bpm": 68, "key": "A minor", "tempo_feel": "floating",
        "energy_level": 0.25, "density": 0.3, "brightness": 0.2, "warmth": 0.9,
        "genre_proximity": ["soul", "r&b"], "instrumentation_hints": ["piano", "soft drums"],
    },
    "02_hopeful_pop": {
        "tempo_bpm": 118, "key": "G major", "tempo_feel": "building",
        "energy_level": 0.7, "density": 0.6, "brightness": 0.8, "warmth": 0.5,
        "genre_proximity": ["pop"], "instrumentation_hints": ["guitar", "drums"],
    },
    "03_angry_driving": {
        "tempo_bpm": 142, "key": "E minor", "tempo_feel": "driving",
        "energy_level": 0.9, "density": 0.8, "brightness": 0.5, "warmth": 0.2,
        "genre_proximity": ["rock", "trap"], "instrumentation_hints": ["heavy drums", "bass"],
    },
    "04_dreamy_floating": {
        "tempo_bpm": 84, "key": "D major", "tempo_feel": "floating",
        "energy_level": 0.35, "density": 0.2, "brightness": 0.7, "warmth": 0.6,
        "genre_proximity": ["ambient", "lo-fi"], "instrumentation_hints": ["pads"],
    },
    # Same as 01 but ONLY the fields the engine is claimed to ignore differ.
    "05_same_as_01_other_dead_fields": {
        "tempo_bpm": 68, "key": "A minor", "tempo_feel": "floating",
        "energy_level": 0.25, "density": 0.3, "brightness": 0.95, "warmth": 0.05,
        "genre_proximity": ["metal", "country"], "instrumentation_hints": ["strings", "brass"],
    },
}


def to_float(int16_stereo: np.ndarray) -> np.ndarray:
    return int16_stereo.astype(np.float32) / 32768.0


def rms_db(x: np.ndarray) -> float:
    r = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return 20 * np.log10(r) if r > 1e-9 else -120.0


def digest(x: np.ndarray) -> str:
    return hashlib.sha1(x.tobytes()).hexdigest()[:10]


def melody_chord_clash(fp: dict) -> tuple[int, int]:
    """Count melody notes that are not chord tones of the bar they sit in."""
    f = fp_utils.normalize(fp)
    prog = theory.build_progression(f["key"], f["energy_level"], f["tempo_feel"], 0)
    part = composer.compose_melody(prog, 8, f["energy_level"], f["density"])
    chords = prog["chords"]
    total = clash = 0
    for ev in part.events:
        bar = int(ev.start // 4)
        chord_pcs = {n % 12 for n in chords[bar % len(chords)]}
        total += 1
        if ev.note % 12 not in chord_pcs:
            clash += 1
    return clash, total


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/frank_baseline")
    out_dir.mkdir(parents=True, exist_ok=True)
    full_digests: dict[str, str] = {}

    for name, fp in FINGERPRINTS.items():
        sections, mixes, full = beat_svc.render_full_beat(fp)
        full_digests[name] = digest(full)
        mp3 = renderer.to_mp3_bytes(full)
        (out_dir / f"{name}.mp3").write_bytes(mp3)

        print(f"\n=== {name} ===  ({full.shape[0] / SR:.1f}s, {len(mp3) / 1e6:.1f} MB)")
        print(f"{'#':<2} {'section':<8} {'bars':>4} {'layers':<34} {'rms_dB':>7} {'hash':>11}")
        for s, m in zip(sections, mixes):
            print(
                f"{s.index:<2} {s.name:<8} {s.bars:>4} {','.join(s.layers):<34} "
                f"{rms_db(to_float(m)):>7.1f} {digest(m):>11}"
            )
        clash, total = melody_chord_clash(fp)
        print(f"melody notes that are NOT chord tones: {clash}/{total}")

    print("\n=== Claim checks ===")
    a, b = full_digests["01_sad_slow_soul"], full_digests["05_same_as_01_other_dead_fields"]
    print(
        "brightness/warmth/genre/instrument hints change the audio? "
        f"{'NO (identical file)' if a == b else 'yes'}"
    )
    print("Output written to", out_dir)


if __name__ == "__main__":
    main()
