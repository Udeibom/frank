"""
Taste memory rules (spec 09, design "Promotion"). Pure: no database, so every rule is property-tested.

A preference is stated only after repeated evidence: at least PROMOTE_SIGNALS signals the same way, across at least
PROMOTE_SONGS songs, and more for it than against. Two contradicting signals in a row retire it. Something the person
says about themselves becomes a preference at once ("I hate autotune").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

PROMOTE_SIGNALS = 3
PROMOTE_SONGS = 2
RETIRE_AFTER = 2

# topic -> (specialist, sentence when the direction is +1, sentence when it is -1). Plain words only.
TOPICS: dict[str, tuple[str, str, str]] = {
    "verse_density": ("beat_maker", "You usually like the verses fuller.", "You usually like the verses stripped back."),
    "chorus_size": ("beat_maker", "You like choruses that really lift.", "You like choruses that stay close to the verses."),
    "busy_drums": ("beat_maker", "You like busy, lively drums.", "You like simple, steady drums."),
    "new_tune_ideas": ("beat_maker", "You like trying new tune ideas.", "You like keeping the tune you have."),
    "warm_sounds": ("beat_maker", "You lean toward warm, soft sounds.", "You lean toward brighter, sharper sounds."),
    "brightness": ("producer", "You like songs that feel bright and open.", "You like songs that feel dark and close."),
    "energy": ("producer", "You like songs with a lot of energy.", "You like calm, gentle songs."),
    "speed": ("producer", "You like faster songs.", "You like slower songs."),
    "vocal_level": ("mix_engineer", "You like your voice right up front.", "You like your voice sitting inside the music."),
    "vocal_space": ("mix_engineer", "You like a lot of space around your voice.", "You like your voice close and dry."),
    "vocal_clarity": ("mix_engineer", "You like your voice crisp and clear.", "You like your voice soft and smooth."),
    "autotune_amount": ("vocal_producer", "You like your voice tuned firmly.", "You don't like your voice sounding tuned."),
    "lyric_cliche": ("songwriter", "You're happy with familiar phrases.", "You don't like clichés in your words."),
    "other": ("producer", "", ""),
}

# words a person uses about themselves -> topic, direction when they say they LIKE it
SELF_WORDS: list[tuple[str, str, int]] = [
    (r"auto-?tune|tuned voice|robot voice", "autotune_amount", 1), (r"clich", "lyric_cliche", 1),
    (r"echo|reverb|space|big room", "vocal_space", 1), (r"stripped|minimal|simple|sparse", "verse_density", -1),
    (r"busy|full|big sound|lots going on", "verse_density", 1), (r"bright", "brightness", 1), (r"dark|moody", "brightness", -1),
    (r"fast|upbeat", "speed", 1), (r"slow|ballad", "speed", -1), (r"warm", "warm_sounds", 1), (r"loud|energy|hype", "energy", 1),
    (r"calm|chill|gentle|soft", "energy", -1), (r"drums", "busy_drums", 1),
]
SELF_PATTERN = re.compile(r"\bi\s+(really\s+|do\s+|kind of\s+|kinda\s+)?(hate|love|like|dislike|don't like|do not like|can't stand|cannot stand|prefer|adore)\s+(.{3,80})", re.I)
NEGATIVE = {"hate", "dislike", "don't like", "do not like", "can't stand", "cannot stand"}


@dataclass(frozen=True)
class Signal:
    topic: str
    direction: int
    project_id: Optional[str]
    order: int = 0                      # older first


@dataclass
class Outcome:
    status: str                         # "active" | "retired" | "none"
    direction: int = 0
    strength: float = 0.0
    statement: str = ""


def statement_for(topic: str, direction: int) -> str:
    _, up, down = TOPICS.get(topic, TOPICS["other"])
    return up if direction > 0 else down


def evaluate(signals: list[Signal], current: Optional[Outcome] = None) -> Outcome:
    """What the evidence for ONE topic says now. `current` is the stored preference, if any."""
    if not signals:
        return current or Outcome("none")
    ordered = sorted(signals, key=lambda s: s.order)
    if current and current.status == "active":
        tail = ordered[-RETIRE_AFTER:]
        if len(tail) == RETIRE_AFTER and all(s.direction == -current.direction for s in tail):
            return Outcome("retired", current.direction, 0.0, current.statement)
    best: Optional[Outcome] = None
    for d in (1, -1):
        same = [s for s in ordered if s.direction == d]
        songs = {s.project_id for s in same if s.project_id}
        against = len(ordered) - len(same)
        if len(same) >= PROMOTE_SIGNALS and len(songs) >= PROMOTE_SONGS and len(same) > against:
            strength = round((len(same) - against) / len(ordered), 3)
            best = Outcome("active", d, strength, statement_for(signals[0].topic, d))
    if best and signals[0].topic != "other":
        if current and current.status == "retired" and current.direction == best.direction:
            # a retired preference only comes back on fresh evidence after it was retired
            fresh = [s for s in ordered[-PROMOTE_SIGNALS:] if s.direction == best.direction]
            if len(fresh) < PROMOTE_SIGNALS:
                return current
        return best
    if current and current.status == "active":
        # still supported? weaken it as contradictions come in
        same = sum(s.direction == current.direction for s in ordered)
        return Outcome("active", current.direction, round(max(0.0, (2 * same - len(ordered)) / len(ordered)), 3), current.statement)
    return current or Outcome("none")


def from_self(text: str) -> Optional[tuple[str, int, str]]:
    """'I hate autotune' -> (topic, direction, their own words). None when it is not about their taste."""
    m = SELF_PATTERN.search(text)
    if not m:
        return None
    verb, what = m.group(2).lower(), m.group(3).strip().rstrip(".!?")
    liked = 1 if verb not in NEGATIVE else -1
    for pattern, topic, d in SELF_WORDS:
        if re.search(pattern, what, re.I):
            return topic, d * liked, f"You said: \u201c{m.group(0).strip().rstrip('.!?')}\u201d."
    return "other", liked, f"You said: \u201c{m.group(0).strip().rstrip('.!?')}\u201d."


# typed beat operations and mix actions -> the taste they show when chosen
def signals_for_direction(kind: str, actions: list[dict], section_names: list[str]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for a in actions:
        if kind == "beat":
            op = a.get("op")
            idx = a.get("section")
            idx = idx if isinstance(idx, list) else ([idx] if isinstance(idx, int) else [])
            names = {section_names[i] for i in idx if 0 <= i < len(section_names)} or set(section_names)
            up = op in ("bigger", "busier", "add_part")
            down = op in ("smaller", "sparser", "remove_part")
            if (up or down) and "verse" in names and "chorus" not in names:
                out.append(("verse_density", 1 if up else -1))
            if (up or down) and "chorus" in names and "verse" not in names:
                out.append(("chorus_size", 1 if up else -1))
            if op in ("busier", "sparser") and a.get("part") == "drums":
                out.append(("busy_drums", 1 if op == "busier" else -1))
            if op == "try_another" and a.get("part") == "melody":
                out.append(("new_tune_ideas", 1))
            if op == "swap_sound" and str(a.get("sound", "")) in ("electric piano", "warm synth", "soft strings", "nylon guitar"):
                out.append(("warm_sounds", 1))
            if op == "swap_sound" and str(a.get("sound", "")) in ("bright piano", "glassy synth", "bells"):
                out.append(("warm_sounds", -1))
        else:
            t, p = a.get("type"), a.get("params") or {}
            if t == "adjust_levels" and float(p.get("vocal_delta_db", 0) or 0) != float(p.get("beat_delta_db", 0) or 0):
                out.append(("vocal_level", 1 if float(p.get("vocal_delta_db", 0) or 0) > float(p.get("beat_delta_db", 0) or 0) else -1))
            if t == "apply_effect" and p.get("target") == "vocal" and p.get("effect") == "space":
                out.append(("vocal_space", 1 if p.get("on", True) else -1))
            if t == "apply_effect" and p.get("target") == "vocal" and p.get("effect") in ("clarity", "smooth"):
                out.append(("vocal_clarity", 1 if p.get("effect") == "clarity" else -1))
    return list(dict.fromkeys(out))


def direction_score(kind: str, actions: list[dict], section_names: list[str], prefs: dict[str, int]) -> int:
    """How well a direction matches the artist's preferences (+1 per match, -1 per clash)."""
    return sum((1 if prefs[t] == d else -1) for t, d in signals_for_direction(kind, actions, section_names) if t in prefs)
