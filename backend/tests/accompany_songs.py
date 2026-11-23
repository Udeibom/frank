"""Made-up sung songs with a known speed, bar line and sections, for the accompaniment tests (core-path spec 15, 8)."""
from __future__ import annotations

from app.services.generation.accompany import Note

# Scale steps of B minor (MIDI): a low verse line and a higher chorus line that comes back.
VERSE = [59, 61, 62, 61, 59, 57, 59, 59, 62, 64, 62, 61, 59, 61, 59, 57]
CHORUS = [66, 66, 64, 66, 69, 67, 66, 64, 66, 64, 62, 64, 66, 64, 62, 61]


def song(bpm: float = 69.0, start_s: float = 3.1, form: str = "VCVC", bars_per_section: int = 8) -> tuple[list[Note], list[tuple[str, float]]]:
    """Notes sung two per bar (on beats 1 and 3, held), sections of `bars_per_section` bars, the first bar line at
    `start_s`. Returns (notes, [(section name, start second)])."""
    beat = 60.0 / bpm
    notes: list[Note] = []
    starts: list[tuple[str, float]] = []
    bar = 0
    for letter in form:
        line = VERSE if letter == "V" else CHORUS
        starts.append(("verse" if letter == "V" else "chorus", start_s + bar * 4 * beat))
        for b in range(bars_per_section):
            for half in range(2):
                t = start_s + (bar + b) * 4 * beat + half * 2 * beat
                pitch = line[(b * 2 + half) % len(line)]
                held = 1.8 * beat if (b % 2 == 1 and half == 1) else 1.6 * beat
                notes.append(Note(t, t + held, float(pitch)))
        bar += bars_per_section
    return notes, starts
