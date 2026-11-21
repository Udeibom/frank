"""
Composer: turns a chord progression and a section's mood into MIDI parts (song-engine spec 04).

Each instrument is composed as its own Part so it can be rendered, balanced and changed on its own.
A part is a list of note events: { note, start (in beats), duration (in beats), velocity }.
Drums use General MIDI percussion note numbers on channel 9.

What makes this sound like music and not a loop:
  - The melody is a short MOTIF (a rhythm and a shape) that comes back, answered upside down, and ends
    each four-bar phrase on a chord tone with a breath. Notes on the strong beats are always notes of
    the chord that is playing, so it can never clash with the harmony.
  - The bass follows the chord (root, fifth, octave) and steps toward the next chord's root.
  - The drums play a groove from the style, fill into a bigger section, and crash on a chorus.
  - Everything varies by SEED: the same seed always gives the same music, a new seed a different song,
    and a repeated section keeps its character but is not a copy of the first one.
  - Small timing and strength differences keep nothing mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

from app.services.generation import theory
from app.services.generation.rng import derive_seed, rng_for
from app.services.generation.styles import StyleChoice, default_choice

# General MIDI percussion notes (channel 9)
KICK = 36
SIDE_STICK = 37
SNARE = 38
CLOSED_HAT = 42
OPEN_HAT = 46
TOM_LOW = 45
TOM_MID = 47
TOM_HIGH = 50
CRASH = 49

# General MIDI instrument presets (used when no style says otherwise, and by the hum playback)
INSTRUMENTS = {
    "keys": 0,       # Acoustic Grand Piano
    "epiano": 4,     # Electric Piano
    "bass": 33,      # Fingered Bass
    "pad": 89,       # Warm Pad
    "strings": 48,   # String Ensemble
    "pluck": 24,     # Nylon Guitar
}

STEP = 0.25                     # one sixteenth note, in beats
GAP = 0.05                      # always leave this much room before the next note of the same pitch


@dataclass
class NoteEvent:
    note: int
    start: float      # in beats
    duration: float   # in beats
    velocity: int


@dataclass
class Part:
    """One instrument's notes plus which General MIDI preset renders it."""
    name: str                       # "keys", "bass", "drums", "melody", "pad", "strings", "arp"
    preset: int                     # GM program number (ignored for drums)
    is_drums: bool
    events: list[NoteEvent] = field(default_factory=list)
    lead: bool = False              # True when this part is the person's own tune


@dataclass
class SectionContext:
    """What the composer needs to know about where a section sits in the song."""
    name: str = "verse"
    index: int = 0
    repeat: int = 0                 # how many sections of this kind came before this one
    final: bool = False             # this is the last section of its kind
    seed: int = 0                   # the song's seed
    style: StyleChoice = field(default_factory=default_choice)
    next_name: Optional[str] = None
    next_energy: Optional[float] = None
    moments: list = field(default_factory=list)   # planned one-off moments for this section (moments.py)
    lead: Any = None                               # the person's own tune (lead.Lead), when this section plays it
    parts: dict = field(default_factory=dict)      # per-part edits from the plan (SectionPlan.parts)


# ─────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────

def _tier(density: float) -> str:
    return "sparse" if density < 0.35 else ("medium" if density < 0.65 else "busy")


def _vel(rng, base: float, spread: float = 6.0) -> int:
    return max(1, min(127, int(round(base + rng.uniform(-spread, spread)))))


def _at(rng, bar_start: float, beat: float, amount: float = 0.012) -> float:
    """A start time with a touch of human looseness, never before the section starts."""
    return max(0.0, bar_start + beat + rng.uniform(-amount, amount))


def _room(beat: float, dur: float, bar_len: float = 4.0) -> float:
    """A duration that finishes before the bar ends, leaving a gap before the next bar's note."""
    return max(0.1, min(dur, bar_len - beat - GAP))


# ─────────────────────────────────────────────
# Keys (chords)
# ─────────────────────────────────────────────

def compose_chords(progression: dict, bars: int, energy: float, density: float, ctx: Optional[SectionContext] = None) -> Part:
    """The chord part: each hit plays the whole chord. Pattern and instrument come from the style."""
    ctx = ctx or SectionContext()
    part = Part("keys", ctx.style.instruments["keys"], False)
    chords = progression["chords"]
    pattern = ctx.style.keys[_tier(density)]
    rng = rng_for(ctx.seed, ctx.index, "keys")

    for bar in range(bars):
        chord = chords[bar % len(chords)]
        bar_start = bar * 4.0
        hits = [list(h) for h in pattern]
        # Lead into a chorus: the last hit of the bar before it comes in a little early.
        if bar == bars - 1 and ctx.next_name == "chorus" and len(hits) > 1 and rng.random() < 0.65:
            hits[-1] = [3.5, 0.4]
        for beat, dur in hits:
            vel = 50 + energy * 30 + (6 if beat == 0 else 0)
            for i, note in enumerate(sorted(chord)):
                part.events.append(
                    NoteEvent(note, _at(rng, bar_start, beat + 0.008 * i, 0.008), _room(beat, dur), _vel(rng, vel, 5))
                )
    return part


# ─────────────────────────────────────────────
# Bass
# ─────────────────────────────────────────────

def _bass_pitch(kind: str, root: int, tones: list[int], next_root: int, scale_pcs: set[int], rng) -> int:
    """The note a bass pattern step plays. All of them are in the key."""
    if kind == "octave":
        return root + 12
    if kind in ("third", "fifth"):
        pc = tones[1] if kind == "third" else tones[2]
        return root + ((pc - root) % 12)
    if kind == "approach":
        direction = rng.choice([-1, 1])
        for _ in range(3):
            n = next_root + direction * (1 + _)
            if n % 12 in scale_pcs:
                return n
        return next_root
    return root


def compose_bass(progression: dict, bars: int, energy: float, density: float, ctx: Optional[SectionContext] = None) -> Part:
    """Bass: follows each chord and steps toward the next one. Busier with higher density."""
    ctx = ctx or SectionContext()
    part = Part("bass", ctx.style.instruments["bass"], False)
    roots = progression["bass_notes"]
    tones = progression["tones"]
    scale_pcs = {(progression["root"] + i) % 12 for i in theory.SCALE_INTERVALS[progression["mode"]]}
    pattern = ctx.style.bass[_tier(density)]
    rng = rng_for(ctx.seed, ctx.index, "bass")

    for bar in range(bars):
        k = bar % len(roots)
        root, next_root = roots[k], roots[(k + 1) % len(roots)]
        bar_start = bar * 4.0
        for beat, kind, dur in pattern:
            note = _bass_pitch(kind, root, tones[k], next_root, scale_pcs, rng)
            vel = 74 + energy * 24 + (7 if beat == 0 else 0)
            part.events.append(NoteEvent(note, _at(rng, bar_start, beat, 0.006), _room(beat, dur), _vel(rng, vel, 5)))
    return part


# ─────────────────────────────────────────────
# Drums
# ─────────────────────────────────────────────

def _lane(pattern: str) -> list[tuple[int, str]]:
    return [(i, ch) for i, ch in enumerate(pattern) if ch != "."]


def _swing_shift(step: int, swing: float) -> float:
    """Delay the off-beat steps a little, so the groove leans back instead of ticking."""
    if step % 4 == 2:
        return swing * 0.17
    if step % 2 == 1:
        return swing * 0.085
    return 0.0


def _fill_for(ctx: SectionContext, energy: float, bar: int, bars: int, rng) -> Optional[tuple[str, int]]:
    """
    Decide whether this bar ends in a fill, and which kind. Returns (kind, first step affected).
    A bigger section coming up always gets one; inside a section there is a small one now and then.
    """
    style = ctx.style
    last = bar == bars - 1
    if last and (ctx.parts.get("drums") or {}).get("fill"):
        return rng.choice(["roll", "toms"]), 8                 # the person asked for a fill here
    into_bigger = ctx.next_name == "chorus" or (ctx.next_energy is not None and ctx.next_energy > energy * 1.05)
    if last and ctx.next_name is not None and into_bigger:
        kind = rng.choices(["roll", "toms", "stop"], weights=[0.45, 0.35, 0.2])[0]
        return kind, 8
    if not last and bar % 4 == 3 and rng.random() < style.fill * 0.5:
        return rng.choice(["roll", "toms"]), 12
    return None


def compose_drums(bars: int, energy: float, density: float, ctx: Optional[SectionContext] = None) -> Part:
    """
    Drums from the style's groove. Slow, hushed songs play in half time (the snare lands on beat three),
    which is what a producer does with a sad slow song. Fills lead into a bigger section and a chorus
    starts with a crash.
    """
    ctx = ctx or SectionContext()
    style = ctx.style
    d = style.drums
    half = energy < style.half_time_below
    kick = _lane(d["half_kick"] if half else d["kick"])
    snare = _lane(d["half_snare"] if half else d["snare"])
    hat = _lane(d["half_hat"] if half else d["hat"])
    ghost = _lane(d["ghost"]) if (density >= 0.55 and not half) else []
    rng = rng_for(ctx.seed, ctx.index, "drums")
    gain = style.drum_gain
    part = Part("drums", 0, True)

    # Real drummers' feel for this style (frankenstein spec 14, 3.1); its own random stream, so fills and
    # variations stay exactly where they were.
    from app.services.generation import grooves

    groove = None if style.own_groove else grooves.for_style(style.name)
    feel = int((ctx.parts.get("drums") or {}).get("feel", 0))
    feel_rng = rng_for(ctx.seed, ctx.index, "drum-feel")
    swung = style.swing > 0.2

    def add(note: int, step_or_beat: float, vel: float, spread: float = 5.0, dur: float = 0.2, jitter: float = 0.0,
            lane: Optional[str] = None, step: Optional[int] = None) -> None:
        shift, accent = grooves.shape(groove, lane, step, feel, feel_rng, swung) if lane is not None else (0.0, 1.0)
        if lane is not None:
            jitter = 0.0                       # the drummers' own spread replaces the generic wobble
        part.events.append(NoteEvent(note, max(0.0, step_or_beat + shift + (rng.uniform(-jitter, jitter) if jitter else 0.0)),
                                     dur, _vel(rng, min(127, vel * gain * accent), spread)))

    for bar in range(bars):
        bs = bar * 4.0
        fill = _fill_for(ctx, energy, bar, bars, rng)
        cut = fill[1] if fill else 99                    # steps from here on are replaced by the fill

        for i, ch in kick:
            if i < cut:
                add(KICK, bs + i * STEP, 98 + energy * 14 + (4 if i == 0 else 0), lane="kick", step=i)
        # A small variation every fourth bar: an extra kick just before the downbeat.
        if bar % 4 == 3 and not fill and rng.random() < 0.4 and not half:
            add(KICK, bs + 14 * STEP, 84)
        for i, ch in snare:
            if i < cut:
                add(SNARE, bs + i * STEP, 90 + energy * 12, lane="snare", step=i)
        for i, ch in ghost:
            if i < cut:
                add(SNARE, bs + i * STEP + _swing_shift(i, style.swing), 34, 6, 0.1, lane="ghost", step=i)

        thin = density < 0.3                             # sparse sections keep only the hats on the beat
        for i, ch in hat:
            if i >= cut or (thin and i % 4):
                continue
            note = OPEN_HAT if ch == "o" else CLOSED_HAT
            add(note, bs + i * STEP + _swing_shift(i, style.swing), 50 + energy * 22 + (10 if i % 4 == 0 else 0), 6, 0.15, 0.007,
                lane="open" if ch == "o" else "hat", step=i)
        if density >= 0.7 and energy >= 0.6 and not half:  # push: sixteenth hats between the eighths
            for i in range(1, 16, 2):
                if i < cut:
                    add(CLOSED_HAT, bs + i * STEP + _swing_shift(i, style.swing), 38 + energy * 10, 5, 0.1, 0.007, lane="hat", step=i)

        if fill:
            kind, first = fill
            if kind == "roll":
                n = 16 - first
                for j in range(n):
                    add(SNARE, bs + (first + j) * STEP, 50 + 52 * (j / max(1, n - 1)), 4, 0.1)
                add(KICK, bs + first * STEP, 96)
            elif kind == "toms":
                run = [TOM_HIGH, TOM_HIGH, TOM_MID, TOM_MID, TOM_LOW, TOM_LOW, TOM_LOW, KICK]
                for j, note in enumerate(run[: (16 - first) // 2 or 1]):
                    add(note, bs + (first + 2 * j) * STEP, 82 + j * 3, 4, 0.2)
                add(SNARE, bs + first * STEP, 86)
            else:  # "stop": the band drops out for a beat, so the next section lands harder
                pass

        if ctx.name == "chorus" and bar == 0:
            add(CRASH, bs, 104, 4, 1.5)
            if ctx.repeat >= 1:
                add(KICK, bs, 110)
    return part


# ─────────────────────────────────────────────
# Melody
# ─────────────────────────────────────────────

ROLE_CENTRE = {"intro": 67, "verse": 67, "pre-chorus": 70, "chorus": 73, "bridge": 70, "outro": 66}

# Rhythms for one bar: (beat, length). Beats 0 and 2 are the strong beats.
MOTIF_RHYTHMS = {
    "sparse": [
        [(0.0, 1.5), (2.0, 1.5)],
        [(0.0, 2.0), (2.5, 1.2)],
        [(0.5, 1.2), (2.0, 1.6)],
    ],
    "medium": [
        [(0.0, 1.0), (1.5, 0.5), (2.0, 1.0), (3.0, 0.8)],
        [(0.0, 0.75), (1.0, 0.75), (2.0, 1.5)],
        [(0.0, 0.5), (0.5, 0.5), (1.0, 1.0), (2.0, 1.5)],
    ],
    "busy": [
        [(0.0, 0.5), (0.5, 0.5), (1.0, 0.5), (1.5, 0.5), (2.0, 1.0), (3.0, 0.8)],
        [(0.0, 0.75), (0.75, 0.25), (1.0, 0.5), (1.5, 0.5), (2.0, 0.5), (2.5, 0.5), (3.0, 0.8)],
    ],
}

# Shapes: how far each note moves along the scale from the one before it.
CONTOURS = [
    [0, 1, 1, -1, -2, 1, 0],
    [0, 2, -1, -1, 1, 0, 1],
    [0, -1, -1, 2, 1, -2, 0],
    [0, 1, 0, 2, -3, 1, 1],
    [0, 2, 1, -1, -1, -1, 2],
]

MAX_LEAP = 7          # semitones: bigger jumps are hard to sing


def _scale_pool(progression: dict, low: int, high: int) -> list[int]:
    intervals = theory.SCALE_INTERVALS[progression["mode"]]
    return [n for n in range(low, high + 1) if (n - progression["root"]) % 12 in intervals]


def _nearest_chord_tone(pool: list[int], chord_pcs: set[int], idx: int, around: Optional[int] = None) -> int:
    """The index of the chord tone in the pool closest to `idx` (and, if given, within a singable leap of `around`)."""
    candidates = [i for i, n in enumerate(pool) if n % 12 in chord_pcs]
    if around is not None:
        near = [i for i in candidates if abs(pool[i] - pool[around]) <= MAX_LEAP]
        candidates = near or candidates
    return min(candidates, key=lambda i: (abs(i - idx), i)) if candidates else idx


def compose_melody(progression: dict, bars: int, energy: float, density: float, ctx: Optional[SectionContext] = None) -> Part:
    """
    A singable line built from a motif. The motif is chosen once per KIND of section (all the
    choruses share one), so the song has a tune people can remember; repeats vary a little.
    Notes on strong beats are always notes of the current chord. Each four-bar phrase ends on a long
    chord tone and a breath.
    """
    ctx = ctx or SectionContext()
    part = Part("melody", ctx.style.instruments["melody"], False)
    tier = _tier(density)
    centre = ROLE_CENTRE.get(ctx.name, 67) + int(energy * 2)
    pool = _scale_pool(progression, centre - 8, centre + 10)
    chords = progression["chords"]
    chord_pcs = [{n % 12 for n in c} for c in chords]

    motif = rng_for(ctx.seed, ctx.name, "motif")
    rhythm_a, rhythm_b = motif.choice(MOTIF_RHYTHMS[tier]), motif.choice(MOTIF_RHYTHMS[tier])
    contour_a = list(motif.choice(CONTOURS))
    contour_b = [-c for c in contour_a]                       # the answer turns the shape upside down
    vary = rng_for(ctx.seed, ctx.index, "melody-variation")
    rng = rng_for(ctx.seed, ctx.index, "melody-feel")

    prev = _nearest_chord_tone(pool, chord_pcs[0], min(range(len(pool)), key=lambda i: abs(pool[i] - centre)))
    for bar in range(bars):
        bar_start = bar * 4.0
        pcs = chord_pcs[bar % len(chords)]
        phase = bar % 4

        if phase == 3:                                        # cadence: land on the chord and let it ring
            idx = _nearest_chord_tone(pool, pcs, prev, prev)
            dur = 3.0 if tier == "sparse" else 2.0
            part.events.append(NoteEvent(pool[idx], _at(rng, bar_start, 0.0), _room(0.0, dur), _vel(rng, 70 + energy * 24, 4)))
            prev = idx
            continue

        rhythm, contour = (rhythm_a, contour_a) if phase in (0, 1) else (rhythm_b, contour_b)
        for j, (beat, dur) in enumerate(rhythm):
            step = contour[j % len(contour)]
            if phase == 1 and j == len(rhythm) - 1:
                step += 1                                     # the second bar ends differently
            if ctx.repeat > 0 and vary.random() < 0.25:
                step += vary.choice([-1, 1])                  # a repeat is the same tune, not a copy
            idx = max(0, min(len(pool) - 1, prev + step))
            strong = beat in (0.0, 2.0)
            if strong:
                idx = _nearest_chord_tone(pool, pcs, idx, prev)
            elif abs(pool[idx] - pool[prev]) > MAX_LEAP:
                idx = prev                                    # too big a leap on a weak beat: hold the note
            if not strong and j > 0 and rng.random() < 0.1:
                continue                                      # a breath
            nxt = rhythm[j + 1][0] if j + 1 < len(rhythm) else 4.0
            length = min(dur * 0.94, nxt - beat - GAP, 4.0 - beat - GAP)
            if length <= 0.05:
                continue
            vel = 62 + energy * 26 + (6 if strong else 0)
            part.events.append(NoteEvent(pool[idx], _at(rng, bar_start, beat), length, _vel(rng, vel, 4)))
            prev = idx
    return part


# ─────────────────────────────────────────────
# Atmosphere and colour
# ─────────────────────────────────────────────

def compose_pad(progression: dict, bars: int, energy: float, ctx: Optional[SectionContext] = None) -> Part:
    """A soft sustained pad for atmosphere."""
    ctx = ctx or SectionContext()
    part = Part("pad", ctx.style.instruments["pad"], False)
    chords = progression["chords"]
    rng = rng_for(ctx.seed, ctx.index, "pad")
    for bar in range(bars):
        for n in chords[bar % len(chords)]:
            part.events.append(NoteEvent(n + 12, bar * 4.0, 3.95, _vel(rng, 40 + energy * 15, 3)))
    return part


def compose_strings(progression: dict, bars: int, energy: float, ctx: Optional[SectionContext] = None) -> Part:
    """Long held notes that lift a bigger section."""
    ctx = ctx or SectionContext()
    part = Part("strings", ctx.style.instruments["strings"], False)
    chords = progression["chords"]
    rng = rng_for(ctx.seed, ctx.index, "strings")
    for bar in range(bars):
        for n in sorted(chords[bar % len(chords)]):
            part.events.append(NoteEvent(n, bar * 4.0, 3.95, _vel(rng, 46 + energy * 22, 3)))
    return part


def compose_arp(progression: dict, bars: int, energy: float, ctx: Optional[SectionContext] = None) -> Part:
    """A running pattern through the chord tones, for the biggest moments."""
    ctx = ctx or SectionContext()
    part = Part("arp", ctx.style.instruments["arp"], False)
    chords = progression["chords"]
    rng = rng_for(ctx.seed, ctx.index, "arp")
    for bar in range(bars):
        notes = [n + 12 for n in sorted(chords[bar % len(chords)])]
        cycle = notes + notes[-2:0:-1]                        # up, then back down without repeating the top
        for k in range(8):
            part.events.append(
                NoteEvent(cycle[k % len(cycle)], _at(rng, bar * 4.0, k * 0.5, 0.008), 0.42, _vel(rng, 46 + energy * 20, 4))
            )
    return part


def _held_busy(part: Part, edit: Optional[dict]) -> Part:
    """
    "Busier" and "simpler" for the parts whose pattern is not chosen by how busy the section is (the soft background,
    the strings, the running pattern). Simpler: fewer voices (the top note of each chord goes) and, for the running
    pattern, every other note. Busier: the chord doubled an octave up. Every note stays a note of the chord.
    """
    busy = float((edit or {}).get("busy", 0.0))
    if busy == 0.0 or not part.events:
        return part
    if busy < 0:
        if part.name == "arp":
            ev = sorted(part.events, key=lambda e: e.start)
            part.events = ev[::2]
            for e in part.events:
                e.duration = min(e.duration * 2.0, 0.9)
            if busy <= -2:
                part.events = part.events[::2]
            return part
        by_start: dict[float, list[NoteEvent]] = {}
        for e in part.events:
            by_start.setdefault(round(e.start, 3), []).append(e)
        keep: list[NoteEvent] = []
        drop = 2 if busy <= -2 else 1
        for group in by_start.values():
            group.sort(key=lambda e: e.note)
            keep += group[: max(1, len(group) - drop)]
        part.events = keep
        return part
    extra = [NoteEvent(e.note + 12, e.start, e.duration, max(1, int(e.velocity * 0.7)))
             for e in part.events if e.note + 12 <= 100]
    part.events += extra if busy < 2 else extra + [NoteEvent(e.note - 12, e.start, e.duration, max(1, int(e.velocity * 0.6)))
                                                    for e in part.events if e.note - 12 >= 36 and e.velocity > 30][: len(extra)]
    return part


def _trim_overlaps(part: Part) -> Part:
    """
    Make sure a note ends before the next note of the SAME pitch begins. A pattern from the style data
    or a little timing looseness can make them touch; a synth would then cut the note off with a click.
    A note with no room left to sound is dropped.
    """
    if part.is_drums:
        return part
    by_pitch: dict[int, list[NoteEvent]] = {}
    for e in part.events:
        by_pitch.setdefault(e.note, []).append(e)
    dropped: set[int] = set()
    for events in by_pitch.values():
        events.sort(key=lambda e: e.start)
        for a, b in zip(events, events[1:]):
            room = b.start - GAP - a.start
            if a.duration > room:
                if room < 0.05:
                    dropped.add(id(a))
                else:
                    a.duration = room
    part.events = [e for e in part.events if id(e) not in dropped]
    return part


# ─────────────────────────────────────────────
# Section-level composition
# ─────────────────────────────────────────────

def layers_for_section(
    section: str,
    energy: float,
    density: float,
    repeat: int = 0,
    final: bool = False,
    style: Optional[StyleChoice] = None,
) -> list[str]:
    """
    Which parts play in a section. Real songs build: the second chorus is bigger than the first and
    the last one is biggest, a bridge pulls the drums out, an intro and outro are sparse.
    """
    extra = list(style.extra_layers) if style else []
    if section == "intro":
        base = ["keys", "pad"]
        if energy >= 0.5:
            base.append("drums")
    elif section == "verse":
        base = ["keys", "bass", "drums"]
        if density >= 0.6 or repeat >= 1:
            base.append("melody")
        if repeat >= 1 and energy >= 0.4:
            base.append("pad")
    elif section == "pre-chorus":
        base = ["keys", "bass", "drums", "pad"]
    elif section == "chorus":
        base = ["keys", "bass", "drums", "melody", "pad"]
        if repeat >= 1:
            base.append("strings")
        if final or energy >= 0.7:
            base.append("arp")
    elif section == "bridge":
        base = ["pad", "keys", "bass", "strings"]
        if energy >= 0.75:
            base.append("drums")
    elif section == "outro":
        base = ["keys", "pad"]
        if repeat >= 1:
            base.append("melody")
    else:
        base = ["keys", "bass", "drums"]
    if section in ("verse", "pre-chorus", "chorus", "bridge"):
        base += [layer for layer in extra if layer not in base]
    return base


def compose_section(
    section: str,
    progression: dict,
    bars: int,
    energy: float,
    density: float,
    layers: Optional[list[str]] = None,
    ctx: Optional[SectionContext] = None,
) -> list[Part]:
    """
    Compose all the parts for one section, one Part per active layer. Layers the composer does not
    know are ignored, so an older saved beat can never break a new composer.
    """
    ctx = ctx or SectionContext(name=section)
    active = layers if layers is not None else layers_for_section(section, energy, density, ctx.repeat, ctx.final, ctx.style)
    parts: list[Part] = []

    def setting(name: str) -> tuple[SectionContext, float]:
        """The context and busyness for one part, after the person's edits to that part."""
        edit = ctx.parts.get(name) or {}
        part_ctx = ctx
        if edit.get("reseed"):
            part_ctx = replace(ctx, seed=derive_seed(ctx.seed, "reseed", name, int(edit["reseed"])))
        busy = max(0.0, min(1.0, density + 0.3 * float(edit.get("busy", 0.0))))
        return part_ctx, busy

    def add(part: Part) -> None:
        preset = (ctx.parts.get(part.name) or {}).get("preset")
        if preset is not None and not part.is_drums and not part.lead:
            part.preset = int(preset)
        parts.append(part)

    if "keys" in active:
        c, d = setting("keys")
        add(compose_chords(progression, bars, energy, d, c))
    if "bass" in active:
        c, d = setting("bass")
        add(compose_bass(progression, bars, energy, d, c))
    if "drums" in active:
        c, d = setting("drums")
        add(compose_drums(bars, energy, d, c))
    if "melody" in active:
        if ctx.lead is not None:
            from app.services.generation import lead as lead_mod   # imported here: lead builds on this module
            parts.append(Part("melody", lead_mod.LEAD_PROGRAM, False, lead_mod.lead_events(ctx.lead, bars, energy, ctx.seed, ctx.index), lead=True))
        else:
            c, d = setting("melody")
            add(compose_melody(progression, bars, energy, d, c))
    if "pad" in active:
        c, _ = setting("pad")
        add(_held_busy(compose_pad(progression, bars, energy, c), ctx.parts.get("pad")))
    if "strings" in active:
        c, _ = setting("strings")
        add(_held_busy(compose_strings(progression, bars, energy, c), ctx.parts.get("strings")))
    if "arp" in active:
        c, _ = setting("arp")
        add(_held_busy(compose_arp(progression, bars, energy, c), ctx.parts.get("arp")))
    if ctx.moments:
        from app.services.generation import touches   # imported here: touches builds on this module
        parts = touches.apply_moments(parts, ctx.moments, progression, bars, ctx)
    return [_trim_overlaps(p) for p in parts]
