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


# ── tuning to the song's own notes (sing-it spec 06, requirement 2) ──────

LOCK_STEP_S = 0.05           # "Lock it in" flattens the line in steps this long
SPLICE_FADE_S = 0.008


def plan_moves(notes: list, song, mode: str) -> list[dict]:
    """
    Decide each sung note's move (pure: no audio). A note already within the mode's threshold of its target is
    never touched (property 1); every move brings a note closer to its target (property 2).
    A wrong note (a whole step or more from the target) is moved all the way in every mode, so it never ends up
    stranded between two notes; the fine error inside a note is removed at the mode's strength.
    """
    from app.services.audio.song_notes import target_note

    settings = CORRECTION_MODES.get(mode, CORRECTION_MODES["light"])
    moves: list[dict] = []
    for n in notes:
        if not np.isfinite(n.centre):
            continue
        t = song.at((n.start + n.end) / 2)
        target = target_note(n.centre, t)
        error = target - n.centre
        if abs(error) * 100.0 < max(settings["threshold_cents"], 1.0):
            continue
        whole = float(round(error))                     # semitones of wrong note
        fine = error - whole
        shift = whole + settings["strength"] * fine
        moves.append({"start": n.start, "end": n.end, "from": round(n.centre, 2), "to": target, "shift": round(shift, 4),
                      "section": t.section, "before_cents": round(abs(error) * 100), "after_cents": round(abs(error - shift) * 100)})
    return moves


def _splice(out: np.ndarray, src: np.ndarray, start: int, end: int, shift: float, sr: int) -> None:
    fade = int(SPLICE_FADE_S * sr)
    start, end = max(0, start - fade), min(src.shape[0], end + fade)
    if end - start < fade * 3 or abs(shift) < 1e-3:
        return
    seg = _pitch_shift(src[start:end], sr, shift)
    n = min(seg.shape[0], end - start)
    seg = seg[:n].astype(np.float32)
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    seg[:fade] = seg[:fade] * ramp + out[start:start + fade] * (1 - ramp)
    seg[n - fade:n] = seg[n - fade:n] * (1 - ramp) + out[start + n - fade:start + n] * ramp
    out[start:start + n] = seg


def tune(mono: np.ndarray, sr: int, mode: str, song, notes: list | None = None) -> tuple[np.ndarray, list[dict]]:
    """
    Tune a mono take toward the song's notes. Gentle modes move each note by one amount, so slides and vibrato
    inside the note are kept (requirement 2.3); "Lock it in" also straightens the line inside each note.
    Returns (new audio, the moves made). The input is never changed.
    """
    from app.services.audio import vocal_notes

    if notes is None:
        notes = vocal_notes.sung_notes(mono, sr)
    moves = plan_moves(notes, song, mode)
    out = mono.astype(np.float32).copy()
    src = mono.astype(np.float32)
    by_start = {round(n.start, 4): n for n in notes}
    for m in moves:
        a, b = int(m["start"] * sr), int(m["end"] * sr)
        if mode != "full":
            _splice(out, src, a, b, m["shift"], sr)
            continue
        note = by_start.get(round(m["start"], 4))
        frames = note.frames if note is not None else np.array([m["from"]])
        step = max(1, int(LOCK_STEP_S * sr))
        for k, x in enumerate(range(a, b, step)):
            lo = int(k * len(frames) * step / max(1, b - a))
            hi = max(lo + 1, int((k + 1) * len(frames) * step / max(1, b - a)))
            here = np.nanmedian(frames[lo:hi]) if np.any(np.isfinite(frames[lo:hi])) else m["from"]
            _splice(out, src, x, min(b, x + step), float(m["to"] - here), sr)
    return out, moves


def tune_take(wav_bytes: bytes, mode: str, song=None) -> tuple[bytes, list[dict]]:
    """WAV in, WAV out, plus the moves. `song` is a SongNotes; without one every note of the twelve is allowed."""
    from app.services.audio.song_notes import SongNotes

    y, sr = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    if y.size == 0:
        return wav_bytes, []
    out, moves = tune(y, sr, mode, song or SongNotes())
    buf = io.BytesIO()
    sf.write(buf, np.clip(out, -1.0, 1.0), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue(), moves


def correct_pitch(wav_bytes: bytes, mode: str = "light", song=None) -> bytes:
    """Kept for callers that only want the audio."""
    return tune_take(wav_bytes, mode, song)[0]
