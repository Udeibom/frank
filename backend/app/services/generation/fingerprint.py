"""
Fingerprint helpers.

The musical fingerprint (built in the Feel Lab) is the bridge between the user's
feelings and the engine's musical decisions. This module normalizes a raw
fingerprint dict into the parameters the composer/renderer need, and provides a
stable hash for caching generated textures.
"""

from __future__ import annotations
import hashlib
import json

# Sensible defaults for a fingerprint that's only partially filled in.
DEFAULTS = {
    "tempo_bpm": 90,
    "tempo_feel": "steady",
    "key": "C minor",
    "mode": "minor",
    "energy_level": 0.5,
    "density": 0.5,
    "brightness": 0.4,
    "warmth": 0.6,
    "genre_proximity": [],
         "instrumentation_hints": [],
}

TEMPO_FEELS = {"steady", "building", "floating", "driving"}


def normalize(fingerprint: dict) -> dict:
    """Fill in missing fields with defaults and clamp numeric ranges to 0..1."""
    from app.services.generation.texture import PALETTES
    from app.services.generation.theory import SCALE_INTERVALS, parse_key

    raw = fingerprint or {}
    fp = {**DEFAULTS, **raw}
    unsupported = list(fp.get("unsupported_hints") or [])
    if not isinstance(unsupported, list):
        unsupported = []

    # Clamp the 0..1 feel parameters
    for k in ("energy_level", "density", "brightness", "warmth"):
        try:
            fp[k] = max(0.0, min(1.0, float(fp[k])))
        except (TypeError, ValueError):
            fp[k] = DEFAULTS[k]

    # Tempo sanity
    try:
        # Whole numbers stay whole; a speed measured from someone's singing keeps its fraction, because 69.4
        # rounded to 69 drifts by more than a second over four minutes (core-path spec 15, requirement 8).
        v = round(float(fp["tempo_bpm"]), 2)
        if not (v == v) or v in (float("inf"), float("-inf")):
            raise ValueError
        fp["tempo_bpm"] = int(v) if v == int(v) else v
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float("inf")) — found by property-based testing.
        fp["tempo_bpm"] = DEFAULTS["tempo_bpm"]
    fp["tempo_bpm"] = max(50, min(180, fp["tempo_bpm"]))

    # Ensure key carries a mode the theory layer understands
    if not isinstance(fp.get("key"), str) or not fp["key"].strip():
        if "key" in raw:
            unsupported.append("key")
        fp["key"] = DEFAULTS["key"]

    feel = fp.get("tempo_feel")
    if feel not in TEMPO_FEELS:
        if "tempo_feel" in raw and feel is not None:
            unsupported.append(str(feel))
        fp["tempo_feel"] = DEFAULTS["tempo_feel"]

    _, key_mode = parse_key(fp["key"])
    mode = fp.get("mode")
    if "mode" in raw and mode in SCALE_INTERVALS:
        pass
    else:
        if "mode" in raw and mode is not None and mode not in SCALE_INTERVALS:
            unsupported.append(str(mode))
        mode = key_mode
    fp["mode"] = mode

    palette = fp.get("texture_palette")
    if palette is not None:
        try:
            palette = int(palette)
            if not 0 <= palette < len(PALETTES):
                raise ValueError
        except (TypeError, ValueError):
            unsupported.append("texture_palette")
            palette = None
    fp["texture_palette"] = palette
    fp["unsupported_hints"] = _unique(unsupported)

    return fp


def approved_start(fingerprint: dict | None) -> dict | None:
    start = (fingerprint or {}).get("approved_start")
    return start if isinstance(start, dict) and start.get("kind") in ("hum", "direction") else None


def with_approved_start(fingerprint: dict, start: dict) -> dict:
    return {**(fingerprint or {}), "approved_start": start}


def without_approved_start(fingerprint: dict, kind: str | None = None, source_id: str | None = None) -> dict:
    start = approved_start(fingerprint)
    if not start:
        return fingerprint
    if kind is not None and start.get("kind") != kind:
        return fingerprint
    if source_id is not None and start.get("source_id") != source_id:
        return fingerprint
    out = dict(fingerprint)
    out.pop("approved_start", None)
    return out


def _unique(values: list) -> list:
    """Keep the first mention of each unsupported hint."""
    out: list = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _palette(fp: dict) -> int:
    from app.services.generation.texture import palette_for

    return palette_for(fp)


def texture_cache_key(fingerprint: dict) -> str:
    """
    A deterministic hash of the musical parameters that affect a texture.
    Identical parameters -> identical key -> reuse the cached texture.
    """
    fp = normalize(fingerprint)
    relevant = {
        "key": fp["key"],
        "mode": fp["mode"],
        "tempo_bpm": fp["tempo_bpm"],
        "tempo_feel": fp["tempo_feel"],
        "energy_level": round(fp["energy_level"], 2),
        "density": round(fp["density"], 2),
        "warmth": round(fp["warmth"], 2),
        "brightness": round(fp["brightness"], 2),
        # The sound family it plays on (core-path spec 15, 4.1): a different direction is a different file.
        "palette": _palette(fp),
    }
    blob = json.dumps(relevant, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
