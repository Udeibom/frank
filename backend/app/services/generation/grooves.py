"""
Real drummers' feel (frankenstein spec 14, requirement 3.1), from styles/grooves.json (mined from the Groove
MIDI Dataset by scripts/mine_grooves.py). Frank's patterns decide which hits play; this decides how each one is
played: a touch early or late, and how hard, the way the drummers in the dataset played that step in that style.

`feel` is the person's choice per section: -1 tighter, 0 natural, +1 looser.
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import get_settings

PATH = Path(__file__).resolve().parent / "styles" / "grooves.json"
MIN_RECORDINGS = 20
MAX_OFFSET_STEPS = 0.3            # never more than about a third of a sixteenth off the grid
FEEL_SCALE = {-1: 0.35, 0: 1.0, 1: 1.7}
ACCENT_POWER = 0.8                # how much of the drummers' accent pattern to keep


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(PATH.read_text())["styles"] if PATH.exists() else {}


def for_style(name: str) -> Optional[dict]:
    t = _table()
    entry = t.get(name)
    if not entry or entry.get("recordings", 0) < MIN_RECORDINGS:
        entry = t.get("_default")
    if not entry:
        return None
    lanes = entry["lanes"]
    # Timing relative to the downbeat kick, so a constant recording delay is not mistaken for feel.
    zero = lanes.get("kick", {}).get("offset", [0.0])[0]
    return {lane: {"offset": [o - zero for o in row["offset"]], "spread": row["spread"], "accent": row["accent"]}
            for lane, row in lanes.items()}


def _pattern(row: dict) -> dict[str, str]:
    out = {}
    for lane in ("kick", "snare", "hat", "open", "ghost"):
        raw = str(row.get(lane, ""))
        out[lane] = "".join(ch if ch in "xog." else "." for ch in raw)[:16].ljust(16, ".")
    return out


def patterns_for_style(name: str) -> dict[str, dict[str, str]]:
    entry = _table().get(name)
    if not entry or entry.get("recordings", 0) < MIN_RECORDINGS:
        entry = _table().get("_default")
    if not entry:
        return {}
    patterns = entry.get("patterns") or {}
    natural = patterns.get("natural") if isinstance(patterns, dict) else {}
    if not isinstance(natural, dict) or not natural:
        return {}
    section = natural.get("all")
    if isinstance(section, dict):
        return {"all": _pattern(section)}
    return {key: _pattern(value) for key, value in natural.items() if isinstance(value, dict)}


def pick_pattern(name: str, section: Optional[str] = None, rng=None) -> Optional[dict[str, str]]:
    patterns = patterns_for_style(name)
    if not patterns:
        return None
    row = patterns.get(section or "") or patterns.get("all")
    if isinstance(row, list):
        row = (rng or random).choice(row)
    if not isinstance(row, dict):
        return None
    return _pattern(row)


def humanize(lanes: dict[str, str], style: str, feel: int, seed: int) -> Optional[dict[str, dict[str, list[float]]]]:
    settings = get_settings()
    if not settings.groove_humanizer_enabled or not lanes:
        return None
    try:
        from app.services.remote import organs

        raw = organs.groove_humanize(lanes, style, feel, seed, timeout=settings.groove_humanizer_timeout_s)
    except Exception:
        return None
    out = {}
    for lane, row in (raw.get("lanes") or {}).items():
        offsets = [max(-0.06, min(0.06, float(v))) for v in row.get("offset", [])]
        accents = [max(0.7, min(1.4, float(v))) for v in row.get("accent", [])]
        if len(offsets) == 16 and len(accents) == 16:
            out[lane] = {"offset": offsets, "accent": accents}
    return out or None


def shape(groove: Optional[dict], lane: str, step: int, feel: int, rng, swung: bool) -> tuple[float, float]:
    """(time shift in beats, velocity factor) for one hit."""
    if not groove or lane not in groove:
        return 0.0, 1.0
    row = groove[lane]
    s = step % 16
    scale = FEEL_SCALE.get(int(feel), 1.0)
    off = row["offset"][s]
    if swung and s % 2:
        off *= 0.5                # the style already swings its off-beats; don't swing them twice
    off += rng.gauss(0.0, row["spread"][s] * 0.35) if row["spread"][s] else 0.0
    off = max(-MAX_OFFSET_STEPS, min(MAX_OFFSET_STEPS, off * scale))
    accent = row["accent"][s] ** ACCENT_POWER
    if feel < 0:
        accent = 1.0 + (accent - 1.0) * 0.6
    return off * 0.25, accent
