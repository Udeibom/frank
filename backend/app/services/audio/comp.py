"""
Vocal comping — stitch the best moments from several takes into one.

We split each take into short time windows, score each window by how confidently
pitched and how energetic it is (a proxy for a committed, in-tune delivery), and
for each window pick the best take. The winning windows are concatenated with
short crossfades so the seams aren't audible.

The result is a suggestion the user can accept or adjust — never the final word.
All CPU, runs in a background job.
"""

from __future__ import annotations
import io
import numpy as np
import librosa
import soundfile as sf

SR = 44100
PITCH_SR = 16000  # scoring runs at reduced rate for fast pyin
WINDOW_SECONDS = 2.0
CROSSFADE_SECONDS = 0.05


def _load(wav_bytes: bytes) -> np.ndarray:
    y, _ = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    return y.astype(np.float32)


def _window_score(segment_lo: np.ndarray) -> float:
    """
    Higher is better: confident pitch + healthy energy.
    Expects the segment already downsampled to PITCH_SR for fast pyin.
    """
    if segment_lo.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(segment_lo**2)))
    try:
        _, _, voiced_prob = librosa.pyin(
            segment_lo,
            fmin=80.0,
            fmax=1000.0,
            sr=PITCH_SR,
            hop_length=1024,
            frame_length=2048,
        )
        pitch_conf = float(np.nanmean(voiced_prob)) if voiced_prob.size else 0.0
        if np.isnan(pitch_conf):
            pitch_conf = 0.0
    except Exception:
        pitch_conf = 0.0
    # Weight pitch confidence a bit higher than loudness
    return 0.6 * pitch_conf + 0.4 * min(rms * 5.0, 1.0)


def build_comp(takes: list[tuple[str, bytes]]) -> tuple[bytes, list[dict]]:
    """
    takes: list of (take_id, wav_bytes). Returns (comp_wav_bytes, segments).
    segments: [{take_id, start_time, end_time}] describing which take won each
    window — used by the UI to show the colour-coded comp.
    """
    if not takes:
        return b"", []

    # Full-rate audio for output, plus a downsampled copy per take for scoring
    loaded = [(tid, _load(b)) for tid, b in takes]
    loaded_lo = [
        (tid, librosa.resample(a, orig_sr=SR, target_sr=PITCH_SR))
        for tid, a in loaded
    ]
    max_len = max(a.shape[0] for _, a in loaded)
    win = int(WINDOW_SECONDS * SR)
    win_lo = int(WINDOW_SECONDS * PITCH_SR)
    fade = int(CROSSFADE_SECONDS * SR)

    comp = np.zeros(max_len, dtype=np.float32)
    segments: list[dict] = []
    prev_take: str | None = None

    for wi, start in enumerate(range(0, max_len, win)):
        end = min(start + win, max_len)
        start_lo = wi * win_lo
        # Score this window across all takes (on the downsampled copies)
        best_tid, best_audio, best_score = loaded[0][0], None, -1.0
        for (tid, audio), (_, audio_lo) in zip(loaded, loaded_lo):
            seg = audio[start:end]
            if seg.shape[0] < end - start:
                seg = np.pad(seg, (0, (end - start) - seg.shape[0]))
            seg_lo = audio_lo[start_lo:start_lo + win_lo]
            score = _window_score(seg_lo)
            if score > best_score:
                best_tid, best_audio, best_score = tid, seg, score

        if best_audio is None:
            continue

        # Crossfade into the previous window to hide seams
        chunk = best_audio.copy()
        if start > 0 and fade > 0 and chunk.shape[0] >= fade:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            chunk[:fade] *= ramp
            comp[start:start + fade] *= (1.0 - ramp)
        comp[start:end] += chunk[: end - start]

        # Record the segment (merge consecutive windows from the same take).
        # A tail window too short to survive 2-decimal rounding (< 5 ms, e.g. a
        # take 2 samples longer than the others) would become a zero-length
        # segment; fold it into the previous segment instead. Found by a
        # property-based test (tests/test_properties_comp.py).
        too_short = round(end / SR, 2) <= round(start / SR, 2)
        if segments and (prev_take == best_tid or too_short):
            segments[-1]["end_time"] = round(end / SR, 2)
        else:
            segments.append(
                {
                    "take_id": best_tid,
                    "start_time": round(start / SR, 2),
                    "end_time": round(end / SR, 2),
                }
            )
        if not too_short:
            prev_take = best_tid

    # Normalize
    peak = float(np.abs(comp).max())
    if peak > 0:
        comp *= 0.89 / peak

    buf = io.BytesIO()
    sf.write(buf, comp, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue(), segments
