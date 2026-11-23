"""
Music that plays to the singer (core-path spec 15, requirement 8).

The founder, 23 Nov: "Frank needs to understand what the person sang, the same way a human sitting on a piano would
understand and play to them." Until now the beat was built from the feeling and the voice was laid on top; the
music followed its own plan of verses and choruses while the singer followed theirs.

A pianist accompanying a singer listens for four things, and so does this module:
1. **The pulse and the bar lines.** If they sang over Frank's music, its pulse is theirs (the take is already in
   song time). Otherwise the pulse is found from when their notes start, and the bar line from where their lines
   and long notes land.
2. **Where the song changes.** Their verses and choruses, placed in time by the word timings of each lyric line;
   without words, by their phrases and which melodies come back.
3. **The chords under each bar**, chosen to fit the notes they sing in that bar (the same best-path harmony the
   hummed tune uses, here bar by bar through the whole song).
4. **How big each part is**, from how high and how busy their singing is there, and the music steps back where
   they sing: their voice is the tune, so the music never plays a competing one.
It begins before their first line and ends a couple of bars after their last note, on the home chord.
Everything here is pure (no audio, no database), so it can be tested; the job is in beat_runner.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from app.services.generation import composer, lead as lead_mod
from app.services.generation.beat import SECTION_ENERGY, SectionPlan, _stamp_repeats

PICKUP_BEATS = 0.75          # a line that starts this close before a bar line belongs to that bar (a pickup)
OUTRO_BARS = 2               # after the last note: two bars that settle home
MAX_SECTION_BARS = 32
MIN_NOTES = 8


@dataclass(frozen=True)
class Note:
    start: float             # seconds in the recording
    end: float
    pitch: float             # MIDI, as sung


@dataclass(frozen=True)
class Grid:
    bpm: float
    start_s: float           # where the first bar line falls in the recording (0 <= start_s < one bar)

    @property
    def beat_s(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar_s(self) -> float:
        return 4.0 * self.beat_s

    def bar_at(self, t: float) -> float:
        return (t - self.start_s) / self.bar_s


@dataclass
class SungSection:
    name: str
    start_s: float
    end_s: float
    feeling: Optional[str] = None


@dataclass
class Accompaniment:
    sections: list[SectionPlan]
    grid: Grid
    key: str
    first_note_s: float
    last_note_s: float
    sung: list[SungSection] = field(default_factory=list)
    how: str = "phrases"     # "words" when the lyric lines placed the sections


# ── 1. pulse and bar lines ──────────────────────────────────────────────────────────────────────────────

def _strength(onsets: np.ndarray, weights: np.ndarray, period: float) -> tuple[float, float]:
    z = (weights * np.exp(2j * np.pi * onsets / period)).sum() / max(weights.sum(), 1e-9)
    return float(abs(z)), float((np.angle(z) / (2 * np.pi)) * period % period)


def grid_from_notes(notes: list[Note], text: str = "", line_starts: Optional[list[float]] = None) -> Grid:
    """The singer's own pulse and bar line, for a recording made without Frank's music."""
    from app.services.intake import pace

    onsets = np.array([n.start for n in notes], dtype=float)
    weights = np.array([min(1.5, max(0.1, n.end - n.start)) for n in notes], dtype=float)
    # Every speed at which their notes start on a beat. Held notes fit many speeds equally well (notes two beats
    # apart fit 1, 1.5, 2... times the speed), so take the slowest pulse that explains them all, the way a pianist
    # counts, then count it at the speed that suits the song's feeling.
    tempos = np.arange(50.0, 180.0001, 0.05)
    strength = np.array([_strength(onsets, weights, 60.0 / t)[0] for t in tempos])
    top = float(strength.max())
    fits = [i for i in range(1, len(tempos) - 1)
            if strength[i] >= 0.92 * top and strength[i] >= strength[i - 1] and strength[i] >= strength[i + 1]]
    slowest = float(tempos[fits[0]]) if fits else float(tempos[int(strength.argmax())])

    def fits_at(t: float) -> bool:
        return 50.0 <= t <= 180.0 and _strength(onsets, weights, 60.0 / t)[0] >= 0.92 * top

    target = pace.centre(text)
    options = [slowest * f for f in (1.0, 2.0, 4.0) if fits_at(slowest * f)] or [slowest]
    coarse = min(options, key=lambda t: abs(math.log2(t / target)))
    best = max(np.arange(coarse - 0.5, coarse + 0.5001, 0.01), key=lambda b: _strength(onsets, weights, 60.0 / b)[0])
    bpm = round(float(best), 2)
    beat = 60.0 / bpm
    phase = _strength(onsets, weights, beat)[1]
    # The bar line: of the four beats, the one their lines and long notes land on most.
    starts = list(line_starts or []) or [n.start for i, n in enumerate(notes) if i == 0 or n.start - notes[i - 1].end > beat]
    long_notes = [n.start for n in notes if n.end - n.start >= beat]

    def score(k: int) -> float:
        line = phase + k * beat
        total = 0.0
        for t, w in [(t, 2.0) for t in starts] + [(t, 1.0) for t in long_notes]:
            pos = ((t - line) / (4 * beat)) % 1.0
            dist = min(pos, 1.0 - pos) * 4                       # distance from the bar line, in beats
            total += w * max(0.0, 1.0 - dist / 0.5)
        return total

    k = max(range(4), key=score)
    return Grid(bpm=bpm, start_s=float((phase + k * beat) % (4 * beat)))


# ── 2. where the song changes ───────────────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def sections_from_words(lines: list[dict], structure: Optional[dict], lyrics: str) -> Optional[list[SungSection]]:
    """
    The lyric sections (verse, chorus...) placed in time by when each of their lines was sung. Lines are matched by
    their words, because the sections count headings like [Chorus] as lines and the word timings do not.
    """
    from app.services.intake.lyrics import lines_of

    placed = [l for l in lines or [] if l.get("start") is not None and l.get("end") is not None]
    secs = (structure or {}).get("sections") or []
    if len(placed) < 2 or not secs:
        return None
    all_lines = lines_of(lyrics or "")
    used: set[int] = set()
    out: list[SungSection] = []
    for sec in secs:
        try:
            a, b = int(sec["first_line"]), int(sec["last_line"])
        except (KeyError, TypeError, ValueError):
            continue
        texts = {_norm(all_lines[k - 1]) for k in range(a, b + 1) if 0 < k <= len(all_lines)}
        hits = [i for i, l in enumerate(placed) if i not in used and _norm(l.get("text", "")) in texts]
        if not hits:
            continue
        used.update(hits)
        out.append(SungSection(str(sec.get("name") or "verse").lower(), min(placed[i]["start"] for i in hits),
                               max(placed[i]["end"] for i in hits), sec.get("feeling")))
    out = [s for s in out if s.name in SECTION_ENERGY and s.name not in ("intro", "outro")]
    if len(out) < 1 or len(used) < max(2, len(placed) // 2):
        return None
    out.sort(key=lambda s: s.start_s)
    return out


def _profile(notes: list[Note]) -> np.ndarray:
    h = np.zeros(12)
    for n in notes:
        h[int(round(n.pitch)) % 12] += n.end - n.start
    return h / (np.linalg.norm(h) or 1.0)


BLOCK_BARS = 4               # songs move in four-bar phrases; a section is one or more of them


def _similar(a: list[Note], b: list[Note]) -> bool:
    if not a or not b:
        return False
    ha, hb = float(np.mean([n.pitch for n in a])), float(np.mean([n.pitch for n in b]))
    return float(_profile(a) @ _profile(b)) > 0.9 and abs(ha - hb) < 2.0


def sections_from_phrases(notes: list[Note], grid: Grid) -> list[SungSection]:
    """
    Without words: the singing in four-bar phrases. Neighbouring phrases with the same melody belong to one section;
    a section starts where the melody changes, or after a long pause. The melody that keeps coming back and is sung
    highest is the chorus, the way a pianist hears it (people often sing straight from a verse into a chorus, so a
    pause alone does not mark the change).
    """
    if not notes:
        return []
    first_bar = _bar(grid, notes[0].start)
    blocks: list[list[Note]] = []
    block_start: list[int] = []
    for n in notes:
        b = _bar(grid, n.start)
        k = (b - first_bar) // BLOCK_BARS
        start = first_bar + k * BLOCK_BARS
        if not block_start or start != block_start[-1]:
            blocks.append([])
            block_start.append(start)
        blocks[-1].append(n)
    # Higher or lower: a chorus usually sits clearly above the verse. Two kinds of phrase when the singing splits
    # cleanly by height; otherwise phrases that repeat an earlier one are told apart from new ones.
    heights = np.array([float(np.mean([n.pitch for n in b])) for b in blocks])
    order = np.sort(heights)
    cut, best_gap = None, 0.0
    for k in range(1, len(order)):
        if order[k] - order[k - 1] > best_gap:
            best_gap, cut = float(order[k] - order[k - 1]), float((order[k] + order[k - 1]) / 2)
    if cut is not None and best_gap >= 1.5:
        kind = ["chorus" if h > cut else "verse" for h in heights]
    else:
        kind = ["verse"] * len(blocks)
    groups: list[list[int]] = [[0]]
    for i in range(1, len(blocks)):
        gap = blocks[i][0].start - blocks[i - 1][-1].end
        if kind[i] == kind[groups[-1][-1]] and gap < grid.bar_s * 0.9 and len(groups[-1]) < 4:
            groups[-1].append(i)
        else:
            groups.append([i])
    sects = [[n for i in g for n in blocks[i]] for g in groups]
    names = [kind[g[0]] for g in groups]
    if len(set(names)) == 1 and len(sects) > 1:
        # One height all the way through: the melody that comes back, sung highest, is still the chorus.
        family = list(range(len(sects)))
        for a in range(len(sects)):
            for b in range(a):
                if _similar(sects[a], sects[b]):
                    family[a] = family[b]
                    break
        hs = [float(np.mean([n.pitch for n in g])) for g in sects]
        repeated = [f for f in set(family) if family.count(f) >= 2]
        chorus = max(repeated, key=lambda f: np.mean([hs[x] for x in range(len(sects)) if family[x] == f]), default=None)
        if chorus is not None and len(set(family)) > 1:
            names = ["chorus" if family[x] == chorus else "verse" for x in range(len(sects))]
    out = []
    for i, g in enumerate(sects):
        start = grid.start_s + block_start[groups[i][0]] * grid.bar_s
        out.append(SungSection(names[i], max(start, g[0].start - grid.beat_s), g[-1].end))
    return out


# ── 3 and 4. the plan: chords per bar that fit them, sized by how they sing ─────────────────────────────

def estimate_key(notes: list[Note]) -> str:
    from app.services.intake.melody import RawNote, estimate_key as key_of

    raw = [RawNote(n.start, n.end, int(round(n.pitch)), n.pitch) for n in notes]
    name, mode, _ = key_of(raw)
    return f"{name} {mode}"


def _bar(grid: Grid, t: float) -> int:
    """The bar a moment belongs to; a line sung just before a bar line starts that bar."""
    return max(0, int(math.floor(grid.bar_at(t) + PICKUP_BEATS / 4.0)))


def _harmony(notes: list[Note], grid: Grid, first_bar: int, bars: int, key: str, extension: float) -> dict:
    """One chord per bar that fits what they sing in those bars."""
    rel = []
    for n in notes:
        s = (n.start - grid.start_s) / grid.beat_s - first_bar * 4.0
        e = (n.end - grid.start_s) / grid.beat_s - first_bar * 4.0
        s, e = max(0.0, s), min(bars * 4.0, e)
        if e - s > 0.05:
            rel.append((int(round(n.pitch)), round(s, 4), round(e - s, 4)))
    if not rel:
        return {"degrees": [0] * bars, "sevenths": [False] * bars}
    prog = lead_mod.harmonize(lead_mod.Lead(notes=tuple(rel), bars=bars, key=key), key, extension)
    return {"degrees": list(prog["degrees"]), "sevenths": [bool(x) for x in prog["sevenths"]]}


def plan(notes: list[Note], grid: Grid, sung: list[SungSection], fp: dict, how: str = "phrases") -> Optional[Accompaniment]:
    """The whole accompaniment as a section plan the engine renders, with each section's own chords."""
    from app.services.generation.styles import pick_style

    notes = sorted(notes, key=lambda n: n.start)
    if len(notes) < MIN_NOTES or not sung:
        return None
    style = pick_style(fp)
    key = estimate_key(notes)
    first, last = notes[0].start, max(n.end for n in notes)
    starts = [_bar(grid, s.start_s) for s in sung]
    # Sections in time order, each from its first bar to where the next begins; never zero bars long.
    bounds: list[tuple[str, int, int, Optional[str]]] = []
    end_bar = max(starts[-1] + 1, int(math.ceil(grid.bar_at(last) - 1e-6)))
    for i, s in enumerate(sung):
        a = starts[i] if not bounds else max(starts[i], bounds[-1][2])
        b = starts[i + 1] if i + 1 < len(sung) else end_bar
        b = max(b, a + 1)
        while b - a > MAX_SECTION_BARS:
            bounds.append((s.name, a, a + 16, s.feeling))
            a += 16
        bounds.append((s.name, a, b, s.feeling))
    intro = bounds[0][1]
    out: list[SectionPlan] = []
    if intro > 0:
        out.append(SectionPlan(0, "intro", "Intro", intro, 0.0, 0.0, layers=[]))
    for name, a, b, feeling in bounds:
        out.append(SectionPlan(len(out), name, name.capitalize(), b - a, 0.0, 0.0, layers=[]))
        out[-1].parts["harmony"] = _harmony(notes, grid, a, b - a, key, style.extension)
        out[-1].parts["_span"] = (a, b, feeling)
    out.append(SectionPlan(len(out), "outro", "Outro", OUTRO_BARS, 0.0, 0.0, layers=[]))
    _stamp_repeats(out)

    # How big each part is: higher and busier singing gets more music under it.
    sung_parts = [s for s in out if "_span" in s.parts]
    def stats(s: SectionPlan) -> tuple[float, float]:
        a, b, _ = s.parts["_span"]
        inside = [n for n in notes if a <= _bar(grid, n.start) < b]
        height = float(np.mean([n.pitch for n in inside])) if inside else 0.0
        busy = len(inside) / max(1, b - a)
        return height, busy
    table = [stats(s) for s in sung_parts]
    hs, bs = np.array([t[0] for t in table]), np.array([t[1] for t in table])
    z = lambda v: (v - v.mean()) / (v.std() or 1.0)  # noqa: E731
    zh, zb = z(hs), z(bs)
    base_e, base_d = float(fp.get("energy_level", 0.5)), float(fp.get("density", 0.5))
    for s, a, b in zip(sung_parts, zh, zb):
        feeling = s.parts["_span"][2]
        mult = SECTION_ENERGY.get(s.name, 0.8) + 0.12 * float(a) + 0.06 * float(b)
        if feeling == "sorrowful":
            mult -= 0.06
        s.energy = max(0.05, min(1.0, base_e * mult))
        s.density = max(0.05, min(1.0, base_d * (0.8 + 0.4 * mult)))
    for s in out:
        if s.name == "intro":
            s.energy, s.density = max(0.05, base_e * 0.6), max(0.05, base_d * 0.6)
            first_chords = sung_parts[0].parts["harmony"]
            n = s.bars
            s.parts["harmony"] = {"degrees": (first_chords["degrees"] * n)[:n], "sevenths": [False] * n}
        elif s.name == "outro":
            s.energy, s.density = max(0.05, base_e * 0.5), max(0.05, base_d * 0.5)
            s.parts["harmony"] = {"degrees": [3, 0][-s.bars:], "sevenths": [False] * s.bars}   # settle home
        s.layers = composer.layers_for_section(s.name, s.energy, s.density, s.repeat, s.final, style)
        # Their voice is the tune: the music never plays a competing one, and leaves room where they sing.
        s.layers = [p for p in s.layers if p != "melody" and not (p == "arp" and "_span" in s.parts and s.energy < 0.6)]
        s.parts.pop("_span", None)
        s.uid = s.index
    return Accompaniment(out, grid, key, first, last, sung, how)
