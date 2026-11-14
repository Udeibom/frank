"""
Touches: turns the planned moments (moments.py) into notes (song-engine spec 04).

Applied to the parts of one section after they are composed. A touch can take notes away (a bar where
the drums drop out, a beat of silence), add a new part (a riser, a one-time bell, an answer to the
tune), change a part's sound (a different instrument in the bridge), or replace the last bar with a
proper ending. Every note it adds is a note of the chord playing at that moment.
"""

from __future__ import annotations

from typing import Optional

from app.services.generation import theory
from app.services.generation.composer import CRASH, GAP, KICK, NoteEvent, Part, SectionContext, _scale_pool, _vel
from app.services.generation.moments import REVERSE_CYMBAL, RISER_PROGRAM, Moment
from app.services.generation.rng import rng_for

ORDER = ["late_entry", "dropout", "swap_voice", "answer", "one_off", "stop", "riser", "ending"]


def _remove(part: Part, lo: float, hi: float) -> None:
    """Take out the notes that start in [lo, hi), and shorten notes that would ring into it."""
    kept: list[NoteEvent] = []
    for e in part.events:
        if lo <= e.start < hi:
            continue
        if not part.is_drums and e.start < lo < e.start + e.duration:
            e.duration = max(0.05, lo - e.start - GAP)
        kept.append(e)
    part.events = kept


def _chord_at(progression: dict, bar: int) -> list[int]:
    chords = progression["chords"]
    return chords[bar % len(chords)]


def _answer(part_by_name: dict[str, Part], progression: dict, bars: int, m: Moment, ctx: SectionContext) -> Optional[Part]:
    """Short replies in the gaps of the tune: two chord tones, no more than one reply every two bars."""
    melody = part_by_name.get("melody")
    if melody is None or not melody.events:
        return None
    rng = rng_for(ctx.seed, ctx.index, "answer")
    events = sorted(melody.events, key=lambda e: e.start)
    pool = _scale_pool(progression, 70, 92)
    out = Part("color", m.program, False)
    last_bar = -9
    for k, e in enumerate(events):
        end = e.start + e.duration
        nxt = events[k + 1].start if k + 1 < len(events) else bars * 4.0
        gap = nxt - end
        bar = int(end // 4)
        if gap < 1.6 or bar - last_bar < 2 or bar >= bars or rng.random() < 0.35:
            continue
        pcs = {n % 12 for n in _chord_at(progression, bar)}
        tones = [n for n in pool if n % 12 in pcs and n > e.note]
        if len(tones) < 2:
            continue
        start = end + 0.25
        a, b = tones[0], tones[1]
        if start + 1.2 >= nxt - GAP:
            continue
        out.events.append(NoteEvent(b, start, 0.5, _vel(rng, 68, 4)))
        out.events.append(NoteEvent(a, start + 0.5, min(1.0, nxt - GAP - start - 0.5), _vel(rng, 62, 4)))
        last_bar = bar
    return out if out.events else None


def _riser(bars: int, progression: dict, has_stop: bool, ctx: SectionContext) -> list[Part]:
    """A climbing run on the last bar plus a reversed cymbal swell, building toward what comes next."""
    end = bars * 4.0
    stop_at = end - (1.0 if has_stop else 0.2)
    pool = _scale_pool(progression, 60, 84)
    pcs = {n % 12 for n in _chord_at(progression, bars - 1)}
    start_idx = next((i for i, n in enumerate(pool) if n % 12 in pcs), 0)
    run = Part("riser", RISER_PROGRAM, False)
    rng = rng_for(ctx.seed, ctx.index, "riser")
    steps = 8
    for j in range(steps):
        t = end - 4.0 + j * 0.5
        if t + 0.45 > stop_at:
            break
        idx = min(len(pool) - 1, start_idx + j)
        run.events.append(NoteEvent(pool[idx], t, 0.45, _vel(rng, 50 + 7 * j, 3)))
    sweep = Part("sweep", REVERSE_CYMBAL, False)
    sweep.events.append(NoteEvent(60, max(0.0, end - 3.0), max(0.5, stop_at - (end - 3.0)), 76))
    return [p for p in (run, sweep) if p.events]


def _ending(parts: list[Part], progression: dict, bars: int, ctx: SectionContext) -> list[Part]:
    """The last bar becomes one held chord on the home note with a crash. The bar before loses its drums."""
    end = bars * 4.0
    lo = end - 4.0
    for p in parts:
        _remove(p, lo, end)
        if p.is_drums and bars >= 3:
            _remove(p, lo - 4.0, lo)
    home = theory.chord_for_degree(progression["root"], progression["mode"], 0, 3)
    keys = Part("finale_keys", ctx.style.instruments["keys"], False)
    pad = Part("finale_pad", ctx.style.instruments["strings"], False)
    bass = Part("finale_bass", ctx.style.instruments["bass"], False)
    drums = Part("finale_drums", 0, True)
    for n in home:
        keys.events.append(NoteEvent(n, lo, 3.9, 78))
        pad.events.append(NoteEvent(n + 12, lo, 3.95, 56))
    bass.events.append(NoteEvent(home[0] - 12, lo, 3.9, 84))
    drums.events.append(NoteEvent(CRASH, lo, 2.0, 92))
    drums.events.append(NoteEvent(KICK, lo, 0.3, 96))
    return [keys, pad, bass, drums]


def apply_moments(parts: list[Part], moments: list[Moment], progression: dict, bars: int, ctx: SectionContext) -> list[Part]:
    """Apply a section's moments to its composed parts. Returns the new list of parts."""
    if not moments:
        return parts
    by = {p.name: p for p in parts}
    out = list(parts)
    has_stop = any(m.kind == "stop" for m in moments)
    end = bars * 4.0
    for m in sorted(moments, key=lambda m: ORDER.index(m.kind) if m.kind in ORDER else 99):
        if m.kind == "late_entry":
            for name in m.parts:
                if name in by:
                    _remove(by[name], 0.0, m.bar * 4.0)
        elif m.kind == "dropout" and m.bar < bars:
            for name in m.parts:
                if name in by:
                    _remove(by[name], m.bar * 4.0, (m.bar + m.bars) * 4.0)
        elif m.kind == "swap_voice":
            for name in m.parts:
                if name in by and not by[name].is_drums:
                    by[name].preset = m.program
        elif m.kind == "answer":
            extra = _answer(by, progression, bars, m, ctx)
            if extra:
                out.append(extra)
        elif m.kind == "one_off":
            pcs = _chord_at(progression, 0)
            note = max(n for n in pcs) + 24
            bell = Part("color_once", m.program, False)
            bell.events.append(NoteEvent(note, 0.0, 3.9, 72))
            out.append(bell)
        elif m.kind == "stop":
            for p in out:
                _remove(p, end - 1.0, end)
        elif m.kind == "riser":
            out.extend(_riser(bars, progression, has_stop, ctx))
        elif m.kind == "ending":
            out.extend(_ending(out, progression, bars, ctx))
    return out
