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


def words_in(text: str) -> list[str]:
    table = _table().get("words", {})
    low = (text or "").lower()
    return [w for w in table if re.search(rf"\b{re.escape(w)}\b", low) and table[w].get("recordings", 0) >= MIN_RECORDINGS]


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
    scale = t.get("scale", {}).get("tempo")
    if scale and abs(avg["tempo"]) >= 0.25:
        out["tempo_bpm"] = int(round(max(60, min(150, scale["mean"] + 0.6 * avg["tempo"] * scale["std"]))))
    return out
