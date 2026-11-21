"""
Real songs' chord habits (frankenstein spec 14, requirement 3.2), from styles/chord_tables.json (mined from
Chordonomicon by scripts/mine_chords.py). Frank's mood still picks the family of progressions; this orders the
family's options by how often songs in that style use them in that kind of section.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

PATH = Path(__file__).resolve().parent / "styles" / "chord_tables.json"
RANKED_SECTIONS = ("verse", "chorus", "bridge", "pre-chorus")
MIN_SONGS = 500


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(PATH.read_text()) if PATH.exists() else {}


def shares(style: str, section: str, mode: str) -> Optional[dict[str, float]]:
    t = _table()
    if not t:
        return None
    use = style if t.get("songs", {}).get(style, 0) >= MIN_SONGS else "_default"
    by_mode = (t.get("styles", {}).get(use, {}).get(section) or {}).get("minor" if mode in ("minor", "dorian") else "major")
    return by_mode or None


def ranked(options: list[list[int]], style: str, section: str, mode: str) -> Optional[list[int]]:
    """Indices into `options`, most used first (ties keep Frank's own order). None when there is no data."""
    if section not in RANKED_SECTIONS:
        return None
    s = shares(style, section, mode)
    if not s:
        return None
    return sorted(range(len(options)), key=lambda i: (-s.get(" ".join(map(str, options[i])), 0.0), i))
