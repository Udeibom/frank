"""
Music theory for Frank's procedural engine.

This module turns a musical intention (key, mode, mood) into concrete musical
material: scales, chord progressions, and voicings — expressed as MIDI note
numbers. It makes explicit, musically-grounded choices so that everything
downstream (bass, melody, drums) is coherent and controllable.

No neural models. No randomness that can't be reasoned about. Just music theory.
"""

from __future__ import annotations

# ─────────────────────────────────────────────
# Notes and scales
# ─────────────────────────────────────────────

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Interval patterns (semitones from the root) for the modes Frank uses.
SCALE_INTERVALS: dict[str, list[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],      # Ionian — bright, resolved
    "minor": [0, 2, 3, 5, 7, 8, 10],      # Aeolian — the natural minor, melancholic
    "dorian": [0, 2, 3, 5, 7, 9, 10],     # minor with a raised 6th — soulful, hopeful-sad
    "mixolydian": [0, 2, 4, 5, 7, 9, 10], # major with a flat 7th — groovy, bluesy
}

# Roman-numeral chord scale degrees (0-indexed) for common progressions,
# chosen per mood. Each entry is a list of scale-degree roots.
PROGRESSIONS: dict[str, list[list[int]]] = {
    # minor-key progressions
    "minor_sad":      [[0, 5, 2, 6], [0, 3, 6, 4]],       # i-VI-III-VII, i-iv-VII-v
    "minor_tense":    [[0, 1, 4, 0], [0, 6, 3, 4]],       # i-ii-v-i
    "minor_driving":  [[0, 6, 5, 4], [0, 0, 5, 6]],       # i-VII-VI-v
    # major-key progressions
    "major_warm":     [[0, 4, 5, 3], [0, 5, 3, 4]],       # I-V-vi-IV (the "pop" progression)
    "major_bright":   [[0, 3, 4, 0], [0, 4, 0, 3]],       # I-IV-V-I
    "major_floating": [[0, 3, 5, 4], [0, 2, 3, 4]],       # I-IV-vi-V
}


def note_name_to_pitch_class(name: str) -> int:
    """'C' -> 0, 'A' -> 9, 'F#' -> 6. Accepts flats too (Bb)."""
    name = name.strip()
    flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    name = flats.get(name, name)
    if name in NOTE_NAMES:
        return NOTE_NAMES.index(name)
    return 0  # default to C if unrecognised


def parse_key(key: str) -> tuple[int, str]:
    """
    Parse a key string like 'C minor' or 'F# major' into
    (root_pitch_class, mode). Falls back to C minor.
    """
    if not key:
        return 0, "minor"
    parts = key.strip().split()
    root = note_name_to_pitch_class(parts[0]) if parts else 0
    mode = "minor"
    if len(parts) > 1:
        m = parts[1].lower()
        if m in SCALE_INTERVALS:
            mode = m
        elif m == "major":
            mode = "major"
        elif m == "minor":
            mode = "minor"
    return root, mode


def scale_notes(root: int, mode: str, octave: int = 4) -> list[int]:
    """
    Return the MIDI notes of one octave of the scale starting at the given
    octave. MIDI note 60 is middle C (C4).
    """
    intervals = SCALE_INTERVALS.get(mode, SCALE_INTERVALS["minor"])
    base = 12 * (octave + 1) + root  # MIDI octave convention: C4 = 60
    return [base + i for i in intervals]


def triad_for_degree(root: int, mode: str, degree: int, octave: int = 3) -> list[int]:
    """
    Build a triad (three notes) rooted on the given scale degree.
    Stacks diatonic thirds so the chord stays within the key — this is what
    keeps the harmony coherent rather than random.
    """
    intervals = SCALE_INTERVALS.get(mode, SCALE_INTERVALS["minor"])
    n = len(intervals)
    base = 12 * (octave + 1) + root

    # A triad is scale degrees d, d+2, d+4 (root, third, fifth), with octave
    # wrapping handled by adding 12 when the index passes the top of the scale.
    chord = []
    for step in (0, 2, 4):
        idx = degree + step
        octave_shift = (idx // n) * 12
        chord.append(base + intervals[idx % n] + octave_shift)
    return chord


def choose_progression_family(mode: str, energy: float, tempo_feel: str) -> str:
    """
    Pick a progression family from the mood. This is an explicit, explainable
    mapping — not a black box. Energy is 0..1.
    """
    if mode in ("minor", "dorian"):
        if tempo_feel == "driving" or energy >= 0.6:
            return "minor_driving"
        if energy <= 0.35:
            return "minor_sad"
        return "minor_tense"
    else:  # major / mixolydian
        if tempo_feel == "floating":
            return "major_floating"
        if energy >= 0.6:
            return "major_bright"
        return "major_warm"


def build_progression(
    key: str,
    energy: float = 0.5,
    tempo_feel: str = "steady",
    variant: int = 0,
) -> dict:
    """
    The main entry point. Given a key and mood, produce a concrete chord
    progression as MIDI note lists, plus the scale for melodies/basslines.

    Returns a dict the composer layer consumes.
    """
    root, mode = parse_key(key)
    family = choose_progression_family(mode, energy, tempo_feel)
    options = PROGRESSIONS[family]
    degrees = options[variant % len(options)]

    chords = [triad_for_degree(root, mode, d) for d in degrees]

    return {
        "root": root,
        "mode": mode,
        "family": family,
        "degrees": degrees,
        "chords": chords,                       # list of [midi, midi, midi]
        "scale": scale_notes(root, mode, 4),    # for melody
        "bass_notes": [triad_for_degree(root, mode, d, octave=2)[0] for d in degrees],
    }
