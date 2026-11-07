"""
Texture generation for the Feel Lab.

A texture is a short (8-12s), sparse, atmospheric rendering of a musical
direction — just enough to let the user feel where the song is heading. It uses
the same procedural engine as the Beat Room, with a minimal arrangement.
"""

from __future__ import annotations
from app.services.generation import theory, composer, renderer, fingerprint as fp_utils

TEXTURE_BARS = 4


def generate_texture_wav(fingerprint: dict) -> bytes:
    """
    Render a short atmospheric texture from a fingerprint. Returns WAV bytes.
    Synchronous and CPU-bound — always call this from a background job, never
    directly in a request handler.
    """
    fp = fp_utils.normalize(fingerprint)

    prog = theory.build_progression(
        key=fp["key"],
        energy=fp["energy_level"],
        tempo_feel=fp["tempo_feel"],
    )

    # Textures are intentionally sparse: keys + pad, drums only if energetic.
    # We cap density low so it stays atmospheric rather than a full beat.
    texture_density = min(fp["density"], 0.45)
    layers = ["keys", "pad"]
    if fp["energy_level"] >= 0.55:
        layers.append("drums")

    parts = composer.compose_section(
        section="intro",
        progression=prog,
        bars=TEXTURE_BARS,
        energy=fp["energy_level"],
        density=texture_density,
        layers=layers,
    )

    total_beats = TEXTURE_BARS * 4
    stems = [renderer.render_part(p, fp["tempo_bpm"], total_beats) for p in parts]
    mix = renderer.mix_stems(stems)
    return renderer.to_wav_bytes(mix)
