"""
Typed edit operations on a beat's plan (song-engine spec 04, requirements 5.2-5.4 and 6.2; tasks 7.1, 7.4).

The Beat Room model no longer passes free text that is matched against keywords. It emits operations like
{"op": "busier", "section": 2, "part": "drums"}. Each is validated, applied to a COPY of the plan, and returns
a plain sentence saying exactly what changed. Invalid operations raise OpError with a plain reason and change
nothing. A section is named by its position in the song (0-based); `section: null` means every section.
"""
from __future__ import annotations

import copy
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.services.generation import composer
from app.services.generation.beat import SectionPlan, _stamp_repeats
from app.services.generation.rng import derive_seed

PARTS = ("drums", "bass", "keys", "melody", "pad", "strings", "arp")
PLAIN_PART = {"drums": "the drums", "bass": "the bass", "keys": "the keys", "melody": "the tune", "pad": "the soft background",
              "strings": "the strings", "arp": "the running pattern"}
PLAIN_SECTION = {"intro": "intro", "verse": "verse", "pre-chorus": "build-up", "chorus": "chorus", "bridge": "bridge", "outro": "ending"}

# Sounds a person can ask for, in their words, mapped to General MIDI programs.
SOUNDS: dict[str, int] = {
    "piano": 0, "bright piano": 1, "electric piano": 4, "organ": 16, "church organ": 19, "nylon guitar": 24,
    "acoustic guitar": 25, "clean guitar": 27, "electric guitar": 29, "harp": 46, "strings": 48, "soft strings": 49,
    "choir": 52, "voices": 53, "vibraphone": 11, "bells": 14, "music box": 10, "marimba": 12, "flute": 73,
    "saxophone": 65, "trumpet": 56, "synth": 81, "warm synth": 89, "glassy synth": 94, "violin": 40, "cello": 42,
    "upright bass": 32, "finger bass": 33, "picked bass": 34, "synth bass": 38,
}
MIN_BARS, MAX_BARS, MAX_SECTIONS = 1, 32, 16

Scope = Union[int, list[int], None]
PartName = Literal["drums", "bass", "keys", "melody", "pad", "strings", "arp"]


class _Op(BaseModel):
    model_config = {"extra": "forbid"}


class Busier(_Op):
    op: Literal["busier"]
    part: PartName
    section: Scope = None


class Sparser(_Op):
    op: Literal["sparser"]
    part: PartName
    section: Scope = None


class Bigger(_Op):
    op: Literal["bigger"]
    section: Scope = None


class Smaller(_Op):
    op: Literal["smaller"]
    section: Scope = None


class AddPart(_Op):
    op: Literal["add_part"]
    part: PartName
    section: Scope = None


class RemovePart(_Op):
    op: Literal["remove_part"]
    part: PartName
    section: Scope = None


class SwapSound(_Op):
    op: Literal["swap_sound"]
    part: PartName
    sound: str
    section: Scope = None


class AddFill(_Op):
    op: Literal["add_fill"]
    section: Union[int, list[int]]


class Reseed(_Op):
    """"Try something different" for one part, or for a whole section when part is empty."""
    op: Literal["try_another"]
    part: Optional[PartName] = None
    section: Scope = None


class AnotherSong(_Op):
    """A whole new take on the song: new seed for everything (requirement 6.2)."""
    op: Literal["another_song"]


class Resize(_Op):
    op: Literal["resize"]
    section: int
    bars: int


class Move(_Op):
    op: Literal["move"]
    section: int
    to: int


class Repeat(_Op):
    op: Literal["repeat"]
    section: int


class RemoveSection(_Op):
    op: Literal["remove_section"]
    section: int


Operation = Annotated[
    Union[Busier, Sparser, Bigger, Smaller, AddPart, RemovePart, SwapSound, AddFill, Reseed, AnotherSong, Resize, Move,
          Repeat, RemoveSection],
    Field(discriminator="op"),
]
_ADAPTER = TypeAdapter(list[Operation])


class OpError(ValueError):
    """An operation that cannot be applied. The message is plain words for the person."""


def parse(raw: list[dict]) -> list:
    """Validate raw operations. Raises OpError naming the first problem in plain words."""
    try:
        return _ADAPTER.validate_python(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise OpError(f"I couldn't follow that change ({'.'.join(str(x) for x in first['loc'])}: {first['msg']}).") from exc


def _where(sections: list[SectionPlan], scope: Scope) -> list[SectionPlan]:
    if scope is None:
        return sections
    idx = [scope] if isinstance(scope, int) else list(scope)
    if not idx or any(not 0 <= i < len(sections) for i in idx):
        raise OpError("That part of the song doesn't exist any more.")
    return [sections[i] for i in dict.fromkeys(idx)]


def _name(sections: list[SectionPlan], s: SectionPlan) -> str:
    same = [x for x in sections if x.name == s.name]
    word = PLAIN_SECTION.get(s.name, s.name)
    if len(same) == 1:
        return f"the {word}"
    ordinal = ["first", "second", "third", "fourth", "fifth", "sixth"][min(same.index(s), 5)]
    return f"the {ordinal} {word}"


def _scope_words(sections: list[SectionPlan], scope: Scope) -> str:
    if scope is None:
        return "everywhere"
    idx = [scope] if isinstance(scope, int) else list(dict.fromkeys(scope))
    targets = [sections[i] for i in idx]
    if len(targets) > 1 and len({t.name for t in targets}) == 1:
        word = PLAIN_SECTION.get(targets[0].name, targets[0].name)
        every = len(targets) == sum(x.name == targets[0].name for x in sections)
        return f"in {'every' if every else 'those'} {word}" + ("" if every else "s")
    names = [_name(sections, t) for t in targets]
    return "in " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1])


def _renumber(sections: list[SectionPlan]) -> None:
    for i, s in enumerate(sections):
        s.index = i
    _stamp_repeats(sections)


def _next_uid(sections: list[SectionPlan]) -> int:
    return max((s.uid if s.uid is not None else s.index) for s in sections) + 1000


def _apply(op, sections: list[SectionPlan], seed: int) -> tuple[int, str]:
    if isinstance(op, (Busier, Sparser)):
        targets = _where(sections, op.section)
        step = 1.0 if isinstance(op, Busier) else -1.0
        hit = [s for s in targets if op.part in s.layers]
        if not hit:
            raise OpError(f"{PLAIN_PART[op.part].capitalize()} isn't playing there, so I can't make it {'busier' if step > 0 else 'simpler'}.")
        for s in hit:
            edit = s.parts.setdefault(op.part, {})
            edit["busy"] = max(-2.0, min(2.0, float(edit.get("busy", 0.0)) + step))
        return seed, f"I made {PLAIN_PART[op.part]} {'busier' if step > 0 else 'simpler'} {_scope_words(sections, op.section)}."
    if isinstance(op, (Bigger, Smaller)):
        step = 0.15 if isinstance(op, Bigger) else -0.15
        for s in _where(sections, op.section):
            s.energy = max(0.05, min(1.0, s.energy + step))
            s.density = max(0.05, min(1.0, s.density + step * 0.6))
        return seed, f"I made it {'bigger' if step > 0 else 'calmer'} {_scope_words(sections, op.section)}."
    if isinstance(op, AddPart):
        hit = [s for s in _where(sections, op.section) if op.part not in s.layers]
        if not hit:
            raise OpError(f"{PLAIN_PART[op.part].capitalize()} is already playing there.")
        for s in hit:
            s.layers.append(op.part)
        return seed, f"I brought in {PLAIN_PART[op.part]} {_scope_words(sections, op.section)}."
    if isinstance(op, RemovePart):
        hit = [s for s in _where(sections, op.section) if op.part in s.layers]
        if not hit:
            raise OpError(f"{PLAIN_PART[op.part].capitalize()} isn't playing there.")
        for s in hit:
            s.layers.remove(op.part)
        return seed, f"I took {PLAIN_PART[op.part]} out {_scope_words(sections, op.section)}."
    if isinstance(op, SwapSound):
        key = op.sound.strip().lower()
        if key not in SOUNDS:
            raise OpError(f"I don't have a sound called “{op.sound}”. I can use: {', '.join(sorted(SOUNDS))}.")
        if op.part == "drums":
            raise OpError("The drums keep their kit; I can make them busier, simpler or add a fill.")
        for s in _where(sections, op.section):
            s.parts.setdefault(op.part, {})["preset"] = SOUNDS[key]
        return seed, f"{PLAIN_PART[op.part].capitalize()} now plays on {key} {_scope_words(sections, op.section)}."
    if isinstance(op, AddFill):
        hit = [s for s in _where(sections, op.section) if "drums" in s.layers]
        if not hit:
            raise OpError("There are no drums there to play a fill.")
        for s in hit:
            s.parts.setdefault("drums", {})["fill"] = True
        return seed, f"I added a drum fill at the end {_scope_words(sections, op.section).replace('in ', 'of ', 1)}."
    if isinstance(op, Reseed):
        targets = _where(sections, op.section)
        parts = [op.part] if op.part else list(PARTS)
        for s in targets:
            for p in parts:
                edit = s.parts.setdefault(p, {})
                edit["reseed"] = int(edit.get("reseed", 0)) + 1
        what = PLAIN_PART[op.part] if op.part else "everything"
        return seed, f"I tried a different idea for {what} {_scope_words(sections, op.section)}."
    if isinstance(op, AnotherSong):
        return derive_seed(seed, "another"), "I made a whole new take on the song, with the same feeling."
    if isinstance(op, Resize):
        s = _where(sections, op.section)[0]
        if not MIN_BARS <= op.bars <= MAX_BARS:
            raise OpError("That would make the section too short or too long.")
        longer = op.bars > s.bars
        s.bars = op.bars
        return seed, f"I made {_name(sections, s)} {'longer' if longer else 'shorter'}."
    if isinstance(op, Move):
        s = _where(sections, op.section)[0]
        if not 0 <= op.to < len(sections):
            raise OpError("I can't move it there.")
        label = _name(sections, s)
        sections.remove(s)
        sections.insert(op.to, s)
        _renumber(sections)
        return seed, f"I moved {label} to a new place in the song."
    if isinstance(op, Repeat):
        s = _where(sections, op.section)[0]
        if len(sections) >= MAX_SECTIONS:
            raise OpError("The song is already as long as I can make it.")
        twin = copy.deepcopy(s)
        twin.uid = _next_uid(sections)
        twin.stems = {}
        sections.insert(op.section + 1, twin)
        label = _name(sections, s)
        _renumber(sections)
        return seed, f"I played {label} one more time."
    if isinstance(op, RemoveSection):
        s = _where(sections, op.section)[0]
        if len(sections) <= 1:
            raise OpError("That's the only part of the song left.")
        label = _name(sections, s)
        sections.remove(s)
        _renumber(sections)
        return seed, f"I took {label} out of the song."
    raise OpError("I don't know how to make that change yet.")


def apply_operations(sections: list[SectionPlan], seed: int, raw: list[dict]) -> tuple[list[SectionPlan], int, list[str]]:
    """
    Apply operations in order to a copy of the plan. Returns (new sections, new seed, plain change sentences).
    The input is never modified. Any invalid operation stops everything and changes nothing.
    """
    ops = parse(raw)
    if not ops:
        raise OpError("There was nothing to change.")
    out = copy.deepcopy(sections)
    for s in out:
        if s.uid is None:
            s.uid = s.index
    changes: list[str] = []
    for op in ops:
        seed, said = _apply(op, out, seed)
        changes.append(said)
    _renumber(out)
    return out, seed, changes


# For the Beat Room prompt: the vocabulary the model may use.
PROMPT_OPERATIONS = """\
OPERATIONS (put them in one action: {"type": "beat_operations", "params": {"operations": [ ... ]}}):
section is the [number] of a section from the beat you are shown, a list of numbers (e.g. every chorus: [2, 4, 6]),
or null for every section. Prefer a list over null when the person names a kind of section.
part is one of: drums, bass, keys, melody, pad, strings, arp.
- {"op": "busier", "part": P, "section": S}        more going on in that part
- {"op": "sparser", "part": P, "section": S}       simpler, more space
- {"op": "bigger", "section": S}                   hits harder, fuller
- {"op": "smaller", "section": S}                  calmer, sits back
- {"op": "add_part", "part": P, "section": S}
- {"op": "remove_part", "part": P, "section": S}
- {"op": "swap_sound", "part": P, "sound": NAME, "section": S}   NAME one of: """ + ", ".join(sorted(SOUNDS)) + """
- {"op": "add_fill", "section": N}                  a drum fill at the end of that section
- {"op": "try_another", "part": P or null, "section": S}   a different idea for that part (or all parts)
- {"op": "another_song"}                           a whole new take with the same feeling
- {"op": "resize", "section": N, "bars": 1-32}     longer or shorter (a bar is about 2-3 seconds)
- {"op": "move", "section": N, "to": M}
- {"op": "repeat", "section": N}                   play it one more time right after
- {"op": "remove_section", "section": N}
"""
