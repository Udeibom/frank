"""
Recorded instruments (frankenstein spec 14, requirement 3.5): the piano, strings, bass, harp, woodwinds and brass
are played from real recordings (Versilian Studios VSCO-2 CE, CC0) through sfizz, instead of the SoundFont.

`render(part, bpm, total_beats)` returns exactly what renderer.SynthSession.render returns (int16 stereo, the
section plus the ringing tail), so the engine does not know which instrument played. Anything unexpected
(sfizz missing, samples missing, a crash) returns None and FluidSynth plays it as before.

Level: each instrument is calibrated once per process against the SoundFont on the same chord, so swapping the
sound never changes the mix balance the engine was tuned for. sfizz streams samples from disk, so memory stays low.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from app.config import get_settings

log = logging.getLogger("frank.sampled")

SAMPLE_RATE = 44100
PART_ALIASES = {"finale_keys": "keys", "finale_pad": "pad", "finale_bass": "bass",
                "finale_strings": "strings", "accompaniment": "melody", "color": "melody",
                "color_once": "melody"}
INSTRUMENTS = {
    "keys": {p: ("VSUpright1.sfz", "UprightPiano.sfz") for p in range(0, 4)},
    "bass": {p: ("ContrabassSusVB.sfz",) for p in (32, 33, 34)},
    "melody": {56: ("TrumpetSus.sfz",), 60: ("FHornSus.sfz",), 65: ("OboeSusVib.sfz",),
               68: ("FHornSus.sfz",), 73: ("FluteSusVib.sfz",), 74: ("FluteSusVib.sfz",)},
    "pad": {48: ("ViolinEnsSusVib.sfz",), 49: ("ViolaEnsSusVib.sfz", "ViolinEnsSusVib.sfz"),
            89: ("ViolinEnsSusVib-Quiet.sfz", "ViolinEnsSusVib.sfz"),
            90: ("ViolaEnsSusVib-Quiet.sfz", "ViolaEnsSusVib.sfz"),
            91: ("ViolinEnsSusVib-Quiet.sfz", "ViolinEnsSusVib.sfz")},
    "strings": {48: ("ViolinEnsSusVib.sfz",), 49: ("ViolaEnsSusVib.sfz", "ViolinEnsSusVib.sfz"),
                50: ("CelloEnsSusVib.sfz", "ViolinEnsSusVib.sfz"),
                51: ("ContrabassSusVB.sfz", "CelloEnsSusVib.sfz"),
                52: ("ViolinEnsSusVib.sfz",)},
    "arp": {10: ("Glockenspiel.sfz",), 11: ("Glockenspiel.sfz",), 12: ("Marimba.sfz",),
            13: ("Xylophone.sfz",), 46: ("Harp.sfz",)},
}
ORGAN_FOR = {name: "samples" for name in INSTRUMENTS}


def binary() -> Optional[str]:
    return shutil.which("sfizz_render")


def sfz_dir() -> Path:
    p = Path(get_settings().sfz_dir)
    return p if p.is_absolute() else Path(__file__).resolve().parents[3] / p


def enabled() -> bool:
    return os.environ.get("SAMPLED_INSTRUMENTS", "on") != "off" and binary() is not None


def canonical_part(name: str) -> str:
    return PART_ALIASES.get(name, name)


def instrument_for(part) -> Optional[Path]:
    name = canonical_part(part.name)
    table = INSTRUMENTS.get(name)
    if part.is_drums or not table:
        return None
    names = table.get(int(part.preset))
    if not names:
        return None
    for candidate in names:
        path = sfz_dir() / candidate
        if path.exists():
            return path
    return None


def _midi(events: list[tuple[int, float, float, int]], bpm: float) -> bytes:
    import mido

    tpb = 960
    mid = mido.MidiFile(type=0, ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    msgs = []
    for note, start, dur, vel in events:
        a = int(round(start * tpb))
        b = max(a + 1, int(round((start + dur) * tpb)))
        msgs.append((a, 1, mido.Message("note_on", note=int(note), velocity=max(1, min(127, int(vel))))))
        msgs.append((b, 0, mido.Message("note_off", note=int(note), velocity=0)))
    msgs.sort(key=lambda m: (m[0], m[1]))
    now = 0
    for t, _, m in msgs:
        m.time = t - now
        now = t
        tr.append(m)
    mid.tracks.append(tr)
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


@lru_cache(maxsize=16)
def _render_bytes(sfz: str, midi: bytes, bpm: float) -> bytes:
    with tempfile.TemporaryDirectory(prefix="frank-sfz-") as d:
        mid, wav = Path(d) / "in.mid", Path(d) / "out.wav"
        mid.write_bytes(midi)
        subprocess.run([binary(), "--sfz", sfz, "--midi", str(mid), "--wav", str(wav),
                        "--samplerate", str(SAMPLE_RATE), "--quality", "2"],
                       capture_output=True, timeout=180, check=True)
        return wav.read_bytes()


def _run(sfz: Path, events: list[tuple[int, float, float, int]], bpm: float) -> np.ndarray:
    """float32 (samples, 2) from sfizz_render."""
    wav_bytes = _render_bytes(str(sfz), _midi(events, bpm), bpm)
    audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio[:, :2]


CAL_CHORD = [(n, 0.0, 3.0, 90) for n in (48, 60, 64, 67)] + [(n, 4.0, 3.0, 70) for n in (55, 62, 65, 71)]


@lru_cache(maxsize=4)
def gain_for(part_name: str, preset: int) -> float:
    """Ratio that makes the recorded instrument as loud as the SoundFont one on the same chord."""
    from app.services.generation.composer import NoteEvent, Part
    from app.services.generation.renderer import SynthSession

    part = Part(canonical_part(part_name), preset, False, [NoteEvent(n, s, d, v) for n, s, d, v in CAL_CHORD])
    with SynthSession(sampled=False) as synth:
        ref = synth.render(part, 90.0, 8.0).astype(np.float32)
    rec = _run(instrument_for(part), CAL_CHORD, 90.0) * 32767.0
    r_ref = float(np.sqrt(np.mean(ref ** 2))) or 1.0
    r_rec = float(np.sqrt(np.mean(rec ** 2))) or 1.0
    return float(np.clip(r_ref / r_rec, 0.05, 20.0))


def render(part, bpm: float, total_beats: float, tail_seconds: float) -> Optional[np.ndarray]:
    """The part from recordings, or None to let FluidSynth play it."""
    if not enabled() or not part.events:
        return None
    sfz = instrument_for(part)
    if sfz is None:
        return None
    try:
        events = [(e.note, e.start, e.duration, e.velocity) for e in part.events]
        audio = _run(sfz, events, bpm) * 32767.0 * gain_for(part.name, part.preset)
        total = int(round(total_beats * 60.0 / bpm * SAMPLE_RATE)) + int(tail_seconds * SAMPLE_RATE)
        out = np.zeros((total, 2), dtype=np.float32)
        n = min(total, audio.shape[0])
        out[:n] = audio[:n]
        np.clip(out, -32768, 32767, out=out)
        return out.astype(np.int16)
    except Exception:  # noqa: BLE001
        log.warning("recorded instrument failed for %s; using the SoundFont", part.name, exc_info=True)
        return None
