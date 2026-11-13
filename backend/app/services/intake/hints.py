"""
What a confirmed tune may tell the rest of Frank about the song's direction
(start-from-any-input spec 02, requirement 6).

Only values Frank is confident about are passed on. A weak guess is left out, never replaced by a
default, so the person is asked instead of being given a made-up speed or key.
"""

from __future__ import annotations

from app.models.song import MelodySketch
from app.services.intake.melody import CONFIDENT


def fingerprint_hints(sketch: MelodySketch, hum_url: str | None = None) -> dict:
    hints: dict = {}
    if sketch.tempo_confidence >= CONFIDENT:
        hints["tempo_bpm"] = int(round(sketch.tempo_bpm))
    if sketch.key_confidence >= CONFIDENT:
        hints["key"] = sketch.key
        hints["mode"] = sketch.mode
    if hum_url:
        hints["hum_reference_file"] = hum_url
    return hints


def unsure_about(sketch: MelodySketch) -> list[str]:
    """What Frank could not pin down, as simple keys ("mood", "speed"), most important first.
    The screen turns these into ONE plain question; it never lists them."""
    out: list[str] = []
    if sketch.key_confidence < CONFIDENT:
        out.append("mood")
    if sketch.tempo_confidence < CONFIDENT:
        out.append("speed")
    return out
