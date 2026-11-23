"""
Synthetic audio for the core-path live run (spec 15): a slow hum like the founder's, and a long sung take.
Shared by e2e_core.py and its local check. Plain numpy; no audio is stored in the repo.
"""
from __future__ import annotations

import io

import numpy as np
import soundfile as sf

SR = 44100


def _voice(midi: float, seconds: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    f = 440 * 2 ** ((midi - 69) / 12) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t))      # a little vibrato
    phase = 2 * np.pi * np.cumsum(f) / sr
    y = 0.5 * np.sin(phase) + 0.2 * np.sin(2 * phase) + 0.08 * np.sin(3 * phase)
    env = np.minimum(1, np.minimum(t / 0.04, (seconds - t) / 0.06).clip(0))
    return (y * env * 0.5).astype(np.float32)


def slow_hum(bpm: float = 69.0) -> bytes:
    """A worship-like tune at `bpm`, sung in eighth notes, so its notes start twice per beat (the founder's case)."""
    eighth = 60.0 / bpm / 2
    tune = [59, 59, 62, 64, 66, 64, 62, 62, 59, 57, 59, 62, 64, 64, 62, 59]
    parts = []
    for i, n in enumerate(tune):
        dur = eighth * (2 if i % 4 == 3 else 1)
        parts += [_voice(n, dur * 0.92), np.zeros(int(dur * 0.08 * SR), np.float32)]
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(parts), SR, format="WAV")
    return buf.getvalue()


def long_take(seconds: float = 240.0, bpm: float = 69.0) -> bytes:
    """A sung take of `seconds` (the founder sang about four minutes), 16-bit mono WAV."""
    beat = 60.0 / bpm
    line = [59, 62, 64, 66, 64, 62, 59, 57]
    out, total, i = [], 0.0, 0
    while total < seconds:
        n = line[i % len(line)]
        out += [_voice(n, beat * 0.9), np.zeros(int(beat * 0.1 * SR), np.float32)]
        total += beat
        i += 1
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(out)[: int(seconds * SR)], SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()
