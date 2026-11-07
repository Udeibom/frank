"""
Vocal pitch analysis and correction.

Detection: librosa pyin gives a fundamental-frequency contour with a confidence
flag per frame. We expose that as a simple colour-coded contour for the UI and
use it to drive correction.

Correction: Rubber Band (via pylibrb) pitch-shifts the vocal toward the nearest
in-key/chromatic note. Three strengths, named in plain language for the user.
Fast enough (Rubber Band does 30s in ~2.6s) to run per take in a background job.

All CPU, no neural models. The original take is never modified — correction
always produces a new audio buffer.
"""

from __future__ import annotations
import io
import numpy as np
import librosa
import soundfile as sf
import pylibrb

SR = 44100

# Pitch detection runs at a reduced sample rate with a coarse hop. pyin at full
# 44.1kHz is ~10x slower for no benefit here — a contour for display and tuning
# doesn't need sample-accurate frequency. 16kHz covers vocal range comfortably.
PITCH_SR = 16000
PITCH_HOP = 1024
PITCH_FRAME = 2048
PITCH_FMIN = 80.0
PITCH_FMAX = 1000.0

# Correction strength by mode: the fraction of the detected error we remove, and
# the minimum error (in cents) a note must be off before we touch it.
CORRECTION_MODES = {
    "light": {"strength": 0.5, "threshold_cents": 50.0},    # just the obvious misses
    "moderate": {"strength": 0.8, "threshold_cents": 20.0}, # tighten it up
    "full": {"strength": 1.0, "threshold_cents": 0.0},      # lock it in (autotune)
}


def _analyze(y: np.ndarray, sr: int):
    """Run pyin with Frank's fast settings. Returns (f0, voiced_prob)."""
    f0, _, voiced_prob = librosa.pyin(
        y,
        fmin=PITCH_FMIN,
        fmax=PITCH_FMAX,
        sr=sr,
        hop_length=PITCH_HOP,
        frame_length=PITCH_FRAME,
    )
    return f0, voiced_prob


def detect_pitch_contour(wav_bytes: bytes) -> list[dict]:
    """
    Return a pitch contour: [{time, note (MIDI float), confidence (0..1)}, ...].
    Unvoiced frames are skipped. Used for the UI's colour-coded display and to
    drive correction. Runs at reduced rate for speed.
    """
    y, sr = librosa.load(io.BytesIO(wav_bytes), sr=PITCH_SR, mono=True)
    if y.size == 0:
        return []

    f0, voiced_prob = _analyze(y, sr)
    times = librosa.times_like(f0, sr=sr, hop_length=PITCH_HOP)

    contour: list[dict] = []
    for t, hz, prob in zip(times, f0, voiced_prob):
        if hz is None or np.isnan(hz):
            continue
        midi = float(librosa.hz_to_midi(hz))
        contour.append(
            {
                "time": round(float(t), 3),
                "note": round(midi, 2),
                "confidence": round(float(prob), 3),
            }
        )
    return contour


def _pitch_shift(mono: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Pitch-shift mono float32 audio by `semitones` using Rubber Band."""
    if abs(semitones) < 1e-4:
        return mono
    scale = 2.0 ** (semitones / 12.0)
    st = pylibrb.RubberBandStretcher(
        sample_rate=sr, channels=1, initial_pitch_scale=scale
    )
    buf = mono.reshape(1, -1).astype(np.float32)
    st.study(buf, final=True)
    st.process(buf, final=True)
    out = st.retrieve_available()
    return out[0] if out.ndim == 2 else out


def _snap_to_grid(
    mono: np.ndarray, sr: int, f0: np.ndarray, pitch_sr: int
) -> np.ndarray:
    """
    "Lock it in" correction: snap off notes to the chromatic grid, segment by
    segment, so each note is actually pulled to pitch (the autotuned sound).

    We walk the pitch contour, group consecutive voiced frames into note
    segments, and for each segment apply a Rubber Band shift equal to the
    segment's distance from its nearest chromatic note. Segments are spliced
    with short crossfades. Unlike a global average shift, this moves every off
    note toward the grid even when the errors cancel out on average.
    """
    hop = PITCH_HOP
    samples_per_frame = int(hop * sr / pitch_sr)  # map 16kHz frames to full-rate

    # Build (start_sample, end_sample, shift_semitones) note segments
    segments: list[tuple[int, int, float]] = []
    seg_start_frame = None
    seg_shift = 0.0
    for i, hz in enumerate(f0):
        voiced = hz is not None and not np.isnan(hz)
        if voiced:
            midi = float(librosa.hz_to_midi(hz))
            shift = round(midi) - midi  # semitones to nearest note
            if seg_start_frame is None:
                seg_start_frame, seg_shift = i, shift
            else:
                # New segment when the target note changes meaningfully
                if abs(shift - seg_shift) > 0.5:
                    segments.append(
                        (seg_start_frame * samples_per_frame, i * samples_per_frame, seg_shift)
                    )
                    seg_start_frame, seg_shift = i, shift
        else:
            if seg_start_frame is not None:
                segments.append(
                    (seg_start_frame * samples_per_frame, i * samples_per_frame, seg_shift)
                )
                seg_start_frame = None
    if seg_start_frame is not None:
        segments.append(
            (seg_start_frame * samples_per_frame, len(f0) * samples_per_frame, seg_shift)
        )

    if not segments:
        return mono

    out = np.copy(mono)
    fade = int(0.01 * sr)
    for start, end, shift in segments:
        start = max(0, min(start, mono.shape[0]))
        end = max(0, min(end, mono.shape[0]))
        if end - start < fade * 2 or abs(shift) < 0.02:
            continue
        shifted = _pitch_shift(mono[start:end], sr, shift)
        n = min(shifted.shape[0], end - start)
        # Crossfade edges to hide splices
        seg = shifted[:n].copy()
        if n > fade * 2:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            seg[:fade] = seg[:fade] * ramp + out[start:start + fade] * (1 - ramp)
            seg[-fade:] = seg[-fade:] * (1 - ramp) + out[end - fade:end] * ramp
        out[start:start + n] = seg
    return out


def correct_pitch(wav_bytes: bytes, mode: str = "light") -> bytes:
    """
    Apply pitch correction to a vocal take. Returns new WAV bytes.

    Approach: detect the contour, find the overall tuning error toward the
    nearest chromatic grid, and apply a single corrective shift scaled by the
    mode's strength. (A full per-note re-pitch would be segment-spliced; for the
    MVP a confidence-weighted global nudge gives a natural, musical result
    without the artefacts of aggressive per-frame correction — except in "full"
    mode, which snaps harder for the autotuned effect.)
    """
    settings = CORRECTION_MODES.get(mode, CORRECTION_MODES["light"])

    # Analyze pitch at the reduced rate (fast), but keep the full-rate audio for
    # the actual pitch shift so output quality isn't degraded.
    y_full, sr_full = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    if y_full.size == 0:
        return wav_bytes
    y_lo = librosa.resample(y_full, orig_sr=sr_full, target_sr=PITCH_SR)

    f0, voiced_prob = _analyze(y_lo, PITCH_SR)

    # Error in cents from the nearest semitone, per voiced frame
    errors_cents: list[float] = []
    weights: list[float] = []
    for hz, prob in zip(f0, voiced_prob):
        if hz is None or np.isnan(hz) or prob < 0.3:
            continue
        midi = librosa.hz_to_midi(hz)
        nearest = round(midi)
        cents = (midi - nearest) * 100.0
        errors_cents.append(cents)
        weights.append(float(prob))

    if not errors_cents:
        return wav_bytes

    errors = np.array(errors_cents)
    w = np.array(weights)

    # Confidence-weighted average tuning error
    avg_error_cents = float(np.average(errors, weights=w))

    # Only correct if the average error exceeds the mode threshold
    if abs(avg_error_cents) < settings["threshold_cents"]:
        return wav_bytes

    if mode == "full":
        # "Lock it in" — real per-note snapping to the chromatic grid, so each
        # off note is pulled to pitch (the produced/autotuned sound). A single
        # global shift can't do this: +40 and -40 cent notes average to ~0.
        corrected = _snap_to_grid(y_full.astype(np.float32), sr_full, f0, PITCH_SR)
    else:
        # "light"/"moderate" — remove the consistent tuning bias with a single
        # clean shift (no splice artifacts). Natural, gentle.
        correction_semitones = -(avg_error_cents / 100.0) * settings["strength"]
        corrected = _pitch_shift(
            y_full.astype(np.float32), sr_full, correction_semitones
        )

    buf = io.BytesIO()
    sf.write(buf, corrected, sr_full, format="WAV", subtype="PCM_16")
    return buf.getvalue()
