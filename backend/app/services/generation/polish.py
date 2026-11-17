"""
Polish: the per-instrument mixing chain for the song engine (song-engine spec 04, sound quality spec 05).

Raw sample-set audio is dry and flat: every instrument sits in the same place, in the same room, with
the same amount of low-end mud. A mix engineer gives each instrument its own treatment. This module
does that for each part before the parts are added together:
  - TONE: cut the low rumble an instrument does not need, trim the muddy middle, add presence.
  - SMOOTHING: a gentle compressor so notes are even and drums have punch.
  - SPACE: a small, medium or large room, kept apart per instrument so the bass stays tight and the pads
    float.
  - POSITION: where the instrument sits left to right.
Then a light "glue" pass over the whole song and a ceiling so nothing clips.

All settings are data in STRIPS. Nothing here changes a note or a section length; it only shapes audio of
the same length, so timing stays exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

SAMPLE_RATE = 44100
CEILING_DB = -1.0            # nothing in the song goes above this (matches the song's final peak level)
END_FADE_SECONDS = 0.12      # a reverb tail cut at the end of a buffer must not click


@dataclass(frozen=True)
class Strip:
    """The treatment for one kind of part."""
    highpass_hz: float = 0.0
    lowpass_hz: float = 0.0
    cuts: tuple[tuple[float, float, float], ...] = ()      # (centre Hz, gain dB, width) peak filters
    high_shelf_db: float = 0.0
    comp_threshold_db: float = 0.0                          # 0 means no smoothing
    comp_ratio: float = 2.0
    comp_attack_ms: float = 15.0
    comp_release_ms: float = 120.0
    room: float = 0.0                                       # 0 means no space
    room_wet: float = 0.0
    room_damping: float = 0.5
    echo_mix: float = 0.0                                   # tempo-synced echo, 0 means none
    pan: float = 0.0                                        # -1 left .. +1 right


STRIPS: dict[str, Strip] = {
    "drums": Strip(highpass_hz=35, cuts=((250, -2.0, 1.0),), high_shelf_db=1.0,
                   comp_threshold_db=-16, comp_ratio=3.0, comp_attack_ms=18, comp_release_ms=100,
                   room=0.18, room_wet=0.08),
    "bass": Strip(highpass_hz=30, lowpass_hz=5000, cuts=((250, -1.5, 1.0),),
                  comp_threshold_db=-20, comp_ratio=3.5, comp_attack_ms=8, comp_release_ms=120),
    "keys": Strip(highpass_hz=110, cuts=((300, -2.5, 0.9),),
                  comp_threshold_db=-22, comp_ratio=2.0, comp_attack_ms=20, comp_release_ms=150,
                  room=0.3, room_wet=0.12, room_damping=0.5, pan=-0.2),
    "melody": Strip(highpass_hz=180, cuts=((2500, 1.5, 1.0),),
                    comp_threshold_db=-20, comp_ratio=2.5, comp_attack_ms=15, comp_release_ms=140,
                    room=0.4, room_wet=0.18, echo_mix=0.12, pan=0.15),
    "pad": Strip(highpass_hz=160, lowpass_hz=10000, room=0.6, room_wet=0.30, room_damping=0.6),
    "strings": Strip(highpass_hz=140, lowpass_hz=9000, room=0.6, room_wet=0.25, room_damping=0.6, pan=-0.3),
    "arp": Strip(highpass_hz=250, room=0.35, room_wet=0.20, echo_mix=0.15, pan=0.35),
    "color": Strip(highpass_hz=200, room=0.5, room_wet=0.30, pan=0.3),
    "riser": Strip(highpass_hz=200, room=0.6, room_wet=0.30),
}
ALIASES = {
    "finale_keys": "keys", "finale_pad": "pad", "finale_bass": "bass", "finale_drums": "drums",
    "color_once": "color", "sweep": "riser",
}


def strip_for(part_name: str) -> Optional[Strip]:
    return STRIPS.get(ALIASES.get(part_name, part_name))


def _pan(audio: np.ndarray, pan: float) -> np.ndarray:
    """Equal-power placement. 0 leaves the audio untouched."""
    if abs(pan) < 1e-6:
        return audio
    angle = (pan + 1.0) * np.pi / 4.0
    left, right = float(np.cos(angle)) * np.sqrt(2.0), float(np.sin(angle)) * np.sqrt(2.0)
    out = audio.copy()
    out[:, 0] *= left
    out[:, 1] *= right
    return out


def treat_part(name: str, audio: np.ndarray, bpm: float) -> np.ndarray:
    """
    Treat one part. `audio` is float32 stereo shaped (samples, 2) on the int16 scale; the same shape and
    scale come back. Parts with no strip are returned untouched.
    """
    strip = strip_for(name)
    if strip is None or audio.size == 0:
        return audio
    from pedalboard import (
        Compressor, Delay, HighpassFilter, HighShelfFilter, LowpassFilter, PeakFilter, Pedalboard, Reverb,
    )

    board = Pedalboard([])
    if strip.highpass_hz:
        board.append(HighpassFilter(cutoff_frequency_hz=strip.highpass_hz))
    if strip.lowpass_hz:
        board.append(LowpassFilter(cutoff_frequency_hz=strip.lowpass_hz))
    for centre, gain, width in strip.cuts:
        board.append(PeakFilter(cutoff_frequency_hz=centre, gain_db=gain, q=width))
    if strip.high_shelf_db:
        board.append(HighShelfFilter(cutoff_frequency_hz=8000.0, gain_db=strip.high_shelf_db))
    if strip.comp_threshold_db:
        board.append(Compressor(threshold_db=strip.comp_threshold_db, ratio=strip.comp_ratio,
                                attack_ms=strip.comp_attack_ms, release_ms=strip.comp_release_ms))
    if strip.echo_mix:
        beat = 60.0 / max(bpm, 1.0)
        board.append(Delay(delay_seconds=min(1.0, beat * 0.75), feedback=0.25, mix=strip.echo_mix))
    if strip.room:
        board.append(Reverb(room_size=strip.room, damping=strip.room_damping, wet_level=strip.room_wet,
                            dry_level=1.0 - strip.room_wet * 0.5, width=1.0))
    x = (audio.T / 32768.0).astype(np.float32)
    y = board(x, SAMPLE_RATE).T * 32768.0
    fade = min(int(END_FADE_SECONDS * SAMPLE_RATE), y.shape[0])
    if fade > 0:
        y[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
    return _pan(y.astype(np.float32), strip.pan)


def treat_song(song: np.ndarray) -> np.ndarray:
    """A light glue pass over the whole song, then a ceiling. Same shape and scale in and out."""
    if song.size == 0:
        return song
    from pedalboard import Compressor, Limiter, Pedalboard

    board = Pedalboard([
        Compressor(threshold_db=-14, ratio=1.8, attack_ms=30, release_ms=200),
        Limiter(threshold_db=CEILING_DB, release_ms=120),
    ])
    process_in_place(board, song)
    # The limiter reacts a moment after a sudden peak, so a rare sample can get past it. Hold the ceiling.
    ceiling = 32768.0 * 10.0 ** (CEILING_DB / 20.0)
    np.clip(song, -ceiling, ceiling, out=song)
    return song


CHUNK_SECONDS = 5.0


def process_in_place(board, song: np.ndarray) -> None:
    """
    Run a pedalboard chain over a float32 (samples, 2) buffer on the int16 scale, a few seconds at a time,
    writing back into the same buffer. The chain keeps its state between chunks (reset=False), so the result
    matches one long pass while memory stays at one chunk instead of several copies of the whole song.
    """
    if song.dtype != np.float32:
        raise TypeError("process_in_place needs a float32 buffer")
    step = int(CHUNK_SECONDS * SAMPLE_RATE)
    board.reset()
    for start in range(0, song.shape[0], step):
        end = min(start + step, song.shape[0])
        x = np.ascontiguousarray(song[start:end].T) / np.float32(32768.0)
        y = board(x, SAMPLE_RATE, reset=False)
        song[start:start + y.shape[1]] = y.T * np.float32(32768.0)
