"""
Timing (sing-it spec 06, requirement 3).

1. Device delay: the browser plays four clicks at known times while recording; the person claps along (or the mic
   hears the speakers). The delay is the median gap between each click and the sound that answered it.
2. Placing a take in song time: the browser says how long after the recording started the beat began
   (`lead_in_s`) and where in the song the beat started (`beat_offset_s`). The take is trimmed by lead-in + delay
   and placed at its song position, so every downstream tool (mix, tuning, harmony, comp) reads song time.
3. Tighten the timing: phrases that start clearly early or late against the beat move toward it, never more than
   a quarter of a beat, and never in the gentlest setting.
"""
from __future__ import annotations

from typing import Optional

import librosa
import numpy as np

MAX_DELAY_S = 0.6
TIGHTEN = {"light": None, "moderate": {"min_off": 0.12, "strength": 0.7}, "full": {"min_off": 0.05, "strength": 1.0}}
GRID_DIVISION = 2            # phrases are lined up to the nearest half beat (people start on the "and" too)
MAX_MOVE_BEATS = 0.25
FADE_S = 0.01


def detect_delay(recording: np.ndarray, sr: int, click_times: list[float]) -> tuple[Optional[float], float]:
    """(delay in seconds, confidence 0..1). None when too few clicks were answered to tell."""
    if recording.size < sr // 4 or not click_times:
        return None, 0.0
    onsets = librosa.onset.onset_detect(y=recording.astype(np.float32), sr=sr, hop_length=128, units="time", backtrack=True)
    gaps: list[float] = []
    env = np.abs(recording.astype(np.float32))
    for c in click_times:
        after = [o for o in onsets if -0.05 <= o - c <= MAX_DELAY_S]
        if after:
            gaps.append(_sharpen(env, sr, min(after)) - c)   # the first sound after the click is the answer to it
    if len(gaps) < max(2, len(click_times) // 2):
        return None, 0.0
    med = float(np.median(gaps))
    spread = float(np.median(np.abs(np.array(gaps) - med)))
    conf = max(0.0, min(1.0, len(gaps) / len(click_times) * (1.0 - spread / 0.05)))
    return max(0.0, med), conf


def _sharpen(env: np.ndarray, sr: int, onset: float) -> float:
    """The onset detector works in steps of a few milliseconds; the sound starts where it first gets loud."""
    a, b = max(0, int((onset - 0.03) * sr)), min(env.size, int((onset + 0.06) * sr))
    if b - a < 8:
        return onset
    win = env[a:b]
    peak = float(win.max())
    floor = float(np.median(env[max(0, a - int(0.1 * sr)):a])) if a > 0 else 0.0
    if peak <= floor * 2:
        return onset
    first = int(np.argmax(win > floor + 0.5 * (peak - floor)))
    return (a + first) / sr


def place_in_song(mono: np.ndarray, sr: int, lead_in_s: float, delay_s: float, beat_offset_s: float) -> np.ndarray:
    """The take in song time: sample k is what was sung at song second k / sr."""
    trim = int(round((lead_in_s + delay_s) * sr))
    body = mono[trim:] if trim >= 0 else np.concatenate([np.zeros(-trim, dtype=mono.dtype), mono])
    pad = int(round(max(0.0, beat_offset_s) * sr))
    return np.concatenate([np.zeros(pad, dtype=mono.dtype), body]) if pad else body.copy()


def phrase_moves(starts: list[float], seconds_per_beat: float, mode: str) -> list[float]:
    """How far each phrase start moves (seconds, + is later). Pure, so it can be property-tested."""
    rule = TIGHTEN.get(mode)
    if rule is None:
        return [0.0 for _ in starts]
    grid = seconds_per_beat / GRID_DIVISION
    cap = MAX_MOVE_BEATS * seconds_per_beat
    out: list[float] = []
    for s in starts:
        off = round(s / grid) * grid - s
        if abs(off) < rule["min_off"] * seconds_per_beat:
            out.append(0.0)
            continue
        out.append(float(np.clip(off * rule["strength"], -cap, cap)))
    return out


def tighten(mono: np.ndarray, sr: int, phrases: list[tuple[float, float]], seconds_per_beat: float, mode: str) -> tuple[np.ndarray, list[dict]]:
    """Move whole phrases toward the beat. The audio between phrases (breaths) stays where it was."""
    moves = phrase_moves([a for a, _ in phrases], seconds_per_beat, mode)
    if not any(moves):
        return mono.copy(), []
    out = mono.astype(np.float32).copy()
    fade = int(FADE_S * sr)
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    report: list[dict] = []
    pieces: list[tuple[int, np.ndarray]] = []
    for (a, b), m in zip(phrases, moves):
        if not m:
            continue
        i, j = max(0, int(a * sr) - fade), min(mono.shape[0], int(b * sr) + fade)
        seg = mono[i:j].astype(np.float32).copy()
        if seg.shape[0] < 3 * fade:
            continue
        seg[:fade] *= ramp
        seg[-fade:] *= ramp[::-1]
        out[i:j] *= np.concatenate([ramp[::-1], np.zeros(j - i - 2 * fade, dtype=np.float32), ramp])   # take it out
        pieces.append((i + int(round(m * sr)), seg))
        report.append({"start": round(a, 3), "moved_ms": round(m * 1000)})
    for at, seg in pieces:
        at = max(0, at)
        n = min(seg.shape[0], out.shape[0] - at)
        if n > 0:
            out[at:at + n] += seg[:n]
    return out, report


def sits_ms(vocal: np.ndarray, beat: Optional[np.ndarray], sr: int) -> Optional[float]:
    """The Listener's own measure of where the singing sits against the beat (ms, + is behind)."""
    from app.services.listener import dsp

    if beat is None:
        return None
    n = min(vocal.shape[0], beat.shape[0])
    got = dsp.timing_offset_ms(vocal[:n], beat[:n], sr)
    return None if got is None or got[1] < 0.15 else got[0]
