"""
Moments: the one-off things that make a song feel arranged instead of stacked (song-engine spec 04).

A stacked song has the same instruments the whole way and only ever ADDS layers. A produced song
also takes things away, brings a sound in late, uses a sound once, builds into a chorus, stops for a
beat before it lands, and ends on purpose. This module decides WHERE those things happen. It is pure
planning: no audio and no notes. `touches.py` turns each moment into notes.

Planning depends only on the song's shape (section names, order, bars) and the seed, never on how
busy a section is, so changing one section never moves a moment in another.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.generation.rng import rng_for

WARM_COLOURS = [24, 46, 11, 25]      # nylon guitar, harp, vibraphone, steel guitar
BRIGHT_COLOURS = [9, 10, 8, 12]      # glockenspiel, music box, celesta, marimba
ONE_OFF_WARM = 14                    # tubular bells
ONE_OFF_BRIGHT = 9                   # glockenspiel
KEYS_SWAPS = [4, 11, 24, 46]         # electric piano, vibraphone, nylon guitar, harp
VOICE_PAD = 53                       # voice oohs
RISER_PROGRAM = 95                   # sweep pad
REVERSE_CYMBAL = 119


@dataclass(frozen=True)
class Moment:
    kind: str            # late_entry | dropout | stop | riser | answer | one_off | swap_voice | ending
    bar: int = 0
    bars: int = 1
    parts: tuple[str, ...] = ()
    program: int = 0


@dataclass(frozen=True)
class Facts:
    """What the planner knows about one section."""
    index: int
    name: str
    bars: int
    repeat: int
    final: bool
    next_name: Optional[str]
    uid: Optional[int] = None    # stable identity: a moved section keeps its own moments


def facts_from(sections: list) -> list[Facts]:
    """Facts for a list of anything with index, name, bars, repeat and final."""
    out: list[Facts] = []
    for i, s in enumerate(sections):
        nxt = sections[i + 1].name if i + 1 < len(sections) else None
        uid = getattr(s, "uid", None)
        out.append(Facts(s.index, s.name, s.bars, s.repeat, s.final, nxt, s.index if uid is None else uid))
    return out


KIND_ORDER = ["verse", "chorus", "bridge", "outro", "pre-chorus", "intro"]


def _colour(seed: int, name: str, tone_score: float) -> int:
    """A sound for this kind of section. Different kinds of section get different sounds."""
    rng = rng_for(seed, "colour", name)
    warm_chance = max(0.1, min(0.9, 0.5 + tone_score * 0.5))
    pool = WARM_COLOURS if rng.random() < warm_chance else BRIGHT_COLOURS
    start = rng.randrange(len(pool))
    position = KIND_ORDER.index(name) if name in KIND_ORDER else len(KIND_ORDER)
    return pool[(start + position) % len(pool)]


def one_off_section(facts: list[Facts], seed: int) -> Optional[int]:
    """The single section that gets the song's one-time sound: the bridge, or else the last chorus."""
    # The ending clears the last bar, so a very short last section cannot keep the sound.
    usable = [f for f in facts if not (f is facts[-1] and f.bars < 3)]
    bridges = [f.index for f in usable if f.name == "bridge"]
    choruses = [f.index for f in usable if f.name == "chorus" and f.final]
    options = bridges + choruses
    if not options:
        return None
    return rng_for(seed, "one-off").choice(options)


def plan_moments(facts: list[Facts], seed: int, warmth: float, brightness: float) -> dict[int, list[Moment]]:
    """Moments for every section, keyed by section index."""
    tone_score = warmth - brightness
    plan: dict[int, list[Moment]] = {f.index: [] for f in facts}
    special = one_off_section(facts, seed)
    last = facts[-1].index if facts else None

    for f in facts:
        rng = rng_for(seed, "moments", f.index if f.uid is None else f.uid, f.name)
        moments = plan[f.index]
        big = f.bars >= 8

        # A verse opens thin and the low end walks in part-way, the way a band builds a first verse.
        if f.name == "verse" and f.repeat == 0 and big and rng.random() < 0.7:
            moments.append(Moment("late_entry", bar=4, parts=("bass",)))
        if f.name == "verse" and f.repeat == 0 and big and rng.random() < 0.4:
            moments.append(Moment("late_entry", bar=2, parts=("drums",)))

        # Everything pulls back for a bar in the middle of a later chorus, then slams back in.
        if f.name == "chorus" and f.repeat >= 1 and big and rng.random() < 0.6:
            moments.append(Moment("dropout", bar=3, bars=1, parts=("drums", "bass")))

        # A call-and-response sound that fills the gaps in the tune. A different sound for each kind of section.
        answer_chance = {"chorus": 0.9 if f.repeat >= 1 else 0.35, "verse": 0.5 if f.repeat >= 1 else 0.0, "bridge": 0.7}
        if f.bars >= 4 and rng.random() < answer_chance.get(f.name, 0.0):
            moments.append(Moment("answer", program=_colour(seed, f.name, tone_score)))

        # A different voice in the places a song changes character.
        if f.name == "bridge":
            taken = _colour(seed, "bridge", tone_score)
            moments.append(Moment("swap_voice", parts=("keys",), program=rng.choice([k for k in KEYS_SWAPS if k != taken])))
        if (f.name == "chorus" and f.repeat >= 1) or f.name == "bridge":
            if rng.random() < 0.6:
                moments.append(Moment("swap_voice", parts=("pad",), program=VOICE_PAD))

        # A build into a chorus, sometimes ending in a beat of silence so the chorus lands harder.
        if f.next_name == "chorus" and f.name in ("verse", "pre-chorus", "bridge"):
            chance = {"bridge": 0.9, "pre-chorus": 0.9}.get(f.name, 0.55 if f.repeat == 0 else 0.7)
            if rng.random() < chance:
                moments.append(Moment("riser"))
            if rng.random() < (0.7 if f.name == "bridge" else 0.3):
                moments.append(Moment("stop"))

        # One sound that appears once in the whole song.
        if f.index == special:
            moments.append(Moment("one_off", program=ONE_OFF_WARM if tone_score >= -0.05 else ONE_OFF_BRIGHT))

        # Every song ends on purpose.
        if f.index == last:
            moments.append(Moment("ending"))
    return plan
