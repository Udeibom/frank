"""
Hum analysis for the Feel Lab.

When the user hums a melody or vibe, we extract rough musical properties —
tempo, key, and pitch range/movement — and turn them into fingerprint hints plus
a plain-language description the LLM can speak back. We never show numbers to
the user; this just seeds the direction.

Key change (Nov 2026): the key is now extracted from the notes the person
actually sang, using the same Krumhansl-Kessler key-finding used by the full
melody pipeline. Previously it was left to the LLM to guess from conversational
words like "melancholy". That meant the beat was built in a key unrelated to
the user's voice. Now the hum's key goes directly into fingerprint_hints and is
treated as authoritative downstream — the conversation still shapes mood, energy,
and style, but the key comes from audio.
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
        "key": str | None,       # e.g. "A minor", None when too uncertain
        "key_confidence": float, # 0..1
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
        f0, voiced_flag, voiced_prob = librosa.pyin(
            y,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C6")),
            sr=sr,
            hop_length=128,
        )
    except Exception:
        f0, voiced_flag, voiced_prob = np.array([]), np.array([]), np.array([])

    valid_mask = voiced_flag & ~np.isnan(f0)
    voiced_hz = f0[valid_mask] if f0.size > 0 else np.array([])

    if voiced_hz.size >= 2:
        # Register from median pitch
        median_hz = float(np.median(voiced_hz))
        median_midi = librosa.hz_to_midi(median_hz)
        register = "low" if median_midi < 52 else ("high" if median_midi > 67 else "mid")

        # Movement: compare first third vs last third
        third = max(1, len(voiced_hz) // 3)
        start_mean = float(np.mean(voiced_hz[:third]))
        end_mean = float(np.mean(voiced_hz[-third:]))
        spread = float(np.std(voiced_hz))
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

    # Key from the notes actually sung — this is the critical change.
    # We convert the voiced f0 frames into RawNote objects (one per contiguous
    # voiced run) and feed them through the same Krumhansl-Kessler estimator
    # used by the full melody pipeline. This gives a real key from real audio,
    # not a guess from the words "this feels dark".
    key_str, key_confidence = _estimate_key_from_f0(f0, voiced_flag, sr)

    # Fingerprint hints: tempo and energy are always included; key is included
    # when the confidence is high enough to be useful (≥0.4). Below that the
    # hum was too short or ambiguous — the LLM conversation still picks a key,
    # but at least it isn't fighting actual audio evidence.
    hints: dict = {
        "tempo_bpm": tempo_bpm,
        "energy_level": round(energy, 2),
    }
    if key_str and key_confidence >= 0.4:
        hints["key"] = key_str
        hints["key_confidence"] = round(key_confidence, 2)
        # mode is the second word of the key string ("C minor" -> "minor")
        parts = key_str.split()
        if len(parts) >= 2:
            hints["mode"] = parts[1]

    return {
        "tempo_bpm": tempo_bpm,
        "energy_level": round(energy, 2),
        "pitch_movement": pitch_movement,
        "register": register,
        "key": key_str,
        "key_confidence": round(key_confidence, 2),
        "fingerprint_hints": hints,
    }


# ── key estimation from raw pyin output ──────────────────────────────────

_HOP_S = 128 / 22050   # matches the hop_length used in analyze_hum


def _estimate_key_from_f0(
    f0: np.ndarray, voiced_flag: np.ndarray, sr: int
) -> tuple[str | None, float]:
    """
    Convert voiced pyin frames into RawNote objects and run the melody
    pipeline's Krumhansl-Kessler key estimator on them.

    Returns (key_string, confidence), e.g. ("A minor", 0.73).
    Returns (None, 0.0) if there is not enough voiced audio.
    """
    from app.services.intake.melody import RawNote, estimate_key, segment_notes

    if f0.size == 0:
        return None, 0.0

    valid_mask = voiced_flag & ~np.isnan(f0)
    if valid_mask.sum() < 20:   # fewer than ~0.1 s of voiced frames: too short
        return None, 0.0

    # Build a MIDI array with NaN where unvoiced, then use melody.segment_notes
    # to turn it into RawNote objects with the same logic used for full hums.
    times = np.arange(len(f0)) * _HOP_S
    midi = np.full(len(f0), np.nan)
    midi[valid_mask] = librosa.hz_to_midi(f0[valid_mask])

    try:
        notes = segment_notes(midi, times)
    except Exception:
        return None, 0.0

    if len(notes) < 3:
        return None, 0.0

    try:
        key_name, mode, confidence = estimate_key(notes)
    except Exception:
        return None, 0.0

    return f"{key_name} {mode}", float(confidence)


def _empty_result() -> dict:
    return {
        "tempo_bpm": 90,
        "energy_level": 0.5,
        "pitch_movement": "steady",
        "register": "mid",
        "key": None,
        "key_confidence": 0.0,
        "fingerprint_hints": {"tempo_bpm": 90, "energy_level": 0.5},
    }
