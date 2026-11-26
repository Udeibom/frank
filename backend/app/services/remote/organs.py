"""
Typed wrappers for each remote organ (frankenstein spec 14, sections D and E). Every function either returns its
result or raises spaces.RemoteUnavailable with a plain reason; callers decide the fallback. Bytes in, bytes or
plain data out; temp files are always cleaned up.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.services.remote import spaces


def _with_file(which: str, api: str, data: bytes, ext: str, *extra: Any, timeout: float = 300) -> Any:
    f = spaces.audio_file(data, ext)
    try:
        return spaces.call(which, api, f, *extra, timeout=timeout)
    finally:
        spaces.cleanup(f)


# ── ears ──

def embed_audio(data: bytes, ext: str = "mp3") -> list[float]:
    return _with_file("ears", "/embed_audio", data, ext, timeout=180)["embedding"]


def embed_text(texts: list[str]) -> list[list[float]]:
    return spaces.call("ears", "/embed_text", json.dumps(texts), timeout=120)["embeddings"]


def labels(data: bytes, ext: str = "mp3") -> dict:
    return _with_file("ears", "/labels", data, ext, timeout=240)


def aesthetics(data: bytes, ext: str = "mp3") -> dict:
    return _with_file("ears", "/aesthetics", data, ext, timeout=180)


def structure(data: bytes, ext: str = "mp3") -> dict:
    return _with_file("ears", "/structure", data, ext, timeout=300)


def chords(data: bytes, ext: str = "mp3") -> list[dict]:
    return _with_file("ears", "/chords", data, ext, timeout=240)["chords"]


def separate(data: bytes, ext: str = "mp3") -> tuple[bytes, bytes]:
    f = spaces.audio_file(data, ext)
    try:
        vocal, music = spaces.call("ears", "/separate", f, timeout=420)
        return spaces.read_file(vocal), spaces.read_file(music)
    finally:
        spaces.cleanup(f)


def pitch(data: bytes, ext: str = "wav") -> dict:
    return _with_file("ears", "/pitch", data, ext, timeout=180)


def emotions(lines: list[str]) -> list[list[dict]]:
    return spaces.call("ears", "/emotions", json.dumps(lines), timeout=120)["lines"]


def match_master(target: bytes, reference: bytes, target_ext: str = "wav", ref_ext: str = "mp3") -> bytes:
    a, b = spaces.audio_file(target, target_ext), spaces.audio_file(reference, ref_ext)
    try:
        return spaces.read_file(spaces.call("ears", "/match_master", a, b, timeout=420))
    finally:
        spaces.cleanup(a, b)


def denoise(data: bytes, ext: str = "wav") -> bytes:
    f = spaces.audio_file(data, ext)
    try:
        return spaces.read_file(spaces.call("ears", "/denoise", f, timeout=420))
    finally:
        spaces.cleanup(f)


# ── hands ──

def accompany(notes: list[dict], bpm: float, beats: float) -> list[dict]:
    payload = json.dumps({"notes": notes, "bpm": bpm, "beats": beats})
    return spaces.call("hands", "/accompany", payload, timeout=360)["parts"]


def groove_humanize(lanes: dict[str, str], style: str, feel: int, seed: int, timeout: float = 180.0) -> dict:
    payload = json.dumps({"lanes": lanes, "style": style, "feel": feel, "seed": seed})
    return spaces.call("hands", "/groove_humanize", payload, timeout=timeout)


def timbre(data: bytes, instrument: str, ext: str = "wav") -> bytes:
    f = spaces.audio_file(data, ext)
    try:
        return spaces.read_file(spaces.call("hands", "/timbre", f, instrument, timeout=900))
    finally:
        spaces.cleanup(f)


def speak(text: str, voice: str = "af_heart") -> bytes:
    return spaces.read_file(spaces.call("hands", "/speak", text, voice, timeout=180))


def sing(notes: list[dict], words: list[str], bpm: float) -> bytes:
    payload = json.dumps({"notes": notes, "words": words, "bpm": bpm})
    return spaces.read_file(spaces.call("hands", "/sing", payload, timeout=600))


def ambience(prompt: str, seconds: float = 20.0) -> bytes:
    return spaces.read_file(spaces.call("hands", "/ambience", prompt, seconds, timeout=360))


def cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    x, y = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    return float(x @ y / ((np.linalg.norm(x) * np.linalg.norm(y)) + 1e-9))


def try_(fn, *args, **kwargs) -> Optional[Any]:
    """Call an organ; None when it is unavailable (the plain reason is logged by spaces.call)."""
    try:
        return fn(*args, **kwargs)
    except spaces.RemoteUnavailable:
        return None
