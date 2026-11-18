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


# ── a harmony that follows the chords (sing-it spec 06, requirement 6) ───

LEAD_IN_S = 0.03             # a little before each note, so the start of the word comes along
FADE_S = 0.012


def _scale_step(note: int, scale: frozenset[int], steps: int) -> int:
    """`steps` notes of the scale away from `note` (a third is two steps)."""
    n, moved = note, 0
    d = 1 if steps > 0 else -1
    while moved < abs(steps):
        n += d
        if n % 12 in scale:
            moved += 1
    return n


def harmony_note(sung_target: int, chord: frozenset[int] | None, scale: frozenset[int], direction: str) -> int:
    """The nearest chord note strictly above (or below) the sung note; a scale third when no chord is known."""
    d = 1 if direction == "above" else -1
    if chord:
        n = sung_target + d
        for _ in range(12):
            if n % 12 in chord:
                return n
            n += d
    return _scale_step(sung_target, scale, 2 * d)


def plan_harmony(notes: list, song, direction: str, sections: set[int] | None = None) -> list[dict]:
    """Per sung note: where its harmony goes. Notes outside the chosen sections get no harmony."""
    from app.services.audio.song_notes import target_note

    plan: list[dict] = []
    for n in notes:
        if not np.isfinite(n.centre):
            continue
        t = song.at((n.start + n.end) / 2)
        if sections is not None and t.section not in sections:
            continue
        sung = target_note(n.centre, t)
        h = harmony_note(sung, t.chord, song.scale, direction)
        plan.append({"start": n.start, "end": n.end, "sung": sung, "note": h, "shift": h - n.centre,
                     "chord": sorted(t.chord) if t.chord else None, "section": t.section})
    return plan


def render_harmony(mono: np.ndarray, sr: int, plan: list[dict]) -> np.ndarray:
    out = np.zeros_like(mono, dtype=np.float32)
    fade, lead = int(FADE_S * sr), int(LEAD_IN_S * sr)
    for p in plan:
        a, b = max(0, int(p["start"] * sr) - lead), min(mono.shape[0], int(p["end"] * sr) + fade)
        if b - a < fade * 3:
            continue
        seg = _shift(mono[a:b].astype(np.float32), sr, float(p["shift"]))[: b - a].astype(np.float32)
        n = seg.shape[0]
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        seg[:fade] *= ramp
        seg[n - fade:] *= ramp[::-1]
        out[a:a + n] += seg
    return out


def chord_harmony(
    wav_bytes: bytes, song, harmony_type: str = "above", sections: set[int] | None = None, notes: list | None = None,
) -> tuple[bytes, list[dict]]:
    """
    A harmony from the person's own voice where every note is a note of the chord playing at that moment.
    `harmony_type` is "above", "below" or "both". Returns (WAV bytes, the plan of harmony notes).
    """
    from app.services.audio import vocal_notes

    y, sr = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    if y.size == 0:
        return wav_bytes, []
    y = y.astype(np.float32)
    if notes is None:
        notes = vocal_notes.sung_notes(y, sr)
    directions = ["above", "below"] if harmony_type == "both" else [harmony_type if harmony_type in ("above", "below") else "above"]
    out = np.zeros_like(y)
    plans: list[dict] = []
    for d in directions:
        plan = plan_harmony(notes, song, d, sections)
        plans += [{**p, "direction": d} for p in plan]
        out += render_harmony(y, sr, plan) * (0.7 if len(directions) > 1 else 1.0)
    peak = float(np.abs(out).max())
    if peak > 0:
        out *= 0.75 / peak
    buf = io.BytesIO()
    sf.write(buf, out, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue(), plans
