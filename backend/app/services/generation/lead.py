"""
The person's own tune as the lead of the song (song-engine spec 04, requirement 3.3).

Frank no longer invents a tune when the person has hummed one. The confirmed hum becomes the melody
of the chorus, note for note, and the chords and bass are chosen to FIT it, the way an arranger
harmonises a tune someone brings in. This module has three jobs:

  1. `from_sketch`   : turn a confirmed hum into a lead (octave placed for the song, whole bars long).
  2. `harmonize`     : pick one chord per bar that explains the tune best and moves in ways that sound
                       like a song (a best-path search over the bars, not a random progression).
  3. `lead_part`     : play the tune, repeated to fill a section, as a normal part of the song.

The tune is never altered except by whole octaves: every pitch and every start time stays what the person
sang (on the beat grid the hum was snapped to). Playing it adds only a few thousandths of a beat of human
looseness, so it does not sound mechanical. If a section is shorter than the tune, the tune is cut at a
phrase boundary and that is reported, never done silently.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, replace
from typing import Any, Optional

from app.services.generation import theory
from app.services.generation.rng import rng_for

log = logging.getLogger(__name__)
KEY_PATTERN = re.compile(r"^[A-Ga-g][#b]?(\s+\w+)?$")
LEAD_SECTIONS = ("chorus",)       # where the tune plays: the part people remember
PHRASE_BARS = (1, 2, 4, 8, 16)   # a tune is rounded up to one of these lengths
MAX_BARS = 16                    # a longer hum is cut to its first sixteen bars
MIN_NOTES = 3                    # fewer notes than this is not a tune
LOW, HIGH = 62, 76               # the middle of the tune is moved by octaves to sit in here
LEAD_PROGRAM = 54                # the "ooh" voice sound, the one the person already recognised their hum in
CAUTION = -0.6                   # score for a melody note that clashes with the chord
PASSING = 0.3                    # score for a melody note a step from a chord tone (a passing note)


@dataclass(frozen=True)
class Lead:
    """The tune: (pitch, start_beat, dur_beats) triples starting at beat 0, plus how many bars it fills."""
    notes: tuple[tuple[int, float, float], ...]
    bars: int
    key: str            # "A minor"
    source: Optional[str] = None   # id of the melody version this came from

    def to_dict(self) -> dict[str, Any]:
        return {"notes": [list(n) for n in self.notes], "bars": self.bars, "key": self.key, "source": self.source}

    @staticmethod
    def from_dict(data: Optional[dict[str, Any]]) -> Optional["Lead"]:
        if not isinstance(data, dict):
            return None
        try:
            notes = tuple((int(p), float(s), float(d)) for p, s, d in data["notes"])
            bars = int(data["bars"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        valid = (
            bars in PHRASE_BARS
            and len(notes) >= MIN_NOTES
            and all(0 <= p <= 127 and math.isfinite(s) and math.isfinite(d) and s >= 0 and d > 0 for p, s, d in notes)
        )
        if not valid:
            return None
        return Lead(notes=notes, bars=bars, key=_clean_key(str(data.get("key", ""))), source=data.get("source"))


def _clean_key(key: str) -> str:
    """A key like "A minor" or "F# major", or "" when it is not one (so the song's own key is used instead)."""
    key = key.replace("\u266d", "b").replace("\u266f", "#").strip()
    return key if KEY_PATTERN.match(key) else ""


def _key_string(key: str, mode: str) -> str:
    key = _clean_key(str(key or ""))
    if not key:
        return ""
    if " " in key:
        return key
    return f"{key} {mode}".strip() if mode else key


def from_sketch(content: dict[str, Any], source: Optional[str] = None) -> Optional[Lead]:
    """
    A lead from a confirmed melody facet. Returns None when there is no usable tune (not confirmed,
    too few notes, nothing sung). Uses the notes snapped to the beat grid, because the drums and chords
    play on that grid.
    """
    if not isinstance(content, dict) or not content.get("confirmed"):
        return None
    raw = content.get("notes") or []
    notes: list[tuple[int, float, float]] = []
    for n in raw:
        try:
            pitch, start, dur = int(n["pitch_midi"]), float(n["start_beat"]), float(n["dur_beats"])
        except (KeyError, TypeError, ValueError, OverflowError):      # OverflowError: an infinite pitch
            continue
        if start < 0 or dur <= 0 or not (0 <= pitch <= 127) or not math.isfinite(start + dur):
            continue
        notes.append((pitch, start, dur))
    if len(notes) < MIN_NOTES:
        return None
    notes.sort(key=lambda n: (n[1], n[0]))

    limit = MAX_BARS * 4.0
    notes = [(p, s, min(d, limit - s)) for p, s, d in notes if s < limit]
    if len(notes) < MIN_NOTES:
        return None
    end = max(s + d for _, s, d in notes)
    needed = max(1, min(MAX_BARS, math.ceil(end / 4.0 - 1e-9)))
    bars = next(b for b in PHRASE_BARS if b >= needed)       # a whole phrase, so repeats line up with the chords

    # Move the whole tune by octaves so its middle sits where a lead belongs in the song.
    middle = sorted(p for p, _, _ in notes)[len(notes) // 2]
    shift = 0
    while middle + shift > HIGH:
        shift -= 12
    while middle + shift < LOW:
        shift += 12
    # Never leave the playable range: step back by whole octaves instead of bending any pitch.
    lowest, highest = min(p for p, _, _ in notes), max(p for p, _, _ in notes)
    while highest + shift > 127:
        shift -= 12
    while lowest + shift < 0:
        shift += 12
    if highest + shift > 127 or lowest + shift < 0:
        shift = 0                                            # an enormous range: leave it as sung
    shifted = tuple((p + shift, s, d) for p, s, d in notes)
    return Lead(notes=shifted, bars=bars, key=_key_string(str(content.get("key", "")), str(content.get("mode", ""))), source=source)


# ─────────────────────────────────────────────
# Harmony: choose the chords that fit the tune
# ─────────────────────────────────────────────

def _chord_pcs(root: int, mode: str, degree: int, seventh: bool) -> list[int]:
    return sorted({n % 12 for n in theory.chord_for_degree(root, mode, degree, 3, seventh)})


def _is_diminished(pcs: list[int], root_pc: int) -> bool:
    return (root_pc + 3) % 12 in pcs and (root_pc + 6) % 12 in pcs


def _bar_weights(lead: Lead, bar: int) -> list[tuple[int, float]]:
    """(pitch class, weight) of every tune note in this bar. Longer notes and notes on strong beats count more."""
    lo, hi = bar * 4.0, bar * 4.0 + 4.0
    out: list[tuple[int, float]] = []
    for pitch, start, dur in lead.notes:
        a, b = max(start, lo), min(start + dur, hi)
        if b <= a:
            continue
        weight = b - a
        if lo <= start < hi:
            beat = start - lo
            if min(abs(beat), abs(beat - 2.0)) < 0.01:
                weight *= 1.6                      # lands on a strong beat
        out.append((pitch % 12, weight))
    return out


def _fit(weights: list[tuple[int, float]], pcs: list[int], scale_pcs: set[int]) -> float:
    """How well one chord explains the tune notes of one bar: -1 (clashes with everything) to +1."""
    total = sum(w for _, w in weights)
    if total <= 0:
        return 0.0
    score = 0.0
    for pc, w in weights:
        if pc in pcs:
            score += w
        elif any(((pc + d) % 12) in pcs for d in (-2, -1, 1, 2)) and pc in scale_pcs:
            score += w * PASSING
        else:
            score += w * CAUTION
    return score / total


def _move(prev_degree: int, degree: int) -> float:
    """How natural it is to go from one chord to the next (by steps of the scale)."""
    step = (degree - prev_degree) % 7
    if step == 0:
        return -0.04          # staying put is allowed
    if step == 3:
        return 0.16           # up a fourth: the strongest, most settled motion
    if step == 4:
        return 0.12           # down a fourth or up a fifth
    if step in (1, 6):
        return 0.08
    if step in (2, 5):
        return 0.05
    return 0.0


def harmonize(lead: Lead, key: str, extension: float = 0.0) -> dict:
    """
    One chord per bar for the whole length of the tune, in the format the composer expects (the same
    keys `theory.build_progression` returns). `key` is the song's key; the tune is already in it.
    The chord for each bar is found by a best-path search: every bar's chord must explain the tune notes in
    that bar, and the path as a whole must move like a real song and start and end settled.
    """
    root, mode = theory.parse_key(key)
    scale_pcs = {(root + i) % 12 for i in theory.SCALE_INTERVALS[mode]}
    bars = lead.bars

    # Candidates for each bar: the seven chords of the key, and their seventh versions when the style asks.
    candidates: list[tuple[int, bool, list[int]]] = []
    for degree in range(7):
        for seventh in ((False, True) if extension >= 0.3 else (False,)):
            pcs = _chord_pcs(root, mode, degree, seventh)
            candidates.append((degree, seventh, pcs))

    weights_by_bar = [_bar_weights(lead, b) for b in range(bars)]

    def own(bar: int, cand: tuple[int, bool, list[int]]) -> float:
        degree, seventh, pcs = cand
        root_pc = (root + theory.SCALE_INTERVALS[mode][degree]) % 12
        score = _fit(weights_by_bar[bar], pcs, scale_pcs)
        if _is_diminished(pcs, root_pc):
            score -= 0.4
        if seventh:
            score -= 0.12
        if bar == 0 and degree == 0:
            score += 0.12
        if bar == bars - 1 and degree in (0, 4):
            score += 0.12
        return score

    # best[bar][i] = (best score of any path ending in candidate i at this bar, which candidate came before)
    best: list[list[tuple[float, int]]] = []
    for bar in range(bars):
        row: list[tuple[float, int]] = []
        for i, cand in enumerate(candidates):
            here = own(bar, cand)
            if bar == 0:
                row.append((here, -1))
                continue
            prev_scores = [(best[bar - 1][j][0] + _move(candidates[j][0], cand[0]), j) for j in range(len(candidates))]
            top, j = max(prev_scores, key=lambda t: (t[0], -t[1]))
            row.append((here + top, j))
        best.append(row)

    last = max(range(len(candidates)), key=lambda i: (best[-1][i][0], -i))
    path = [last]
    for bar in range(bars - 1, 0, -1):
        path.append(best[bar][path[-1]][1])
    path.reverse()

    degrees = [candidates[i][0] for i in path]
    sevenths = [candidates[i][1] for i in path]
    return progression_from_degrees(key, degrees, sevenths)


def progression_from_degrees(key: str, degrees: list[int], sevenths: list[bool], family: str = "from_tune") -> dict:
    """The composer's progression format from one chord (scale step, seventh or not) per bar."""
    root, mode = theory.parse_key(key)
    raw = [theory.chord_for_degree(root, mode, d, 3, s) for d, s in zip(degrees, sevenths)]
    chords = theory.voice_lead(raw)
    return {
        "root": root,
        "mode": mode,
        "family": family,
        "degrees": degrees,
        "chords": chords,
        "chord_pcs": [sorted({n % 12 for n in c}) for c in chords],
        "tones": [[n % 12 for n in c] for c in raw],
        "sevenths": sevenths,
        "scale": theory.scale_notes(root, mode, 4),
        "bass_notes": [theory.triad_for_degree(root, mode, d, octave=2)[0] for d in degrees],
    }


def coverage(lead: Lead, progression: dict) -> float:
    """The share of the tune (by weight) that sits inside the chord playing under it. 1.0 means every note fits."""
    inside = total = 0.0
    chords = progression["chord_pcs"]
    for bar in range(lead.bars):
        pcs = chords[bar % len(chords)]
        for pc, w in _bar_weights(lead, bar):
            total += w
            if pc in pcs:
                inside += w
    return inside / total if total else 1.0


# ─────────────────────────────────────────────
# The tune as a part of the song
# ─────────────────────────────────────────────

def lead_events(lead: Lead, bars: int, energy: float, seed: int, index: int):
    """
    The tune played over `bars` bars of a section, repeated from the start as many times as it fits.
    A repeat that does not fit completely is cut at the end of the section. Same tune every time.
    """
    from app.services.generation.composer import GAP, NoteEvent, _vel

    rng = rng_for(seed, index, "lead")
    end = bars * 4.0
    events: list[NoteEvent] = []
    round_ = 0
    while round_ * lead.bars < bars:
        offset = round_ * lead.bars * 4.0
        for pitch, start, dur in lead.notes:
            s = offset + start
            if s >= end:
                continue
            length = min(dur * 0.94, end - s - GAP)
            if length <= 0.05:
                continue
            events.append(NoteEvent(pitch, max(0.0, s + rng.uniform(-0.006, 0.006)), length, _vel(rng, 72 + energy * 24 + min(dur * 6, 12), 4)))
        round_ += 1
    return events


# ─────────────────────────────────────────────
# Fitting the tune to the song
# ─────────────────────────────────────────────

def fit_to(lead: Lead, bars: int) -> Lead:
    """
    The tune shortened to the longest whole phrase that fits in `bars` bars, cut at a phrase boundary. A tune
    that already fits is returned as it is. Used only when a section is shorter than the tune.
    """
    if bars >= lead.bars:
        return lead
    target = max((b for b in PHRASE_BARS if b <= max(1, bars)), default=1)
    limit = target * 4.0
    notes = tuple((p, s, min(d, limit - s)) for p, s, d in lead.notes if s < limit)
    if len(notes) < MIN_NOTES:
        return lead                      # too little would be left to be a tune: keep it whole
    return replace(lead, notes=notes, bars=target)


def scale_fit(lead: Lead, key: str) -> float:
    """The share of the tune (by length) that sits inside the scale of `key`: 1.0 means every note is in the key."""
    root, mode = theory.parse_key(key)
    scale = {(root + i) % 12 for i in theory.SCALE_INTERVALS[mode]}
    total = sum(d for _, _, d in lead.notes)
    inside = sum(d for p, _, d in lead.notes if p % 12 in scale)
    return inside / total if total else 1.0


def choose_key(lead: Lead, settled: Optional[str]) -> tuple[str, bool]:
    """
    Which key the song is in when there is a tune. A key that was already settled stays, as long as the tune
    fits it nearly as well as the key found in the hum (the hum's mode is only a guess from a few notes, and
    a tune fits a key and its relative key equally well). The hum's key wins only when the settled key clearly
    does not suit the tune. Returns (key, changed_from_settled).
    """
    hum = lead.key or (settled or "")
    if not settled:
        return hum, False
    if not lead.key or theory.parse_key(settled) == theory.parse_key(lead.key):
        return settled, False
    if scale_fit(lead, settled) >= scale_fit(lead, lead.key) - 0.05:
        return settled, False
    return lead.key, True
