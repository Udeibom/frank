"""
Spotify's Basic Pitch as a hum tracker (frankenstein spec 14, requirement 2.6), run on the ONNX runtime, so no
TensorFlow. It hears slides and vibrato as one note more often than a frame-by-frame tracker does, and it hears
chords, which lets Frank read the notes of a reference song's parts too.

Returns the same RawNote list as melody.segment_notes, so everything after (tuning, clean-up, key, tempo) is shared.
"""
from __future__ import annotations

import logging
import os
import tempfile
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf

log = logging.getLogger("frank.basic_pitch")

MIN_NOTE_S = 0.08


@lru_cache(maxsize=1)
def _model():
    logging.getLogger("root").setLevel(logging.ERROR)        # it warns about every runtime it does not find
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model
    p = Path(str(ICASSP_2022_MODEL_PATH))
    return Model(p if p.suffix == ".onnx" else p.parent / "nmp.onnx")


def events(y: np.ndarray, sr: int, onset_threshold: float = 0.5, frame_threshold: float = 0.3,
           min_hz: float | None = 70.0, max_hz: float | None = 1100.0, melodia: bool = True) -> list[tuple[float, float, int, float, list]]:
    """(start s, end s, midi, amplitude, pitch bends) for each note heard."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from basic_pitch.inference import predict
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="frank-bp-")
    os.close(fd)
    try:
        sf.write(path, y.astype(np.float32), sr)
        _, _, ev = predict(path, _model(), onset_threshold=onset_threshold, frame_threshold=frame_threshold,
                           minimum_note_length=MIN_NOTE_S * 1000, minimum_frequency=min_hz, maximum_frequency=max_hz,
                           melodia_trick=melodia)
    finally:
        os.remove(path)
    return [(float(s), float(e), int(p), float(a), list(b or [])) for s, e, p, a, b in ev]


def monophonic(evs: list[tuple[float, float, int, float, list]]) -> list[tuple[float, float, int, float, list]]:
    """A hum is one line: where notes overlap keep the louder one, trimming the other so none overlap."""
    out: list[list] = []
    for s, e, p, a, b in sorted(evs, key=lambda x: (x[0], -x[3])):
        if out and s < out[-1][1]:
            prev = out[-1]
            if a > prev[3] and s - prev[0] < MIN_NOTE_S:
                out[-1] = [s, e, p, a, b]
                continue
            if a > prev[3]:
                prev[1] = s
            else:
                s = prev[1]
                if e - s < MIN_NOTE_S:
                    continue
        out.append([s, e, p, a, b])
    return [tuple(x) for x in out if x[1] - x[0] >= MIN_NOTE_S]  # type: ignore[misc]


def raw_notes(y: np.ndarray, sr: int):
    """Basic Pitch notes as melody.RawNote, with the sung pitch (bends averaged, 1/3 semitone per bend step)."""
    from app.services.intake.melody import RawNote

    out = []
    for s, e, p, a, bends in monophonic(events(y, sr)):
        bend = float(np.mean(bends)) / 3.0 if bends else 0.0
        out.append(RawNote(start_s=s, end_s=e, midi=int(p), midi_f=float(p) + bend))
    return out
