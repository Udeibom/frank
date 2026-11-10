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


def normalize(fingerprint: dict) -> dict:
    """Fill in missing fields with defaults and clamp numeric ranges to 0..1."""
    fp = {**DEFAULTS, **(fingerprint or {})}

    # Clamp the 0..1 feel parameters
    for k in ("energy_level", "density", "brightness", "warmth"):
        try:
            fp[k] = max(0.0, min(1.0, float(fp[k])))
        except (TypeError, ValueError):
            fp[k] = DEFAULTS[k]

    # Tempo sanity
    try:
        fp["tempo_bpm"] = int(fp["tempo_bpm"])
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float("inf")) — found by property-based testing.
        fp["tempo_bpm"] = DEFAULTS["tempo_bpm"]
    fp["tempo_bpm"] = max(50, min(180, fp["tempo_bpm"]))

    # Ensure key carries a mode the theory layer understands
    if not fp.get("key"):
        fp["key"] = DEFAULTS["key"]

    return fp


def texture_cache_key(fingerprint: dict) -> str:
    """
    A deterministic hash of the musical parameters that affect a texture.
    Identical parameters -> identical key -> reuse the cached texture.
    """
    fp = normalize(fingerprint)
    relevant = {
        "key": fp["key"],
        "tempo_bpm": fp["tempo_bpm"],
        "tempo_feel": fp["tempo_feel"],
        "energy_level": round(fp["energy_level"], 2),
        "density": round(fp["density"], 2),
    }
    blob = json.dumps(relevant, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
