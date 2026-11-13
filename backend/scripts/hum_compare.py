"""
Make a "hear the difference" file for a hum: for each short phrase, your original, then Frank's
piano version of it. A few beeps before each phrase give it a number, so you can say
"phrase 3 is off" without naming any notes.

Run from backend/:
    venv/bin/python scripts/hum_compare.py "/path/to/hum.flac" /output/dir
"""
from __future__ import annotations

import sys
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.song import MelodyNote, MelodySketch  # noqa: E402
from app.services.generation import renderer  # noqa: E402
from app.services.intake import melody as m, preview  # noqa: E402

OUT_SR = renderer.SAMPLE_RATE
NOTES_PER_PHRASE = 6


def silence(seconds: float) -> np.ndarray:
    return np.zeros((int(seconds * OUT_SR), 2), dtype=np.int16)


def beeps(count: int) -> np.ndarray:
    parts = []
    t = np.arange(int(0.12 * OUT_SR)) / OUT_SR
    tone = (0.35 * np.sin(2 * np.pi * 1000 * t) * np.hanning(t.size) * 32767).astype(np.int16)
    for _ in range(count):
        parts.append(np.column_stack([tone, tone]))
        parts.append(silence(0.12))
    return np.concatenate(parts)


def phrase_chunk(sketch, first: int, last: int) -> np.ndarray:
    """Frank's version of one stretch of the tune, played the same way the app plays it back."""
    notes = (sketch.performed_notes or sketch.notes)[first:last]
    base = notes[0].start_beat
    part = MelodySketch(
        notes=[],
        performed_notes=[MelodyNote(pitch_midi=n.pitch_midi, start_beat=n.start_beat - base, dur_beats=n.dur_beats) for n in notes],
        tempo_bpm=sketch.tempo_bpm, tempo_confidence=sketch.tempo_confidence, key=sketch.key, mode=sketch.mode,
        key_confidence=sketch.key_confidence, grid=sketch.grid,
    )
    return preview.render_preview_audio(part)


def main(path: str, out_dir: str) -> None:
    src = Path(path)
    result = m.extract_melody(src.read_bytes(), src.suffix.lstrip("."))
    if not result.ok:
        print("Could not read a tune:", result.reason)
        return
    y = m.decode_mono(src.read_bytes(), src.suffix.lstrip("."))
    y44 = librosa.resample(y, orig_sr=m.SR, target_sr=OUT_SR)
    sketch, raw = result.sketch, result.raw_notes

    pieces: list[np.ndarray] = [silence(0.5)]
    n_phrases = 0
    for first in range(0, len(raw), NOTES_PER_PHRASE):
        last = min(first + NOTES_PER_PHRASE, len(raw))
        if last - first < 2:
            continue
        n_phrases += 1
        t0 = max(raw[first].start_s - 0.15, 0.0)
        t1 = raw[last - 1].end_s + 0.25
        original = (np.clip(y44[int(t0 * OUT_SR): int(t1 * OUT_SR)], -1, 1) * 32767 * 0.9).astype(np.int16)
        pieces += [
            beeps(n_phrases), silence(0.4),
            np.column_stack([original, original]), silence(0.6),
            phrase_chunk(sketch, first, last), silence(1.5),
        ]
    audio = np.concatenate(pieces)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = src.stem.replace(" ", "_") + "__compare.mp3"
    (out / name).write_bytes(renderer.to_mp3_bytes(audio))
    print(f"{name}: {n_phrases} phrases")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
