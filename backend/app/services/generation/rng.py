"""
Seeded randomness for the song engine (song-engine spec 04, requirement 6).

Every random choice in the engine comes from a generator built from a SEED and a few names (which
section, which part). The same seed and names always give the same music, so a beat can be rebuilt
exactly, and changing one section's seed leaves every other section untouched.
"""

from __future__ import annotations

import hashlib
import random


def derive_seed(*parts: object) -> int:
    """A 32-bit number that depends only on `parts`."""
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def rng_for(*parts: object) -> random.Random:
    """A random generator that depends only on `parts`."""
    return random.Random(derive_seed(*parts))
