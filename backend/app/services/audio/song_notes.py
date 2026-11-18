"""
The song's own notes at any moment (sing-it spec 06, design "Song targets").

Recomposed from the active beat version's plan (deterministic, no storage): which notes belong to the song (the
scale), which chord is playing, and which note the tune plays. Tuning, harmony, the guide and phrase scoring all
read from this, so the singer is measured against THEIR song, not against all twelve notes.
Times are seconds from the start of the song (takes are placed in song time when they are uploaded).
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.generation import beat as beat_engine
from app.services.generation import composer, theory
from app.services.generation.renderer import SAMPLE_RATE

ALL_NOTES = frozenset(range(12))


@dataclass(frozen=True)
class Span:
    start: float
    end: float
    value: Any


@dataclass(frozen=True)
class Target:
    scale: frozenset[int]                # pitch classes of the song's notes
    chord: Optional[frozenset[int]]      # pitch classes of the chord playing now
    melody: Optional[int]                # MIDI note the tune plays now
    section: Optional[int]               # index of the section playing now


@dataclass
class SongNotes:
    scale: frozenset[int] = ALL_NOTES
    bpm: float = 90.0
    sections: list[Span] = field(default_factory=list)   # value: (index, name)
    chords: list[Span] = field(default_factory=list)     # value: frozenset of pitch classes
    melody: list[Span] = field(default_factory=list)     # value: MIDI note
    melody_part: list[tuple[int, list[composer.NoteEvent], int]] = field(default_factory=list)  # (section idx, events, preset)

    def _find(self, spans: list[Span], t: float) -> Optional[Span]:
        i = bisect_right([s.start for s in spans], t) - 1
        if 0 <= i < len(spans) and spans[i].start <= t < spans[i].end:
            return spans[i]
        return None

    def at(self, t: float) -> Target:
        c, m, s = self._find(self.chords, t), self._find(self.melody, t), self._find(self.sections, t)
        return Target(self.scale, c.value if c else None, m.value if m else None, s.value[0] if s else None)

    def section_name(self, index: Optional[int]) -> Optional[str]:
        for s in self.sections:
            if s.value[0] == index:
                return s.value[1]
        return None

    def section_at(self, t: float) -> Optional[int]:
        s = self._find(self.sections, t)
        return s.value[0] if s else None

    @property
    def has_melody(self) -> bool:
        return bool(self.melody)

    @property
    def seconds_per_beat(self) -> float:
        return 60.0 / self.bpm


def scale_of(key: Optional[str]) -> frozenset[int]:
    if not key:
        return ALL_NOTES
    try:
        root, mode = theory.parse_key(key)
    except Exception:  # noqa: BLE001  an unreadable key leaves every note allowed
        return ALL_NOTES
    return frozenset((root + i) % 12 for i in theory.SCALE_INTERVALS.get(mode, theory.SCALE_INTERVALS["minor"]))


def from_plan(sections: list[beat_engine.SectionPlan], fp: dict, seed: int, lead: Any = None) -> SongNotes:
    bpm = float(fp.get("tempo_bpm", 90))
    spb = 60.0 / bpm
    _, contexts, progressions = beat_engine.plan_contexts(sections, fp, seed, lead)
    spans = beat_engine.section_spans(sections, bpm)
    out = SongNotes(scale=scale_of(fp.get("key")), bpm=bpm)
    for s, ctx, (a, b) in zip(sections, contexts, spans):
        start, end = a / SAMPLE_RATE, b / SAMPLE_RATE
        out.sections.append(Span(start, end, (s.index, s.name)))
        prog = progressions[s.name]
        chords = prog["chords"]
        for bar in range(s.bars):
            pcs = frozenset(n % 12 for n in chords[bar % len(chords)])
            out.chords.append(Span(start + bar * 4 * spb, min(end, start + (bar + 1) * 4 * spb), pcs))
        parts = composer.compose_section(s.name, prog, s.bars, s.energy, s.density, layers=s.layers, ctx=ctx)
        tune = next((p for p in parts if p.name == "melody" and p.events), None)
        if tune is not None:
            events = sorted(tune.events, key=lambda e: e.start)
            out.melody_part.append((s.index, events, tune.preset))
            for e in events:
                out.melody.append(Span(start + e.start * spb, min(end, start + (e.start + e.duration) * spb), int(e.note)))
    out.melody.sort(key=lambda x: x.start)
    return out


def from_fingerprint(fp: Optional[dict]) -> SongNotes:
    """No beat yet: the song's notes come from its feeling's key alone (or every note when there is none)."""
    fp = fp or {}
    return SongNotes(scale=scale_of(fp.get("key")), bpm=float(fp.get("tempo_bpm", 90) or 90))


async def for_project(project_id: str) -> SongNotes:
    """The active beat's notes, or the fingerprint's key when there is no beat. Never raises."""
    from app.db import beat as beat_db
    from app.db import feel as feel_db
    from app.db import projects as projects_db

    try:
        state = await projects_db.get_project_active_state(project_id) or {}
        vid = state.get("active_beat_version_id")
        if vid:
            v = await beat_db.get_beat_version(vid)
            params = (v or {}).get("params") or {}
            if params.get("sections"):
                sections, fp = beat_engine.sections_from_params(params)
                seed = params.get("seed")
                seed = seed if isinstance(seed, int) else beat_engine.default_seed(fp)
                return from_plan(sections, fp, seed, beat_engine.lead_from_params(params))
        latest = await feel_db.get_latest_fingerprint(project_id)
        return from_fingerprint((latest or {}).get("fingerprint") if isinstance(latest, dict) else None)
    except Exception:  # noqa: BLE001  the voice tools still work against every note
        return SongNotes()


def nearest_in(note: float, pcs: frozenset[int]) -> int:
    """The nearest MIDI note whose pitch class is in `pcs` (ties go down)."""
    base = int(round(note))
    for d in sorted(range(-6, 7), key=lambda x: (abs(base + x - note), x)):
        if (base + d) % 12 in pcs:
            return base + d
    return base


def target_note(sung: float, t: Target) -> int:
    """
    Where a sung note should go (requirement 2.1). The nearest note stays the target when it belongs to the song
    (or is the tune's note). Only a note that does not belong moves one step, to the neighbour that does,
    preferring the tune's note.
    Decision (Nov 18, measured on the founder's real hums): the spec's "within two steps of the tune" pulled
    notes up to 1.8 steps onto the engine's tune, which rewrites the person's own melody instead of tuning it.
    Tuning now never moves a note further than its neighbour.
    """
    r = int(round(sung))
    tune_pc = t.melody % 12 if t.melody is not None else None
    if r % 12 in t.scale or r % 12 == tune_pc:
        return r
    nearby = [n for n in (r - 1, r + 1) if n % 12 in t.scale or n % 12 == tune_pc]
    if not nearby:
        return nearest_in(sung, t.scale)
    return min(nearby, key=lambda n: (n % 12 != tune_pc, abs(n - sung)))
