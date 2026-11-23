"""
Which way to count a hummed speed (core-path spec 15, requirement 2.1).

A hum's notes fit a grid at one speed and equally at its half or double: the same pulse, counted differently.
On 22 Nov a slow worship hum was read at 138, so the whole song was built fast and "driving". Choosing among the
three now follows what the song is about: the person's own words first, then the feeling Frank has, then a
neutral walking pace. Changing the count never changes how the tune sounds: its notes are rescaled with it.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

SLOW_WORDS = {
    "worship", "praise", "hymn", "prayer", "pray", "praying", "lord", "god", "jesus", "holy", "worthy", "grace",
    "gentle", "slow", "slowly", "calm", "quiet", "lullaby", "soft", "ballad", "sad", "grief", "grieving", "peace",
    "peaceful", "tender", "intimate", "still", "sleep", "mourning", "lonely", "alone", "heartbreak", "hush", "breathe",
    "breath", "reflective", "devotion", "surrender", "wonder",
}
FAST_WORDS = {
    "dance", "dancing", "party", "club", "hype", "workout", "bounce", "upbeat", "fast", "jump", "rave", "energetic",
    "running", "celebrate", "celebration", "banger", "lit",
}
FEEL_CENTRE = {"floating": 70.0, "steady": 92.0, "building": 100.0, "driving": 120.0}
SLOW_CENTRE, FAST_CENTRE, NEUTRAL_CENTRE = 72.0, 124.0, 96.0
LOW, HIGH = 55.0, 165.0


def centre(text: str = "", fingerprint: Optional[dict[str, Any]] = None) -> float:
    """The speed the song's feeling points at."""
    words = re.findall(r"[a-z]+", (text or "").lower())
    slow = sum(w in SLOW_WORDS for w in words)
    fast = sum(w in FAST_WORDS for w in words)
    if slow > fast:
        return SLOW_CENTRE
    if fast > slow:
        return FAST_CENTRE
    fp = fingerprint or {}
    if fp.get("tempo_feel") in FEEL_CENTRE:
        return FEEL_CENTRE[fp["tempo_feel"]]
    energy = fp.get("energy_level")
    if isinstance(energy, (int, float)):
        return 70.0 + 60.0 * max(0.0, min(1.0, float(energy)))
    return NEUTRAL_CENTRE


def choose_factor(bpm: float, target: float) -> float:
    """0.5, 1 or 2: the count of `bpm` closest to `target`, inside the speeds Frank plays."""
    options = [f for f in (0.5, 1.0, 2.0) if LOW <= bpm * f <= HIGH] or [1.0]
    return min(options, key=lambda f: (abs(math.log2(bpm * f / target)), f != 1.0))


def recount(content: dict[str, Any], factor: float) -> dict[str, Any]:
    """The same tune counted at `factor` times the speed: beats scale by the same factor, so it sounds identical."""
    if factor == 1.0:
        return content
    out = dict(content)
    out["tempo_bpm"] = round(float(content["tempo_bpm"]) * factor, 2)
    for key in ("notes", "performed_notes"):
        if isinstance(content.get(key), list):
            out[key] = [{**n, "start_beat": round(float(n["start_beat"]) * factor, 4),
                         "dur_beats": round(float(n["dur_beats"]) * factor, 4)} for n in content[key]]
    if isinstance(content.get("grid"), (int, float)):
        out["grid"] = float(content["grid"]) * factor
    return out
