"""
Hum to melody (start-from-any-input spec 02, requirement 3).

Turns a clean, single-voice hum into notes with timing, a key and a tempo, each with a
confidence. It never guesses silently: weak or noisy input is rejected with a plain reason,
and low confidence is reported so Frank can ask instead of assume.

Pipeline: decode -> pitch track (pyin) -> note segmentation -> tempo from note timing ->
quantise to a 16th grid -> key from the notes -> quality gate -> self-check (fit).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field, replace
from typing import Optional

import librosa
import numpy as np
from scipy.signal import medfilt

from app.models.song import MelodyNote, MelodySketch
from app.services.audio.convert import to_wav
from app.services.intake.pitch_track import pyin_fast
from app.services.generation.theory import NOTE_NAMES

SR = 22050
HOP = 128                 # ~5.8 ms per step: fine enough to follow quick notes
FRAME = 1024              # ~46 ms of sound per look
HOP_S = HOP / SR

# Time rules are written in seconds and converted, so they do not change if the step size does.
GAP_S = 0.046             # gaps up to this do not split a note
GAP_FRAMES = max(1, round(GAP_S / HOP_S))
MIN_NOTE_S = 0.06         # shorter than this is a blip, not a note
SPLIT_SEMITONES = 0.7     # a pitch move this big, held, starts a new note
SPLIT_HOLD_S = 0.06       # ...for at least this long
SPLIT_HOLD_FRAMES = max(1, round(SPLIT_HOLD_S / HOP_S))
MEDIAN_KERNEL = 7         # ~40 ms of smoothing over the pitch track
GRID_BEATS = 0.25         # 16th notes
COARSE_GRID_BEATS = 0.5   # eighth notes: used when the speed is uncertain, so loose timing is not over-fitted
CONFIDENT = 0.6
ORNAMENT_S = 0.15         # at most this long (less for a fast hummer), next to a neighbouring note, is a wobble not a note
ORNAMENT_MIN_S = 0.07
ORNAMENT_SHARE_OF_TYPICAL = 0.3   # ...and always well under the person's own typical note length
OCTAVE_FIX_MAX_S = 0.3
OCTAVE_CONTEXT_SPREAD = 7  # neighbours this close together mean an octave-away note between them is a glitch
RARE_SHARE = 0.04         # a note name sung this little...
STRONG_SHARE = 0.12       # ...next to one sung this much is probably the same note slightly off
SHORT_OUT_OF_KEY_S = 0.4
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10, 11)  # natural minor plus the leading tone
DIP_RATIO = 0.4           # a loudness dip below this share of the note's level means a new note starts
DIP_MIN_S = 0.023         # ...if it lasts at least this long
DIP_MIN_FRAMES = max(1, round(DIP_MIN_S / HOP_S))

# Pitch search range: from about D2 (73 Hz, a low voice) to C6 (1046 Hz).
SEARCH_LOW = "D2"
SEARCH_HIGH = "C6"
PYIN_RESOLUTION = 0.1      # pitch steps per note

TEMPO_MIN, TEMPO_MAX = 50, 180
MIN_ONSETS_FOR_TEMPO = 6
TEMPO_FAMILY_TOLERANCE = 0.9   # a doubled/halved tempo this nearly as good counts as the same pulse
OUTLIER_SEMITONES = 10         # short notes this far from the tune's centre are tracker noise
OUTLIER_MAX_S = 0.3

# Krumhansl-Kessler key profiles (how much each scale step is expected in a major/minor tune)
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_TONIC_END_BONUS = 0.05   # tunes tend to end on their home note

# Longest recording analysed. Pitch decoding holds a table with a row per moment and a column per
# possible pitch, so memory grows with length; a minute is far more than a tune needs.
MAX_HUM_SECONDS = 60

# Quality gate
MIN_VOICED_SECONDS = 2.0
MIN_NOTES = 4
MIN_MEAN_VOICED_PROB = 0.6
MAX_MEDIAN_LEAP = 9.0     # semitones; bigger usually means noise or several voices
MAX_RANGE = 30            # semitones


@dataclass
class RawNote:
    start_s: float
    end_s: float
    midi: int                 # nearest note after tuning is applied
    midi_f: float = 0.0       # the pitch actually sung, in fractional notes


@dataclass
class MelodyExtraction:
    ok: bool
    reason: Optional[str] = None        # plain-language reason when ok is False
    sketch: Optional[MelodySketch] = None
    diagnostics: dict = field(default_factory=dict)
    raw_notes: list = field(default_factory=list)   # notes with their real timing, for debugging and comparison


# ─── Pitch tracking ──────────────────────────

def decode_mono(audio_bytes: bytes, ext: str = "wav") -> np.ndarray:
    """Any browser/phone format in, mono float audio at SR out."""
    wav = to_wav(audio_bytes, ext)
    y, _ = librosa.load(io.BytesIO(wav), sr=SR, mono=True)
    return y


def track_pitch(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (midi per frame with NaN where unvoiced, voiced probability, frame times)."""
    f0, voiced_flag, voiced_prob = pyin_fast(
        y,
        fmin=float(librosa.note_to_hz(SEARCH_LOW)),
        fmax=float(librosa.note_to_hz(SEARCH_HIGH)),
        sr=SR,
        frame_length=FRAME,
        hop_length=HOP,
        resolution=PYIN_RESOLUTION,
    )
    midi = np.full(len(f0), np.nan)
    ok = voiced_flag & ~np.isnan(f0)
    midi[ok] = librosa.hz_to_midi(f0[ok])
    times = librosa.times_like(f0, sr=SR, hop_length=HOP)
    return midi, np.nan_to_num(voiced_prob), times


def track_energy(y: np.ndarray) -> np.ndarray:
    """Loudness per frame, on the same frames as the pitch track (short window so brief dips show)."""
    rms = librosa.feature.rms(y=y, frame_length=512, hop_length=HOP, center=True)[0]
    return rms


# ─── Note segmentation ───────────────────────

def _runs(valid_idx: np.ndarray) -> list[np.ndarray]:
    """Group voiced frame indices into runs, splitting where the gap is longer than GAP_FRAMES."""
    if valid_idx.size == 0:
        return []
    splits = np.where(np.diff(valid_idx) > GAP_FRAMES + 1)[0] + 1
    return np.split(valid_idx, splits)


def _split_run(vals: np.ndarray) -> list[tuple[int, int]]:
    """Split one run of smoothed pitches into (start, end) note spans (end exclusive)."""
    n = len(vals)
    spans: list[tuple[int, int]] = []
    start = 0
    center = float(vals[0])
    cand: Optional[int] = None
    for i in range(1, n):
        if abs(vals[i] - center) > SPLIT_SEMITONES:
            if cand is not None and abs(vals[i] - float(np.median(vals[cand:i]))) > SPLIT_SEMITONES:
                cand = i                       # the candidate itself is still moving: restart it
            elif cand is None:
                cand = i
            if i - cand + 1 >= SPLIT_HOLD_FRAMES:
                spans.append((start, cand))
                start = cand
                center = float(np.median(vals[cand : i + 1]))
                cand = None
        else:
            cand = None
            center = float(np.median(vals[start : i + 1]))
    spans.append((start, n))
    return spans


def _split_on_dips(frames: np.ndarray, rms: np.ndarray) -> list[tuple[int, int]]:
    """
    Split one held pitch where the sound briefly dips (a repeated note: "da, da, da").
    `frames` are indices into the pitch track. Returns (first, last) frame spans, inclusive.
    """
    level = rms[frames]
    if level.size < 2 * DIP_MIN_FRAMES + 2:
        return [(int(frames[0]), int(frames[-1]))]
    ref = float(np.percentile(level, 75))
    if ref <= 0:
        return [(int(frames[0]), int(frames[-1]))]
    low = level < DIP_RATIO * ref
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            # a dip strictly inside the note, long enough, with sound on both sides
            if j - i >= DIP_MIN_FRAMES and i > 0 and j < len(low):
                spans.append((int(frames[start]), int(frames[i - 1])))
                start = j
            i = j
        else:
            i += 1
    spans.append((int(frames[start]), int(frames[-1])))
    return [(a, b) for a, b in spans if b >= a]


def segment_notes(midi: np.ndarray, times: np.ndarray, rms: Optional[np.ndarray] = None) -> list[RawNote]:
    valid_idx = np.where(~np.isnan(midi))[0]
    notes: list[RawNote] = []
    for run in _runs(valid_idx):
        vals = midi[run]
        if len(vals) >= MEDIAN_KERNEL:
            vals = medfilt(vals, kernel_size=MEDIAN_KERNEL)
        run_notes: list[RawNote] = []
        for s, e in _split_run(vals):
            if e <= s:
                continue
            pitch_f = float(np.median(vals[s:e]))
            frames = run[s:e]
            pieces = _split_on_dips(frames, rms) if rms is not None and len(frames) else [(int(frames[0]), int(frames[-1]))]
            for first, last in pieces:
                start_s = float(times[first])
                end_s = float(times[last]) + HOP_S
                if end_s - start_s < MIN_NOTE_S:
                    continue
                run_notes.append(RawNote(start_s, end_s, int(round(pitch_f)), pitch_f))
        # Neighbours in the same run with the same pitch are one note.
        for note in run_notes:
            notes.append(note)
    return drop_outliers(notes)


def drop_outliers(notes: list[RawNote]) -> list[RawNote]:
    """
    Remove short notes far from the tune's centre. The tracker sometimes latches onto a
    breath or a subharmonic for a moment; a real hummed note is held longer than that.
    """
    if len(notes) < 5:
        return notes
    weights = np.array([n.end_s - n.start_s for n in notes])
    pitches = np.array([n.midi for n in notes], dtype=float)
    order = np.argsort(pitches)
    cum = np.cumsum(weights[order])
    centre = float(pitches[order][np.searchsorted(cum, cum[-1] / 2.0)])  # duration-weighted median
    return [
        n for n in notes
        if not (abs(n.midi - centre) > OUTLIER_SEMITONES and (n.end_s - n.start_s) < OUTLIER_MAX_S)
    ]


# ─── Tuning ──────────────────────────────────

def estimate_tuning_offset(notes: list[RawNote]) -> float:
    """
    How far, in notes, the singer sits from standard tuning (-0.5..0.5). People rarely hum exactly
    on concert pitch; without this a hum centred between two notes flips back and forth between
    them. Found as the duration-weighted circular mean of each note's distance from a whole note.
    """
    if not notes:
        return 0.0
    w = np.array([n.end_s - n.start_s for n in notes])
    frac = np.array([n.midi_f for n in notes])
    z = (w * np.exp(2j * np.pi * frac)).sum()
    return float(np.angle(z) / (2 * np.pi))


def apply_tuning(notes: list[RawNote]) -> float:
    """Re-round every note against the singer's own tuning. Returns the offset used."""
    offset = estimate_tuning_offset(notes)
    for n in notes:
        n.midi = int(round(n.midi_f - offset))
    return offset


# ─── Tempo ───────────────────────────────────

def _tempo_prior(bpm: float) -> float:
    """Gentle preference for common walking-pace tempos, so doubling/halving ties resolve sensibly."""
    return float(np.exp(-0.5 * (np.log2(bpm / 100.0) / 0.5) ** 2))


def _alignment(onsets_s: np.ndarray, bpm: float) -> tuple[float, float]:
    """How well the note starts line up with an eighth-note grid at `bpm`: (strength 0..1, phase seconds)."""
    step = 60.0 / bpm / 2.0
    z = np.exp(2j * np.pi * onsets_s / step).mean()
    return float(abs(z)), float((np.angle(z) / (2 * np.pi)) * step)


def estimate_tempo(onsets_s: np.ndarray) -> tuple[Optional[float], float, float]:
    """
    Find the tempo whose eighth-note grid best lines up with when the notes start.
    Returns (bpm or None, confidence 0..1, grid phase in seconds). None when there is too
    little timing to say anything, so the caller can ask instead of assuming.

    The evidence picks the tempo. The preference for walking-pace tempos is only used to choose
    between a tempo and its double or half when both fit almost equally well (they are the same
    pulse counted differently). Confidence compares the winner with what a random speed would
    score on these same notes, so a regular hum scores high and a free-time one scores low.
    """
    if onsets_s.size < MIN_ONSETS_FOR_TEMPO:
        return None, 0.0, 0.0

    bpms = list(range(TEMPO_MIN, TEMPO_MAX + 1))
    raw = {b: _alignment(onsets_s, b)[0] for b in bpms}
    best_bpm = max(bpms, key=lambda b: raw[b])
    best_raw = raw[best_bpm]

    # Same pulse, counted differently: pick the member of the family closest to a natural pace.
    family = [best_bpm]
    for factor in (0.5, 2.0):
        other = int(round(best_bpm * factor))
        if other in raw and raw[other] >= TEMPO_FAMILY_TOLERANCE * best_raw:
            family.append(other)
    chosen = max(family, key=_tempo_prior)

    typical = float(np.median(list(raw.values())))
    confidence = float(np.clip((raw[chosen] - typical) / 0.5, 0.0, 1.0))
    return float(chosen), confidence, _alignment(onsets_s, chosen)[1]


# ─── Quantise ────────────────────────────────

def quantise(notes: list[RawNote], bpm: float, phase_s: float, grid: float = GRID_BEATS) -> list[MelodyNote]:
    """Snap note starts and lengths to the 16th grid. The first note lands on beat 0."""
    if not notes:
        return []
    beat_s = 60.0 / bpm
    grid_s = beat_s * grid
    first_k = round((notes[0].start_s - phase_s) / grid_s)
    out: list[MelodyNote] = []
    last_end_k = -10**9
    for n in notes:
        k = round((n.start_s - phase_s) / grid_s) - first_k
        length_k = max(1, round((n.end_s - n.start_s) / grid_s))
        k = max(k, last_end_k)                       # never overlap the previous note
        out.append(MelodyNote(pitch_midi=n.midi, start_beat=k * grid, dur_beats=length_k * grid))
        last_end_k = k + length_k
    return out


def fallback_quantise(notes: list[RawNote], bpm: float) -> list[MelodyNote]:
    """Used when timing is too weak to find a grid: still snap to the grid, anchored at the first note."""
    return quantise(notes, bpm, notes[0].start_s if notes else 0.0)


def performed_notes(notes: list[RawNote], bpm: float) -> list[MelodyNote]:
    """
    The tune with the timing the person actually sang, written in beats at the estimated speed.
    No grid snapping: a player following a hum follows the singer, not a metronome.
    """
    if not notes:
        return []
    t0 = notes[0].start_s
    k = bpm / 60.0
    out: list[MelodyNote] = []
    for i, n in enumerate(notes):
        start = (n.start_s - t0) * k
        end = (n.end_s - t0) * k
        if i + 1 < len(notes):
            end = min(end, (notes[i + 1].start_s - t0) * k)   # never overlap the next note
        out.append(MelodyNote(pitch_midi=n.midi, start_beat=round(start, 4), dur_beats=round(max(end - start, 0.05), 4)))
    return out


# ─── Key ─────────────────────────────────────

def estimate_key(notes: list[RawNote]) -> tuple[str, str, float]:
    """Key and mode from the notes, weighted by how long each is held. Returns (key, mode, confidence)."""
    hist = np.zeros(12)
    for n in notes:
        hist[n.midi % 12] += n.end_s - n.start_s
    if hist.sum() <= 0:
        return "C", "minor", 0.0
    last_pc = notes[-1].midi % 12
    scored: list[tuple[float, int, str]] = []
    for tonic in range(12):
        for mode, profile in (("major", _MAJOR), ("minor", _MINOR)):
            r = float(np.corrcoef(hist, np.roll(profile, tonic))[0, 1])
            if np.isnan(r):
                r = -1.0
            if tonic == last_pc:
                r += _TONIC_END_BONUS
            scored.append((r, tonic, mode))
    scored.sort(reverse=True)
    best, second = scored[0], scored[1]
    # Confidence from how far ahead the winner is of the runner-up.
    confidence = float(np.clip((best[0] - second[0]) / 0.15, 0.0, 1.0)) * float(np.clip(best[0] / 0.7, 0.0, 1.0))
    return NOTE_NAMES[best[1]], best[2], confidence


# ─── Musical cleanup ─────────────────────────

def _nearest_scale_pc(pc: int, scale_pcs: set[int]) -> int:
    best = min(scale_pcs, key=lambda c: min((c - pc) % 12, (pc - c) % 12))
    return best


def clean_up(
    notes: list[RawNote], tonic_pc: int, mode: str, key_confidence: float
) -> tuple[list[RawNote], dict]:
    """
    Turn what was detected into what a person would play. A pianist hearing a hum would not copy
    every wobble: they would keep the tune, put notes where they belong, and drop the flutter.

    1. Octave glitches: a brief note an octave away from both neighbours is moved an octave.
    2. Rare wobble: a note name sung hardly at all, right next to one sung a lot, is that note.
    3. Brief out-of-key notes are moved to the nearest note of the key (only when the key is confident).
    4. Tiny ornaments next to a neighbouring note are absorbed into it.
    Returns (cleaned notes, report of what changed). Never adds notes; never reorders them.
    """
    work = [replace(n) for n in notes]
    report = {"octave_fixed": 0, "wobble_snapped": 0, "out_of_key_snapped": 0, "ornaments_merged": 0}
    if not work:
        return work, report

    # 1. octave glitches. A pitch tracker sometimes hears a note an octave away. A brief note, or
    #    any note sitting an octave away from BOTH neighbours when those neighbours are close to
    #    each other, is moved back. (A real tune rarely dips an octave for one note and returns.)
    ref = [n.midi for n in work]
    for i, n in enumerate(work):
        neighbours = [ref[j] for j in (i - 1, i + 1) if 0 <= j < len(work)]
        brief = (n.end_s - n.start_s) < OCTAVE_FIX_MAX_S
        tight_context = len(neighbours) == 2 and abs(neighbours[0] - neighbours[1]) <= OCTAVE_CONTEXT_SPREAD
        if neighbours and (brief or tight_context):
            mean = float(np.mean(neighbours))
            if abs(n.midi - mean) >= 10:
                for shift in (12, -12):
                    if abs(n.midi + shift - mean) <= 5:
                        n.midi += shift
                        report["octave_fixed"] += 1
                        break

    # 2. rare wobble notes
    total = sum(n.end_s - n.start_s for n in work) or 1.0
    share = np.zeros(12)
    for n in work:
        share[n.midi % 12] += (n.end_s - n.start_s) / total
    for n in work:
        pc = n.midi % 12
        if share[pc] < RARE_SHARE:
            options = [(share[(pc + d) % 12], d) for d in (-1, 1) if share[(pc + d) % 12] >= STRONG_SHARE]
            if options:
                n.midi += max(options)[1]
                report["wobble_snapped"] += 1

    # 3. brief out-of-key notes
    if key_confidence >= CONFIDENT:
        scale = {(tonic_pc + i) % 12 for i in (MAJOR_SCALE if mode == "major" else MINOR_SCALE)}
        for n in work:
            if n.midi % 12 not in scale and (n.end_s - n.start_s) < SHORT_OUT_OF_KEY_S:
                target = _nearest_scale_pc(n.midi % 12, scale)
                n.midi += ((target - n.midi % 12 + 6) % 12) - 6
                report["out_of_key_snapped"] += 1

    # 4. ornaments (what counts as tiny depends on how quickly this person hums)
    typical = float(np.median([n.end_s - n.start_s for n in work]))
    ornament_s = float(np.clip(ORNAMENT_SHARE_OF_TYPICAL * typical, ORNAMENT_MIN_S, ORNAMENT_S))
    i = 0
    while i < len(work):
        n = work[i]
        if (n.end_s - n.start_s) < ornament_s and len(work) > 1:
            prev = work[i - 1] if i > 0 else None
            nxt = work[i + 1] if i + 1 < len(work) else None
            if prev is not None and abs(n.midi - prev.midi) <= 2:
                prev.end_s = max(prev.end_s, n.end_s)
            elif nxt is not None and abs(n.midi - nxt.midi) <= 2:
                nxt.start_s = min(nxt.start_s, n.start_s)
            else:
                i += 1
                continue
            del work[i]
            report["ornaments_merged"] += 1
            continue
        i += 1

    return work, report


# ─── Fit (does the sketch explain the hum?) ──

def fit_score(midi: np.ndarray, times: np.ndarray, notes: list[RawNote]) -> float:
    """Share of sung frames that sit within a semitone of the note covering them."""
    valid = np.where(~np.isnan(midi))[0]
    if valid.size == 0 or not notes:
        return 0.0
    starts = np.array([n.start_s for n in notes])
    ends = np.array([n.end_s for n in notes])
    pitches = np.array([n.midi for n in notes], dtype=float)
    hit = 0
    for i in valid:
        t = times[i]
        j = np.searchsorted(starts, t, side="right") - 1
        if j >= 0 and t <= ends[j] and abs(midi[i] - pitches[j]) <= 1.0:
            hit += 1
    return hit / valid.size


# ─── Quality gate ────────────────────────────

def quality_problem(voiced_seconds: float, mean_prob: float, notes: list[RawNote]) -> Optional[str]:
    """A plain-language reason to ask for another recording, or None when it is fine."""
    if voiced_seconds < MIN_VOICED_SECONDS or len(notes) < MIN_NOTES:
        return "I didn't catch enough of a tune that time. Want to hum a little longer? Staying close to the microphone helps."
    if mean_prob < MIN_MEAN_VOICED_PROB:
        return "I picked up a lot of other sound along with your hum. A quieter spot might help me hear you better."
    pitches = [n.midi for n in notes]
    leaps = np.abs(np.diff(pitches)) if len(pitches) > 1 else np.array([0.0])
    if float(np.median(leaps)) > MAX_MEDIAN_LEAP or (max(pitches) - min(pitches)) > MAX_RANGE:
        return "I couldn't pick out a single tune in that one. Want to try humming it once more, just the melody?"
    return None


# ─── Public entry ────────────────────────────

def extract_melody(audio_bytes: bytes, ext: str = "wav", source_audio: Optional[str] = None) -> MelodyExtraction:
    y = decode_mono(audio_bytes, ext)
    if y.size < SR:  # under a second
        return MelodyExtraction(False, "That one was over before I could catch a tune. Want to try again? Take as long as you like.")

    if y.size > MAX_HUM_SECONDS * SR:
        return MelodyExtraction(
            False,
            "That's a long one. A minute or less is plenty for me to catch a tune. Want to hum just a part of it?",
        )
    midi, prob, times = track_pitch(y)
    notes = segment_notes(midi, times, track_energy(y))
    voiced_mask = ~np.isnan(midi)
    voiced_seconds = float(voiced_mask.sum() * HOP_S)
    mean_prob = float(prob[voiced_mask].mean()) if voiced_mask.any() else 0.0

    diagnostics = {
        "voiced_seconds": round(voiced_seconds, 2),
        "mean_voiced_prob": round(mean_prob, 2),
        "raw_note_count": len(notes),
    }
    problem = quality_problem(voiced_seconds, mean_prob, notes)
    if problem:
        return MelodyExtraction(False, problem, None, diagnostics)

    tuning_offset = apply_tuning(notes)
    diagnostics["tuning_offset_notes"] = round(tuning_offset, 2)
    fit_before = fit_score(midi, times, notes)

    key, mode, key_conf = estimate_key(notes)
    notes, cleanup_report = clean_up(notes, NOTE_NAMES.index(key), mode, key_conf)
    diagnostics["cleanup"] = cleanup_report
    if len(notes) < MIN_NOTES:
        return MelodyExtraction(False, quality_problem(0.0, 1.0, notes), None, diagnostics)

    onsets = np.array([n.start_s for n in notes])
    bpm, tempo_conf, phase = estimate_tempo(onsets)
    fit = fit_score(midi, times, notes)

    if bpm is None:
        # Too little timing to find a speed. Report that honestly with zero confidence;
        # the notes use a neutral speed only so they can be written down and played back.
        bpm, tempo_conf, phase = 90.0, 0.0, float(notes[0].start_s)
        diagnostics["tempo_note"] = "not enough timing to estimate; neutral speed used with zero confidence"

    # Loose timing is not forced onto a fine grid: when the speed is uncertain, use eighths.
    grid = GRID_BEATS if tempo_conf >= CONFIDENT else COARSE_GRID_BEATS
    melody_notes = quantise(notes, bpm, phase, grid)
    sketch = MelodySketch(
        notes=melody_notes,
        performed_notes=performed_notes(notes, bpm),
        tempo_bpm=bpm,
        tempo_confidence=round(tempo_conf, 2),
        key=f"{key} {mode}",
        mode=mode,
        key_confidence=round(key_conf, 2),
        grid=grid,
        source_audio=source_audio,
        confirmed=False,
        fit=round(fit, 2),
    )
    diagnostics["note_count"] = len(melody_notes)
    diagnostics["fit_before_cleanup"] = round(fit_before, 2)
    return MelodyExtraction(True, None, sketch, diagnostics, notes)


# ─── Plain-language description ──────────────

def describe_melody(sketch: MelodySketch) -> str:
    """Say what was heard without any music terms."""
    pitches = [n.pitch_midi for n in sketch.notes]
    if not pitches:
        return "I couldn't catch a tune in that one."
    third = max(1, len(pitches) // 3)
    start_avg = float(np.mean(pitches[:third]))
    end_avg = float(np.mean(pitches[-third:]))
    span = max(pitches) - min(pitches)
    total_beats = sketch.notes[-1].start_beat + sketch.notes[-1].dur_beats
    seconds = max(total_beats * 60.0 / sketch.tempo_bpm, 1.0)
    per_second = len(pitches) / seconds   # notes per real second, so it does not depend on the tempo guess

    if end_avg - start_avg > 2:
        shape = "that climbs as it goes"
    elif start_avg - end_avg > 2:
        shape = "that settles lower as it goes"
    elif span > 9:
        shape = "that wanders around and comes back"
    else:
        shape = "that stays around the same place"
    size = "small" if span <= 5 else ("medium-sized" if span <= 12 else "big")
    pace = "unhurried" if per_second < 1.5 else ("steady" if per_second < 2.3 else "lively")
    article = "an" if pace[0] in "aeiou" else "a"
    return f"I heard {article} {pace}, {size} tune {shape}."
