"""
Composer — turns a chord progression and a fingerprint into MIDI parts.

Each instrument (chords/keys, bass, drums, melody/pad) is composed as its own
part so it can be rendered as an independent stem. Section energy and the
fingerprint's density drive how busy each part is — this is what lets the user
later say "the bass feels too busy" and have it mean something concrete.

A "part" here is a list of note events:
    { "note": int, "start": float_beats, "duration": float_beats, "velocity": int }
Drums use General MIDI percussion note numbers on channel 9.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from app.services.generation import theory

# General MIDI percussion notes (channel 9)
KICK = 36
SNARE = 38
CLOSED_HAT = 42
OPEN_HAT = 46

# General MIDI instrument presets used per layer
INSTRUMENTS = {
    "keys": 0,       # Acoustic Grand Piano
    "epiano": 4,     # Electric Piano
    "bass": 33,      # Fingered Bass
    "pad": 89,       # Warm Pad
    "strings": 48,   # String Ensemble
    "pluck": 24,     # Nylon Guitar
}


@dataclass
class NoteEvent:
    note: int
    start: float      # in beats
    duration: float   # in beats
    velocity: int


@dataclass
class Part:
    """One instrument's notes plus which GM preset renders it."""
    name: str                       # "keys", "bass", "drums", "melody", "pad"
    preset: int                     # GM program number (ignored for drums)
    is_drums: bool
    events: list[NoteEvent] = field(default_factory=list)


def _beats_per_chord(density: float) -> float:
    """Higher density -> chords change/strum more often. Returns beats per bar event."""
    return 4.0  # one chord per 4-beat bar; rhythm within is handled per-part


def compose_chords(progression: dict, bars: int, energy: float, density: float) -> Part:
    """Chord/keys part: sustained or rhythmic chords, one chord per bar."""
    preset = INSTRUMENTS["epiano"] if energy < 0.5 else INSTRUMENTS["keys"]
    part = Part(name="keys", preset=preset, is_drums=False)
    chords = progression["chords"]

    for bar in range(bars):
        chord = chords[bar % len(chords)]
        bar_start = bar * 4.0
        velocity = 55 + int(energy * 30)

        if density < 0.4:
            # Sparse: one sustained chord per bar
            for n in chord:
                part.events.append(NoteEvent(n, bar_start, 3.8, velocity))
        else:
            # Busier: gentle rhythmic stabs on beats 1, 2.5, 4
            for beat in (0.0, 1.5, 3.0):
                for n in chord:
                    part.events.append(
                        NoteEvent(n, bar_start + beat, 1.2, velocity)
                    )
    return part


def compose_bass(progression: dict, bars: int, energy: float, density: float) -> Part:
    """Bassline: root-note driven, busier with higher density."""
    part = Part(name="bass", preset=INSTRUMENTS["bass"], is_drums=False)
    bass_notes = progression["bass_notes"]
    velocity = 70 + int(energy * 25)

    for bar in range(bars):
        root = bass_notes[bar % len(bass_notes)]
        bar_start = bar * 4.0

        if density < 0.35:
            # Whole-note root
            part.events.append(NoteEvent(root, bar_start, 3.8, velocity))
        elif density < 0.65:
            # Half notes
            part.events.append(NoteEvent(root, bar_start, 1.8, velocity))
            part.events.append(NoteEvent(root, bar_start + 2.0, 1.8, velocity))
        else:
            # Walking eighths on root + octave for drive
            for i in range(8):
                n = root if i % 2 == 0 else root + 12
                part.events.append(
                    NoteEvent(n, bar_start + i * 0.5, 0.45, velocity)
                )
    return part


def compose_drums(bars: int, energy: float, density: float) -> Part:
    """Drum pattern: kick/snare backbone plus hats scaled by energy."""
    part = Part(name="drums", preset=0, is_drums=True)

    for bar in range(bars):
        bar_start = bar * 4.0

        # Kick on 1 (and 3 when energetic)
        part.events.append(NoteEvent(KICK, bar_start + 0.0, 0.25, 100))
        if energy >= 0.4:
            part.events.append(NoteEvent(KICK, bar_start + 2.0, 0.25, 90))

        # Snare/backbeat on 2 and 4
        part.events.append(NoteEvent(SNARE, bar_start + 1.0, 0.25, 90))
        part.events.append(NoteEvent(SNARE, bar_start + 3.0, 0.25, 90))

        # Hats: sparse at low energy, eighths/sixteenths as energy rises
        if density >= 0.3:
            step = 0.5 if energy < 0.7 else 0.25
            t = 0.0
            while t < 4.0:
                vel = 55 + int(energy * 20)
                part.events.append(NoteEvent(CLOSED_HAT, bar_start + t, 0.2, vel))
                t += step
    return part


def compose_melody(progression: dict, bars: int, energy: float, density: float) -> Part:
    """A simple, singable melodic line drawn from the scale, for fuller sections."""
    part = Part(name="melody", preset=INSTRUMENTS["pluck"], is_drums=False)
    scale = progression["scale"]
    velocity = 60 + int(energy * 25)

    # Melody follows chord tones loosely: pick scale degrees near each chord root.
    for bar in range(bars):
        bar_start = bar * 4.0
        # Two to four notes per bar depending on density
        n_notes = 2 if density < 0.5 else 4
        step = 4.0 / n_notes
        for i in range(n_notes):
            # Choose a scale tone; alternate between chord tones and passing tones
            idx = (bar + i) % len(scale)
            note = scale[idx] + 12  # up an octave to sit above the chords
            part.events.append(
                NoteEvent(note, bar_start + i * step, step * 0.9, velocity)
            )
    return part


def compose_pad(progression: dict, bars: int, energy: float) -> Part:
    """A soft sustained pad for atmosphere."""
    part = Part(name="pad", preset=INSTRUMENTS["pad"], is_drums=False)
    chords = progression["chords"]
    velocity = 40 + int(energy * 15)

    for bar in range(bars):
        chord = chords[bar % len(chords)]
        bar_start = bar * 4.0
        # Pad plays the chord up an octave, fully sustained
        for n in chord:
            part.events.append(NoteEvent(n + 12, bar_start, 4.0, velocity))
    return part


# ─────────────────────────────────────────────
# Section-level composition
# ─────────────────────────────────────────────

# Which layers are present at a given energy level. Lower sections are sparser.
def layers_for_section(section: str, energy: float, density: float) -> list[str]:
    """
    Decide which parts play in a section. This is the arrangement logic:
    an intro is sparse, a chorus is full. Explicit and adjustable.
    """
    if section == "intro":
        base = ["keys", "pad"]
        if energy >= 0.5:
            base.append("drums")
        return base
    if section == "verse":
        base = ["keys", "bass", "drums"]
        if density >= 0.6:
            base.append("melody")
        return base
    if section == "chorus":
        base = ["keys", "bass", "drums", "melody", "pad"]
        return base
    if section == "bridge":
        return ["pad", "keys", "bass"]
    if section == "outro":
        return ["keys", "pad"]
    # default
    return ["keys", "bass", "drums"]


def compose_section(
    section: str,
    progression: dict,
    bars: int,
    energy: float,
    density: float,
    layers: list[str] | None = None,
) -> list[Part]:
    """
    Compose all the parts for one section. Returns a list of Parts, one per
    active layer. If `layers` is given, only those layers are composed (used
    when the user adds/removes a specific layer).
    """
    active = layers if layers is not None else layers_for_section(section, energy, density)
    parts: list[Part] = []

    if "keys" in active:
        parts.append(compose_chords(progression, bars, energy, density))
    if "bass" in active:
        parts.append(compose_bass(progression, bars, energy, density))
    if "drums" in active:
        parts.append(compose_drums(bars, energy, density))
    if "melody" in active:
        parts.append(compose_melody(progression, bars, energy, density))
    if "pad" in active:
        parts.append(compose_pad(progression, bars, energy))

    return parts
