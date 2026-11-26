"""
Texture generation for the Feel Lab.

A texture is a short (8-12s), sparse, atmospheric rendering of a musical
direction — just enough to let the user feel where the song is heading. It uses
the same procedural engine as the Beat Room, with a minimal arrangement.

Each direction has a sound family (core-path spec 15, requirement 4): on 22 Nov every direction was the same
piano and soft pad, so "Try something different" could not sound different. The family comes from the song's
words and hints, or from "Try something different", which moves to one not heard yet.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.generation import theory, composer, renderer, fingerprint as fp_utils
from app.services.generation.styles import pick_style

TEXTURE_BARS = 4

# (name, sound for the keys part, sound for the soft background, the words that point at it). GM programs.
PALETTES: list[tuple[str, int, int, tuple[str, ...]]] = [
    ("piano", 0, 89, ("piano", "keys")),
    ("church", 19, 52, ("organ", "church", "choir", "worship", "gospel", "hymn", "praise")),
    ("guitar", 24, 48, ("guitar", "acoustic", "folk", "campfire", "country")),
    ("electric", 4, 94, ("electric piano", "synth", "r&b", "rnb", "lo-fi", "lofi", "neo soul", "electronic")),
    ("bells", 11, 53, ("bells", "vibraphone", "dreamy", "music box", "twinkly", "lullaby")),
    ("strings", 42, 48, ("strings", "violin", "cello", "orchestra", "orchestral", "cinematic", "film")),
]
MOVEMENTS = ("floating", "steady", "building", "driving")


def palette_for(fp: dict[str, Any]) -> int:
    """The direction's sound family: chosen explicitly, else pointed at by the song's own words and hints."""
    chosen = fp.get("texture_palette")
    if isinstance(chosen, int) and 0 <= chosen < len(PALETTES):
        return chosen
    words = " ".join(str(w).lower() for w in [*(fp.get("instrumentation_hints") or []), *(fp.get("genre_proximity") or [])])
    for i, (_, _, _, cues) in enumerate(PALETTES):
        if any(re.search(rf"\b{re.escape(c)}\b", words) for c in cues):
            return i
    return 0


DIFFERENT = re.compile(r"\b(something|quite|completely|totally|entirely|very)?\s*different\b|another (direction|one|way)|"
                       r"not (quite )?(it|right)|isn'?t (quite )?(it|right)|nope|try again|something else", re.I)


def wants_different(text: str) -> bool:
    return bool(DIFFERENT.search(text or ""))


def contrast(fp: dict[str, Any]) -> dict[str, Any]:
    """
    The changes that make the next direction clearly different from every one heard: a sound family not heard
    yet (all of them before any repeats), the other side of the energy, and another way of moving.
    Returns only the fields to update.
    """
    now = palette_for(fp)
    heard = [h for h in (fp.get("heard_palettes") or []) if isinstance(h, int)]
    heard = list(dict.fromkeys([*heard, now]))
    fresh = [i for i in range(len(PALETTES)) if i not in heard] or [i for i in range(len(PALETTES)) if i != now]
    energy = float(fp_utils.normalize(fp)["energy_level"])
    feel = fp.get("tempo_feel") if fp.get("tempo_feel") in MOVEMENTS else "steady"
    nxt_feel = MOVEMENTS[(MOVEMENTS.index(feel) + 2) % len(MOVEMENTS)]
    return {
        "texture_palette": fresh[0],
        "heard_palettes": heard,
        "energy_level": round(max(0.1, min(0.9, energy - 0.3 if energy >= 0.5 else energy + 0.3)), 2),
        "tempo_feel": nxt_feel,
    }


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
        mode=fp["mode"],
    )

    # Textures are intentionally sparse: keys + pad, drums only if energetic.
    # We cap density low so it stays atmospheric rather than a full beat.
    texture_density = min(fp["density"], 0.45)
    layers = ["keys", "pad"]
    if fp["energy_level"] >= 0.55:
        layers.append("drums")
    if fp["tempo_feel"] in ("building", "driving") and fp["energy_level"] >= 0.4:
        layers.append("arp")

    _, keys, pad, _ = PALETTES[palette_for(fp)]
    ctx = composer.SectionContext(name="intro", parts={"keys": {"preset": keys}, "pad": {"preset": pad},
                                                        "arp": {"preset": keys}}, style=pick_style(fp),
                                  tempo_feel=fp["tempo_feel"])

    parts = composer.compose_section(
        section="intro",
        progression=prog,
        bars=TEXTURE_BARS,
        energy=fp["energy_level"],
        density=texture_density,
        layers=layers,
        ctx=ctx,
    )

    total_beats = TEXTURE_BARS * 4
    stems = [renderer.render_part(p, fp["tempo_bpm"], total_beats) for p in parts]
    mix = renderer.mix_stems(stems)
    return renderer.to_wav_bytes(mix)
