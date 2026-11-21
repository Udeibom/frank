"""
Words people use about music, measured (frankenstein spec 14, requirement 9.4): styles/feeling_words.json, mined
from the Song Describer captions by data/mining/song_describer/mine.py. "dreamy" in a caption came with music that
measures slower, darker and quieter than average; "upbeat" with faster and busier.

`hints(text)` turns the feeling words in a description into gentle direction hints, used only to fill what the
model reading the description left open. Never stronger than the evidence: the average of the words found,
scaled down, around the middle of each range.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "generation" / "styles" / "feeling_words.json"
STRENGTH = 0.18            # one standard unit moves a 0..1 direction value by this much
MIN_RECORDINGS = 8


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(PATH.read_text()) if PATH.exists() else {}


MIN_AGREEMENT = 0.5       # MTG-Jamendo mood tags on the same recordings must point the same way (requirement 9.5)


def trusted(word: str) -> bool:
    t = _table()
    row = t.get("words", {}).get(word)
    if not row or row.get("recordings", 0) < MIN_RECORDINGS:
        return False
    check = t.get("mood_check", {}).get(word)
    return check is None or check["agreement"] >= MIN_AGREEMENT


def words_in(text: str) -> list[str]:
    low = (text or "").lower()
    return [w for w in _table().get("words", {}) if trusted(w) and re.search(rf"\b{re.escape(w)}\b", low)]


def hints(text: str) -> dict:
    t = _table()
    found = words_in(text)
    if not found:
        return {}
    rows = [t["words"][w] for w in found]
    avg = {k: sum(r[k] for r in rows) / len(rows) for k in ("tempo", "brightness", "busyness", "loudness")}
    clamp = lambda x: round(max(0.05, min(0.95, x)), 2)  # noqa: E731
    out = {
        "brightness": clamp(0.5 + STRENGTH * avg["brightness"]),
        "density": clamp(0.5 + STRENGTH * avg["busyness"]),
        "energy_level": clamp(0.5 + STRENGTH * (avg["loudness"] + avg["busyness"]) / 2),
    }
    # No speed from this table: the measured tempo did not follow how people hear speed ("slow" captions measured
    # slightly faster than average, 21 Nov run), so the speed stays with the model and the person.
    return out
