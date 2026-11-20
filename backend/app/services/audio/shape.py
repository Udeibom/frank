"""
The shape of a sound for the screen: loudest moment per slice, 0..1.

The browser never analyses audio, so the Feeling room asks for this. It is the same
measure the final-listen screen uses (export_runner.waveform). Textures are short, so
the answer is kept in memory for the life of the server rather than in a new column.
"""
from __future__ import annotations

import io
from typing import Optional

import soundfile as sf

from app.services.storage.signing import fetch_audio_bytes

_cache: dict[str, list[float]] = {}
_MAX_CACHED = 400


def shape_of_wav(wav_bytes: bytes) -> list[float]:
    """Waveform points for WAV bytes. An unreadable file gives an empty list, never an error."""
    from app.services.jobs.export_runner import waveform   # imported here: export_runner imports the job runners

    try:
        data, _ = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    except Exception:  # noqa: BLE001 - a picture of the sound is nice to have, never a reason to fail
        return []
    return waveform(data.T)   # (channels, samples)


def remember(texture_id: str, points: list[float]) -> None:
    if len(_cache) >= _MAX_CACHED:
        _cache.pop(next(iter(_cache)))
    _cache[texture_id] = points


def shape_of_texture(texture_id: str, audio_url: str) -> list[float]:
    """Cached waveform for a stored texture; reads and measures the file the first time."""
    hit: Optional[list[float]] = _cache.get(texture_id)
    if hit is not None:
        return hit
    points = shape_of_wav(fetch_audio_bytes(audio_url))
    if points:
        remember(texture_id, points)
    return points
