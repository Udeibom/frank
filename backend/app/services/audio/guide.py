"""
The guide (sing-it spec 06, requirement 1): the song's tune played softly on a voice-like sound, in song time, so
the browser can play it together with the beat from the same position while the person sings.
Only the tune; the beat is already playing. The guide only ever plays in the headphones and is never mixed into a
take (the browser plays it; nothing on the server adds it to the vocal).
"""
from __future__ import annotations

import numpy as np

from app.services.audio.song_notes import SongNotes
from app.services.generation.composer import NoteEvent, Part
from app.services.generation.renderer import SAMPLE_RATE, TAIL_SECONDS, SynthSession

GUIDE_PRESET = 53            # General MIDI "voice oohs": sounds like singing, so it is easy to follow
GUIDE_VELOCITY = 88
GUIDE_LEVEL = 0.5            # the browser sets the level the person chooses on top of this


def render_guide(song: SongNotes) -> np.ndarray | None:
    """Stereo int16, as long as the song, with the tune wherever the song has one. None when there is no tune."""
    if not song.melody_part or not song.sections:
        return None
    total = int(song.sections[-1].end * SAMPLE_RATE) + int(TAIL_SECONDS * SAMPLE_RATE)
    out = np.zeros((total, 2), dtype=np.float32)
    starts = {s.value[0]: s.start for s in song.sections}
    ends = {s.value[0]: s.end for s in song.sections}
    with SynthSession() as synth:
        for index, events, _ in song.melody_part:
            beats = (ends[index] - starts[index]) / song.seconds_per_beat
            part = Part(name="guide", preset=GUIDE_PRESET, is_drums=False,
                        events=[NoteEvent(e.note, e.start, e.duration, GUIDE_VELOCITY) for e in events])
            audio = synth.render(part, song.bpm, beats).astype(np.float32)
            at = int(starts[index] * SAMPLE_RATE)
            n = min(audio.shape[0], total - at)
            out[at:at + n] += audio[:n]
            del audio
    peak = float(np.abs(out).max())
    if peak <= 0:
        return None
    out *= (GUIDE_LEVEL * 32767.0) / peak
    return out.astype(np.int16)
