"""
Styles for the song engine (song-engine spec 04, requirement 4).

A style is DATA (styles/styles.json), not code: which instruments play, what the drums do, how busy
the bass gets, how much swing. Choosing a style from a fingerprint uses the genre words and the
instrument hints, and falls back to the mood (energy, warmth, brightness) when there are no words.

Anything the person asked for that Frank cannot do is REPORTED (`unsupported`), never silently
ignored, so Frank can say so in plain words.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

STYLES_FILE = Path(__file__).parent / "styles" / "styles.json"
PARTS = ("keys", "bass", "melody", "pad", "strings", "arp")
TIERS = ("sparse", "medium", "busy")
LANES = ("kick", "snare", "hat", "ghost", "half_kick", "half_snare", "half_hat")
LANE_CHARS = set("xog.")


@dataclass
class StyleChoice:
    """Everything the composer needs to know about the chosen style. Plain data."""

    name: str
    instruments: dict[str, int]
    drums: dict[str, str]
    half_time_below: float
    swing: float
    extension: float
    fill: float
    drum_gain: float
    keys: dict[str, list]
    bass: dict[str, list]
    extra_layers: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)   # words Frank could not act on
    own_groove: bool = False                               # the person tapped this rhythm: play it as they did


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    with open(STYLES_FILE, encoding="utf-8") as f:
        return json.load(f)


def style_names() -> list[str]:
    return [k for k in _raw() if not k.startswith("_")]


def _merged(name: str) -> dict[str, Any]:
    """The default style with the named style's differences laid on top (one level deep)."""
    raw = _raw()
    base = copy.deepcopy(raw["_default"])
    for key, value in raw[name].items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(copy.deepcopy(value))
        else:
            base[key] = copy.deepcopy(value)
    return base


def _words(values: object) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [str(v).lower().strip() for v in values if str(v).strip()]


def _unit(v: object, default: float) -> float:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if x != x or x in (float("inf"), float("-inf")):
        return default
    return max(0.0, min(1.0, x))


def _match_genres(genres: list[str]) -> tuple[Optional[str], list[str]]:
    """Best style for the genre words (earlier words count for more), and the words that matched nothing."""
    scores: dict[str, int] = {n: 0 for n in style_names()}
    unmatched: list[str] = []
    for position, genre in enumerate(genres):
        weight = max(1, 3 - position)
        hit = False
        for name in scores:
            if any(k in genre for k in _raw()[name].get("keywords", [])):
                scores[name] += weight
                hit = True
        if not hit:
            unmatched.append(genre)
    best = max(scores.values(), default=0)
    if best == 0:
        return None, unmatched
    # Ties go to the style listed first in the file, so the choice never depends on dict order tricks.
    return next(n for n in style_names() if scores[n] == best), unmatched


def _closest_by_mood(energy: float, warmth: float, brightness: float) -> str:
    def distance(name: str) -> float:
        m = _raw()[name].get("mood", {})
        return (
            (energy - m.get("energy", 0.5)) ** 2
            + (warmth - m.get("warmth", 0.5)) ** 2
            + (brightness - m.get("brightness", 0.5)) ** 2
        )

    return min(style_names(), key=distance)


def pick_style(fp: dict) -> StyleChoice:
    """Choose and fill in a style from a fingerprint. Deterministic."""
    energy = _unit(fp.get("energy_level"), 0.5)
    warmth = _unit(fp.get("warmth"), 0.6)
    brightness = _unit(fp.get("brightness"), 0.4)
    genres = _words(fp.get("genre_proximity"))
    hints = _words(fp.get("instrumentation_hints"))

    name, unmatched_genres = _match_genres(genres)
    if name is None:
        name = _closest_by_mood(energy, warmth, brightness)
    data = _merged(name)

    instruments: dict[str, int] = {}
    for part in PARTS:
        value = data["instruments"][part]
        if isinstance(value, list):                     # [warm choice, bright choice]
            value = value[0] if warmth >= brightness else value[1]
        instruments[part] = int(value)

    drum_gain = float(data["drum_gain"])
    extra_layers: list[str] = list(data.get("extra_layers", []))
    unsupported: list[str] = list(unmatched_genres)

    for hint in hints:
        rule = next((r for r in _raw()["_hints"] if any(w in hint for w in r["words"])), None)
        if rule is None:
            unsupported.append(hint)
            continue
        for part, program in rule.get("instruments", {}).items():
            instruments[part] = int(program)
        drum_gain *= float(rule.get("drum_gain_mult", 1.0))
        for layer in rule.get("layers", []):
            if layer not in extra_layers:
                extra_layers.append(layer)

    return StyleChoice(
        name=name,
        instruments=instruments,
        drums=dict(data["drums"]),
        half_time_below=float(data["half_time_below"]),
        swing=float(data["swing"]),
        extension=float(data["extension"]),
        fill=float(data["fill"]),
        drum_gain=max(0.3, min(1.6, drum_gain)),
        keys={t: [list(p) for p in data["keys"][t]] for t in TIERS},
        bass={t: [list(p) for p in data["bass"][t]] for t in TIERS},
        extra_layers=extra_layers,
        unsupported=unsupported,
    )


def default_choice() -> StyleChoice:
    """The style used when nothing says otherwise (a mid-mood fingerprint)."""
    return pick_style({})
