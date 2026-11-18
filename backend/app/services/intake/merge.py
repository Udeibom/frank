"""
Putting what Frank learned from one input together with what it already knew
(start-from-any-input spec 02, requirement 6).

Rules:
  - What the person already settled is never changed by any later input, however sure that input is.
    A hint only fills a gap. (Requirement 6.4, decided Nov 13.)
  - When a hint disagrees with something already settled, nothing is changed; the disagreement is
    named so Frank can ask which should lead.
  - Merging the same hints again changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ENERGY_GAP = 0.4        # words and tune this far apart in energy are pulling different ways


@dataclass(frozen=True)
class Conflict:
    field: str
    settled: object       # what is already in the song's direction
    suggested: object     # what the new input suggested


def _missing(v: object) -> bool:
    return v is None or v == [] or v == ""


def merge_fingerprint(existing: Optional[dict], hints: dict) -> tuple[dict, list[str], list[Conflict]]:
    """Returns (merged direction, fields that were filled in, disagreements). `existing` is not modified."""
    merged = dict(existing or {})
    filled: list[str] = []
    conflicts: list[Conflict] = []
    for field, value in hints.items():
        if value is None:
            continue
        current = merged.get(field)
        if _missing(current):
            merged[field] = value
            filled.append(field)
        elif field == "mode" and current in ("minor", "major") and current != value:
            conflicts.append(Conflict("mode", current, value))
        elif field == "energy_level":
            try:
                if abs(float(current) - float(value)) >= ENERGY_GAP:
                    conflicts.append(Conflict("energy_level", current, value))
            except (TypeError, ValueError):
                pass
    return merged, filled, conflicts


def conflict_question(conflicts: list[Conflict], source: str = "words") -> Optional[str]:
    """
    ONE plain question about the most important disagreement, or nothing. `source` is what the new
    hints came from ("words"), the other side being what was already settled (the tune or the talk).
    """
    by_field = {c.field: c for c in conflicts}
    feel = "feel" if source.endswith("s") else "feels"         # "your words feel", "your tune feels"
    if "mode" in by_field:
        c = by_field["mode"]
        new = "heavier" if c.suggested == "minor" else "brighter"
        old = "brighter" if c.suggested == "minor" else "heavier"
        return (
            f"Your {source} {feel} {new} than the sound we've settled on so far, which feels {old}. "
            f"Which should the music lean into most: the feeling of your {source}, what we have so far, or both?"
        )
    if "energy_level" in by_field:
        c = by_field["energy_level"]
        louder = float(c.suggested) > float(c.settled)
        return (
            f"Your {source} {feel} {'bigger and more urgent' if louder else 'quieter and more hushed'} than what we've "
            f"settled on so far. Which should lead the song?"
        )
    return None
