"""
Hum analysis for the Feel Lab.

When the user hums a melody or vibe, we extract rough musical properties —
tempo and pitch range/movement — and turn them into fingerprint hints plus a
plain-language description the LLM can speak back. We never show numbers to the
user; this just seeds the direction.
"""

from __future__ import annotations
import io
import numpy as np
import librosa


def analyze_hum(wav_bytes: bytes) -> dict:
    """
    Analyze a hum recording (WAV bytes) and return:
      {
        "tempo_bpm": int,
        "energy_level": float,   # 0..1, from loudness/movement
        "pitch_movement": "rising" | "falling" | "steady" | "wandering",
        "register": "low" | "mid" | "high",
        "fingerprint_hints": { ... partial fingerprint ... }
      }
    CPU-bound — call from a background job.
    """
    y, sr = librosa.load(io.BytesIO(wav_bytes), sr=22050, mono=True)

    if y.size == 0:
        return _empty_result()

    # Tempo (may be unreliable for a short hum, so clamp to a musical range)
    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_bpm = int(round(float(np.atleast_1d(tempo)[0])))
    except Exception:
        tempo_bpm = 90
    tempo_bpm = max(60, min(140, tempo_bpm))

    # Pitch tracking via pyin (fundamental frequency over time)
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C6")),
            sr=sr,
        )
        voiced = f0[~np.isnan(f0)]
    except Exception:
        voiced = np.array([])

    if voiced.size >= 2:
        # Register from median pitch
        median_hz = float(np.median(voiced))
        midi = librosa.hz_to_midi(median_hz)
        register = "low" if midi < 52 else ("high" if midi > 67 else "mid")

        # Movement: compare first third vs last third
        third = max(1, len(voiced) // 3)
        start_mean = float(np.mean(voiced[:third]))
        end_mean = float(np.mean(voiced[-third:]))
        spread = float(np.std(voiced))
        if spread > 40 and abs(end_mean - start_mean) < 20:
            pitch_movement = "wandering"
        elif end_mean > start_mean * 1.05:
            pitch_movement = "rising"
        elif end_mean < start_mean * 0.95:
            pitch_movement = "falling"
        else:
            pitch_movement = "steady"
    else:
        register = "mid"
        pitch_movement = "steady"

    # Energy from RMS loudness and tempo
    rms = float(np.mean(librosa.feature.rms(y=y)))
    energy = max(0.0, min(1.0, rms * 8.0))  # scale RMS into 0..1 roughly
    if tempo_bpm > 110:
        energy = min(1.0, energy + 0.15)

    # Only seed tempo and energy from the hum — these are things we can actually
    # measure from audio. We deliberately do NOT infer major/minor from vocal
    # register (a low hum isn't inherently "minor"); the mood/mode comes from the
    # conversation, where the LLM reads the user's emotional language.
    hints = {
        "tempo_bpm": tempo_bpm,
        "energy_level": round(energy, 2),
    }

    return {
        "tempo_bpm": tempo_bpm,
        "energy_level": round(energy, 2),
        "pitch_movement": pitch_movement,
        "register": register,
        "fingerprint_hints": hints,
    }


def _empty_result() -> dict:
    return {
        "tempo_bpm": 90,
        "energy_level": 0.5,
        "pitch_movement": "steady",
        "register": "mid",
        "fingerprint_hints": {"tempo_bpm": 90, "energy_level": 0.5},
    }
