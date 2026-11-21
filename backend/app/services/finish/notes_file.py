"""
"Download the notes" (frankenstein spec 14, requirement 8.3): the song's music as a standard MIDI file, one track
per part (drums, bass, keys, melody...), at the song's speed, so a producer, a band or any music app can pick it up
later. Built from the same score the engine renders (beat.score_of), so the file is exactly what Frank plays.
The person only ever sees "the notes"; the file type is named on the download only.
"""
from __future__ import annotations

import io

import mido

from app.services.generation import beat as beat_engine

TICKS = 480                     # per beat
DRUM_CHANNEL = 9
PART_ORDER = ["drums", "bass", "keys", "pad", "strings", "arp", "melody", "accompaniment"]
PART_NAMES = {"drums": "Drums", "bass": "Bass", "keys": "Keys", "pad": "Pad", "strings": "Strings", "arp": "Arpeggio",
              "melody": "Melody", "accompaniment": "Accompaniment"}


def track_for(part: str) -> str:
    """One track per part people recognise: one-off finale notes join their part; small touches share a track."""
    if part.startswith("finale_"):
        part = part[len("finale_"):]
    if part in ("color", "color_once", "riser", "sweep") or part.startswith("color"):
        return "touches"
    return part


PART_NAMES["touches"] = "Touches"


def notes_file(params: dict) -> bytes:
    """MIDI bytes for a beat version's params (sections, fingerprint, seed, lead)."""
    sections, fp = beat_engine.sections_from_params(params)
    seed = params.get("seed")
    seed = seed if isinstance(seed, int) else beat_engine.default_seed(fp)
    lead = beat_engine.lead_from_params(params)
    score = beat_engine.score_of(sections, fp, seed, lead)
    bpm = float(fp.get("tempo_bpm") or 90)

    starts: dict[int, float] = {}
    t = 0.0
    for s in sorted(sections, key=lambda x: x.index):
        starts[s.index] = t
        t += s.bars * 4.0

    by_part: dict[str, list[tuple[int, int, int, int]]] = {}      # name -> (start tick, end tick, note, velocity)
    presets: dict[str, int] = {}
    for (_uid, index, raw), (preset, _bars, events) in score.items():
        name = track_for(raw)
        presets.setdefault(name, preset)
        off = starts.get(index, 0.0)
        for note, start, dur, vel in events:
            a = int(round((off + start) * TICKS))
            b = max(a + 1, int(round((off + start + dur) * TICKS)))
            by_part.setdefault(name, []).append((a, b, int(note), max(1, min(127, int(vel)))))

    mid = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("track_name", name="Frank", time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    mid.tracks.append(conductor)
    # Section names as markers, so the file opens with the song's shape visible.
    markers = sorted((int(starts[s.index] * TICKS), s.label or s.name.capitalize()) for s in sections)
    last = 0
    for tick, label in markers:
        conductor.append(mido.MetaMessage("marker", text=label, time=tick - last))
        last = tick

    names = sorted(by_part, key=lambda n: (PART_ORDER.index(n) if n in PART_ORDER else 99, n))
    channel = 0
    for name in names:
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=PART_NAMES.get(name, name.capitalize()), time=0))
        if name == "drums":
            ch = DRUM_CHANNEL
        else:
            ch = channel if channel != DRUM_CHANNEL else channel + 1
            channel = ch + 1
            track.append(mido.Message("program_change", channel=ch, program=max(0, min(127, presets.get(name, 0))), time=0))
        msgs: list[tuple[int, int, mido.Message]] = []
        for a, b, note, vel in by_part[name]:
            msgs.append((a, 1, mido.Message("note_on", channel=ch, note=note, velocity=vel)))
            msgs.append((b, 0, mido.Message("note_off", channel=ch, note=note, velocity=0)))
        msgs.sort(key=lambda m: (m[0], m[1]))          # note-offs before note-ons at the same moment
        now = 0
        for tick, _, msg in msgs:
            msg.time = tick - now
            now = tick
            track.append(msg)
        mid.tracks.append(track)

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()
