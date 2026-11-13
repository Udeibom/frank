"""
Play a hummed melody back so the person can say "yes, that's my tune"
(start-from-any-input spec 02, requirement 3.4). Uses the same synth as the beat engine.

A held, soft sound is used by default. A piano strikes every note, which makes every small
mistake sound like a wrong note; a sustained sound forgives them the way a human player would.
"""

from __future__ import annotations

from app.models.song import MelodySketch
from app.services.generation import composer, renderer

# General MIDI programs that suit a hummed tune.
PREVIEW_INSTRUMENTS: dict[str, int] = {
    "flute": 73,
    "voice": 54,       # "ooh" voices
    "clarinet": 71,
    "guitar": 24,      # nylon string
    "piano": 0,
}
DEFAULT_PREVIEW = "voice"


JOIN_GAP_BEATS = 0.08   # notes closer than this are played as connected
REST_GAP_BEATS = 0.25   # a gap this long counts as a breath: the next note gets a lift


def _shaped_events(sketch: MelodySketch) -> list[composer.NoteEvent]:
    """Turn the notes into playable events: long notes carry more, phrase starts get a lift, joined notes connect."""
    events: list[composer.NoteEvent] = []
    notes = sketch.performed_notes or sketch.notes   # follow the singer's own timing when we have it
    for i, n in enumerate(notes):
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        end = n.start_beat + n.dur_beats
        joined = nxt is not None and (nxt.start_beat - end) <= JOIN_GAP_BEATS
        after_rest = i == 0 or (n.start_beat - (notes[i - 1].start_beat + notes[i - 1].dur_beats)) > REST_GAP_BEATS

        velocity = 72 + min(int(n.dur_beats * 10), 18) + (8 if after_rest else 0)
        # Connected notes touch slightly; notes before a rest end a little early so the rest is heard.
        duration = n.dur_beats * (1.04 if joined else 0.94)
        events.append(
            composer.NoteEvent(
                note=n.pitch_midi,
                start=n.start_beat,
                duration=max(duration, 0.2),
                velocity=min(velocity, 110),
            )
        )
    return events


def render_preview_audio(sketch: MelodySketch, instrument: str = DEFAULT_PREVIEW):
    """Stereo int16 audio of the melody at the sketch's own speed."""
    part = composer.Part(
        name="melody",
        preset=PREVIEW_INSTRUMENTS.get(instrument, PREVIEW_INSTRUMENTS[DEFAULT_PREVIEW]),
        is_drums=False,
        events=_shaped_events(sketch),
    )
    shown = sketch.performed_notes or sketch.notes
    end_beat = max((n.start_beat + n.dur_beats for n in shown), default=1.0) + 2.0
    with renderer.SynthSession() as synth:
        return synth.render(part, sketch.tempo_bpm, end_beat)


def render_preview_mp3(sketch: MelodySketch, instrument: str = DEFAULT_PREVIEW) -> bytes:
    return renderer.to_mp3_bytes(render_preview_audio(sketch, instrument))
