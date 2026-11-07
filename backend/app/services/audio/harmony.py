"""
Harmony generation — create a harmony vocal from the user's own take.

No second recording needed. We pitch-shift the vocal by a musical interval that
fits the song's key: a third or a fifth, above or below. The shifted copy sits
under the lead as a harmony layer the Mix Room can turn on/off.

All CPU via Rubber Band (pylibrb).
"""

from __future__ import annotations
import io
import numpy as np
import librosa
import soundfile as sf
import pylibrb

SR = 44100

def _intervals_for_mode(mode: str | None) -> dict[str, int]:
    """
    Choose harmony intervals that fit the song's mode. A third above is +4
    semitones in major but +3 in minor — using the wrong one clashes with the
    key. The fourth below (-5) is consonant in both.
    """
    if mode == "minor":
        return {"above": 3, "below": -5}   # minor third up, fourth down
    return {"above": 4, "below": -5}       # major third up, fourth down


def _shift(mono: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    scale = 2.0 ** (semitones / 12.0)
    st = pylibrb.RubberBandStretcher(
        sample_rate=sr, channels=1, initial_pitch_scale=scale
    )
    buf = mono.reshape(1, -1).astype(np.float32)
    st.study(buf, final=True)
    st.process(buf, final=True)
    out = st.retrieve_available()
    return out[0] if out.ndim == 2 else out


def generate_harmony(
    wav_bytes: bytes, harmony_type: str = "above", mode: str | None = None
) -> bytes:
    """
    Generate a harmony part from a vocal take. harmony_type is "above", "below",
    or "both". `mode` ("major"/"minor") picks intervals that fit the song's key.
    Returns WAV bytes of the harmony layer (lead not included).
    """
    y, sr = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    if y.size == 0:
        return wav_bytes
    y = y.astype(np.float32)

    intervals = _intervals_for_mode(mode)

    if harmony_type == "both":
        up = _shift(y, sr, intervals["above"])
        down = _shift(y, sr, intervals["below"])
        n = max(up.shape[0], down.shape[0])
        harmony = np.zeros(n, dtype=np.float32)
        harmony[: up.shape[0]] += up * 0.7
        harmony[: down.shape[0]] += down * 0.7
    else:
        semitones = intervals.get(harmony_type, intervals["above"])
        harmony = _shift(y, sr, semitones)

    # Harmony sits a touch under the lead
    peak = float(np.abs(harmony).max())
    if peak > 0:
        harmony *= 0.75 / peak

    buf = io.BytesIO()
    sf.write(buf, harmony, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()
