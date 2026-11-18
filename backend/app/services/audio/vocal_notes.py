"""
Sung notes and phrases from a take (sing-it spec 06): one pyin pass, shared by tuning, harmony, comp and the
recording engineer. A note is a run of voiced frames that stays near one pitch; a phrase is a run of notes
between breaths (a gap of more than PHRASE_GAP seconds).
"""
from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

PITCH_SR = 16000
HOP = 256                    # 16 ms at 16 kHz: fine enough to find where a note starts
FRAME = 2048
FMIN, FMAX = 70.0, 1000.0
MIN_VOICED_PROB = 0.35
NOTE_JUMP = 0.7              # semitones: a bigger move starts a new note
MIN_NOTE_S = 0.09
PHRASE_GAP = 0.25
ABSOLUTE_FLOOR_DB = -55.0            # seconds of silence that count as a breath (design "Phrase split")


@dataclass
class SungNote:
    start: float             # seconds
    end: float
    centre: float            # MIDI, median of the middle 60 %
    frames: np.ndarray       # MIDI per frame (nan where unvoiced)
    confidence: float

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass
class Phrase:
    index: int
    start: float
    end: float
    notes: list[SungNote]


def contour(mono: np.ndarray, sr: int, hop: int = HOP) -> tuple[np.ndarray, np.ndarray, float]:
    """(midi per frame with nan when unvoiced, voiced probability, seconds per frame). A bigger hop is faster."""
    y = librosa.resample(mono.astype(np.float32), orig_sr=sr, target_sr=PITCH_SR) if sr != PITCH_SR else mono.astype(np.float32)
    if y.size < FRAME:
        return np.zeros(0), np.zeros(0), hop / PITCH_SR
    f0, _, prob = librosa.pyin(y, fmin=FMIN, fmax=FMAX, sr=PITCH_SR, hop_length=hop, frame_length=FRAME)
    midi = librosa.hz_to_midi(np.where(np.isnan(f0), np.nan, f0))
    midi = np.where(prob >= MIN_VOICED_PROB, midi, np.nan)
    return midi, prob, hop / PITCH_SR


def notes_from_contour(midi: np.ndarray, prob: np.ndarray, step: float) -> list[SungNote]:
    notes: list[SungNote] = []
    i, n = 0, len(midi)
    while i < n:
        if np.isnan(midi[i]):
            i += 1
            continue
        j = i + 1
        while j < n and not np.isnan(midi[j]):
            # a note follows the singer's slide; a clear jump away from its running middle starts the next one
            run = np.nanmedian(midi[max(i, j - 6):j])
            if abs(midi[j] - run) > NOTE_JUMP:
                break
            j += 1
        frames = midi[i:j]
        if (j - i) * step >= MIN_NOTE_S:
            k = len(frames)
            mid = frames[int(k * 0.2): max(int(k * 0.2) + 1, int(k * 0.8))]
            notes.append(SungNote(i * step, j * step, float(np.nanmedian(mid)), frames.copy(),
                                  float(np.nanmean(prob[i:j])) if prob.size else 0.0))
        i = j
    return notes


def sung_notes(mono: np.ndarray, sr: int) -> list[SungNote]:
    midi, prob, step = contour(mono, sr)
    return notes_from_contour(midi, prob, step)


def phrases(notes: list[SungNote], gap: float = PHRASE_GAP) -> list[Phrase]:
    out: list[Phrase] = []
    for note in notes:
        if out and note.start - out[-1].end <= gap:
            out[-1].notes.append(note)
            out[-1].end = note.end
        else:
            out.append(Phrase(len(out), note.start, note.end, [note]))
    return out


def phrases_from_energy(mono: np.ndarray, sr: int, gap: float = PHRASE_GAP, floor_db: float = -45.0) -> list[tuple[float, float]]:
    """Phrase boundaries from loudness alone (for takes where the pitch line is thin, like whispered words)."""
    hop = int(0.01 * sr)
    if mono.size < hop * 4:
        return []
    rms = librosa.feature.rms(y=mono.astype(np.float32), frame_length=hop * 4, hop_length=hop)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-9) / max(float(rms.max()), 1e-9))
    on = (db > floor_db) & (rms > 10 ** (ABSOLUTE_FLOOR_DB / 20))     # quiet hiss alone is never a phrase
    spans: list[tuple[float, float]] = []
    start = None
    quiet = 0
    for k, v in enumerate(on):
        if v:
            if start is None:
                start = k
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * hop / sr > gap:
                spans.append((start * hop / sr, (k - quiet + 1) * hop / sr))
                start, quiet = None, 0
    if start is not None:
        spans.append((start * hop / sr, (len(on) - quiet) * hop / sr))
    return [(a, b) for a, b in spans if b - a > 0.15]
