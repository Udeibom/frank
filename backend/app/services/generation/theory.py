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
    "minor_sad":      [[0, 5, 2, 6], [0, 3, 6, 4], [0, 2, 5, 6], [0, 6, 5, 3]],   # i-VI-III-VII, i-iv-VII-v, i-III-VI-VII, i-VII-VI-iv
    "minor_tense":    [[0, 1, 4, 0], [0, 6, 3, 4], [0, 3, 0, 4], [0, 5, 1, 4]],   # i-ii-v-i, i-VII-iv-v, i-iv-i-v, i-VI-ii-v
    "minor_driving":  [[0, 6, 5, 4], [0, 0, 5, 6], [0, 2, 6, 5], [0, 5, 6, 0]],   # i-VII-VI-v, i-i-VI-VII, i-III-VII-VI, i-VI-VII-i
    "minor_building": [[0, 3, 4, 0], [0, 6, 4, 0], [0, 3, 6, 4], [0, 5, 4, 0]],   # i-iv-v-i, i-VII-v-i, i-iv-VII-v, i-VI-v-i
    "dorian_sad":     [[0, 5, 2, 6], [0, 3, 6, 5], [0, 2, 4, 6], [0, 6, 5, 4]],   # i-VI-III-VII with the Dorian lift
    "dorian_warm":    [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 0], [4, 5, 0, 3]],   # i-IV-V-iv and friends
    "dorian_driving": [[0, 6, 5, 4], [0, 4, 6, 5], [0, 2, 6, 4], [0, 5, 4, 6]],   # i-VII-VI-v, i-IV-VII-VI
    "dorian_building":[[0, 3, 4, 0], [0, 4, 3, 0], [0, 6, 4, 3], [0, 5, 4, 0]],   # i-iv-v-i, i-IV-iv-i
    # major-key progressions
    "major_warm":     [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 0, 4], [5, 3, 0, 4]],   # I-V-vi-IV, I-vi-IV-V, I-IV-I-V, vi-IV-I-V
    "major_bright":   [[0, 3, 4, 0], [0, 4, 0, 3], [0, 5, 3, 4], [0, 4, 5, 3]],   # I-IV-V-I, I-V-I-IV, I-vi-IV-V, I-V-vi-IV
    "major_floating": [[0, 3, 5, 4], [0, 2, 3, 4], [0, 4, 5, 3], [3, 0, 4, 5]],   # I-IV-vi-V, I-iii-IV-V, I-V-vi-IV, IV-I-V-vi
    "major_building": [[0, 5, 3, 4], [0, 3, 5, 4], [0, 4, 3, 0], [5, 3, 4, 0]],   # I-vi-IV-V, I-IV-vi-V, I-V-IV-I
    "mixolydian_warm":[[0, 4, 3, 0], [0, 3, 5, 4], [0, 5, 3, 4], [3, 4, 0, 5]],   # I-IV-bVII-I with the flat seven
    "mixolydian_bright":[[0, 3, 4, 0], [0, 4, 0, 3], [0, 5, 4, 0], [0, 3, 5, 4]], # I-IV-V-I, I-bVII-IV-I
    "mixolydian_floating":[[0, 3, 5, 4], [0, 5, 3, 5], [0, 4, 5, 3], [3, 0, 4, 5]],
    "mixolydian_driving":[[0, 6, 4, 0], [0, 4, 6, 5], [0, 5, 6, 4], [0, 6, 5, 4]],
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


def chord_for_degree(root: int, mode: str, degree: int, octave: int = 3, seventh: bool = False) -> list[int]:
    """A triad on the given scale degree, plus the seventh above it when asked. Stays inside the key."""
    intervals = SCALE_INTERVALS.get(mode, SCALE_INTERVALS["minor"])
    n = len(intervals)
    base = 12 * (octave + 1) + root
    steps = (0, 2, 4, 6) if seventh else (0, 2, 4)
    out = []
    for step in steps:
        idx = degree + step
        out.append(base + intervals[idx % n] + (idx // n) * 12)
    return out


def _spread(notes: list[int]) -> int:
    return max(notes) - min(notes)


def _movement(prev: list[int], new: list[int]) -> float:
    """How far the voices have to travel: each new note to its nearest old note, plus the centre shifting."""
    near = sum(min(abs(n - p) for p in prev) for n in new)
    return near + 0.5 * abs(sum(new) / len(new) - sum(prev) / len(prev))


def _arrangements(chord: list[int]) -> list[list[int]]:
    """Every way of playing this chord: each inversion, in a few octaves."""
    out = []
    notes = sorted(chord)
    for _ in range(len(notes)):
        for shift in (-12, 0, 12):
            out.append(sorted(n + shift for n in notes))
        notes = sorted(notes[1:] + [notes[0] + 12])   # next inversion
    return out


def voice_lead(chords: list[list[int]], centre: int = 60) -> list[list[int]]:
    """
    Re-voice a chord sequence so it moves smoothly, as a keyboard player would: each chord keeps its
    notes (same pitch classes) but takes the inversion and octave nearest the one before it, and the
    whole thing stays around `centre` so it neither climbs nor sinks over the progression.
    """
    voiced: list[list[int]] = []
    for chord in chords:
        options = [o for o in _arrangements(chord) if abs(sum(o) / len(o) - centre) <= 7 and _spread(o) <= 16]
        options = options or _arrangements(chord)
        if not voiced:
            best = min(options, key=lambda o: abs(sum(o) / len(o) - centre))
        else:
            best = min(options, key=lambda o: _movement(voiced[-1], o))
        voiced.append(best)
    return voiced


def choose_progression_family(mode: str, energy: float, tempo_feel: str) -> str:
    """
    Pick a progression family from the mood. This is an explicit, explainable
    mapping — not a black box. Energy is 0..1.
    """
    if tempo_feel == "building":
        return f"{mode}_building" if f"{mode}_building" in PROGRESSIONS else (
            "minor_building" if mode in ("minor", "dorian") else "major_building"
        )
    if mode in ("minor", "dorian"):
        if tempo_feel == "driving" or energy >= 0.6:
            return f"{mode}_driving"
        if energy <= 0.35:
            return f"{mode}_sad"
        if mode == "dorian":
            return "dorian_warm"
        return "minor_tense"
    if mode == "mixolydian":
        if tempo_feel == "driving" or energy >= 0.6:
            return "mixolydian_driving"
        if tempo_feel == "floating":
            return "mixolydian_floating"
        if energy >= 0.65:
            return "mixolydian_bright"
        return "mixolydian_warm"
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
    extension: float = 0.0,
    seed: int = 0,
    voice: bool = True,
    mode: str | None = None,
) -> dict:
    """
    The main entry point. Given a key and mood, produce a concrete chord progression as MIDI note
    lists, plus the scale for melodies and the bass notes.

    `extension` is the chance (0..1) that a chord gets its seventh, decided per chord from `seed`, so
    the same seed always gives the same chords. `voice` makes the chords move smoothly. `mode` lets the
    fingerprint's mode colour the chords when it differs from the key's default reading.

    Returns a dict the composer consumes. The keys root, mode, family, degrees, chords, scale and
    bass_notes are the ones earlier code relied on; chord_pcs and sevenths are new.
    """
    from app.services.generation.rng import rng_for

    root, key_mode = parse_key(key)
    mode = mode if mode in SCALE_INTERVALS else key_mode
    family = choose_progression_family(mode, energy, tempo_feel)
    options = PROGRESSIONS[family]
    degrees = options[variant % len(options)]

    sevenths = [rng_for(seed, "seventh", i, d).random() < extension for i, d in enumerate(degrees)]
    raw = [chord_for_degree(root, mode, d, 3, sev) for d, sev in zip(degrees, sevenths)]
    chords = voice_lead(raw) if voice else raw

    return {
        "root": root,
        "mode": mode,
        "family": family,
        "degrees": degrees,
        "chords": chords,                                   # list of [midi, midi, midi(, midi)]
        "chord_pcs": [sorted({n % 12 for n in c}) for c in chords],
        "tones": [[n % 12 for n in c] for c in raw],           # per chord: root, third, fifth (and seventh) as pitch classes, before re-voicing
        "sevenths": sevenths,
        "scale": scale_notes(root, mode, 4),                # for melody
        "bass_notes": [triad_for_degree(root, mode, d, octave=2)[0] for d in degrees],
    }
