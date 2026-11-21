"""
Real drummers' feel (frankenstein spec 14, requirement 3.1), from styles/grooves.json (mined from the Groove
MIDI Dataset by scripts/mine_grooves.py). Frank's patterns decide which hits play; this decides how each one is
played: a touch early or late, and how hard, the way the drummers in the dataset played that step in that style.

`feel` is the person's choice per section: -1 tighter, 0 natural, +1 looser.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

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
