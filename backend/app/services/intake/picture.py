"""
Start from a picture (frankenstein spec 14, requirement 6.6).

Two readings, kept apart so each can be checked:
- `colours`: measured from the pixels (ffmpeg shrinks the image to 24x24; no image library needed). Warm hues
  make the song warmer, light images brighter, vivid colour more energetic. Deterministic and tested.
- Gemini's look: the feeling of the picture in everyday words ("a quiet late-night drive alone"), which then goes
  through the same reading as a typed description.
The picture itself is not stored.
"""
from __future__ import annotations

import colorsys
import subprocess
from dataclasses import dataclass

import numpy as np

SIDE = 24


def pixels(image: bytes) -> np.ndarray:
    """(N, 3) RGB in 0..1 from any image format ffmpeg reads."""
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-vf", f"scale={SIDE}:{SIDE}", "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        input=image, capture_output=True, timeout=30, check=True,
    )
    arr = np.frombuffer(r.stdout, dtype=np.uint8)
    if arr.size < 3:
        raise ValueError("not an image")
    return arr[: arr.size // 3 * 3].reshape(-1, 3).astype(np.float32) / 255.0


@dataclass
class Colours:
    brightness: float       # 0 dark .. 1 light
    warmth: float           # 0 cold blue .. 1 warm orange
    energy: float           # 0 muted .. 1 vivid
    words: list[str]


def warmth_of_hue(h: float) -> float:
    """Hue (0..1 around the wheel) to warmth: orange (~0.08) warmest, blue (~0.6) coldest."""
    d = min(abs(h - 0.08), 1 - abs(h - 0.08))          # distance round the wheel from orange, 0..0.5
    return float(1.0 - d / 0.5)


def colours(px: np.ndarray) -> Colours:
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in px])
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    brightness = float(np.clip(np.mean(v) * 1.1 - 0.05, 0, 1))
    weight = s * v + 1e-6                               # grey pixels say nothing about warmth
    warm = float(np.sum([warmth_of_hue(x) for x in h] * weight) / np.sum(weight))
    colourful = float(np.mean(s * v))
    warmth = float(np.clip(0.5 + (warm - 0.5) * min(1.0, colourful * 4), 0, 1))
    energy = float(np.clip(colourful * 1.6 + np.std(v) * 0.8, 0, 1))
    words = [
        "dark" if brightness < 0.3 else "bright" if brightness > 0.7 else "dim",
        "warm" if warmth > 0.62 else "cold" if warmth < 0.38 else "soft",
        "vivid" if energy > 0.55 else "quiet" if energy < 0.25 else "gentle",
    ]
    return Colours(round(brightness, 2), round(warmth, 2), round(energy, 2), words)


def hints(c: Colours) -> dict:
    """Colour readings as direction hints, only where the picture is clear about them."""
    out: dict = {}
    if c.brightness < 0.3 or c.brightness > 0.7:
        out["brightness"] = c.brightness
    if abs(c.warmth - 0.5) > 0.12:
        out["warmth"] = c.warmth
    if c.energy < 0.25 or c.energy > 0.55:
        out["energy_level"] = round(0.2 + c.energy * 0.7, 2)
    return out


def description_from(look: dict | None, c: Colours) -> str:
    """The words the description reader gets: Gemini's feeling first, the measured colours always."""
    parts = []
    if look and look.get("feeling"):
        parts.append(f"It should feel like {look['feeling'].rstrip('.')}.")
    if look and look.get("words"):
        parts.append("It feels " + ", ".join(look["words"][:5]) + ".")
    if look and look.get("movement"):
        parts.append(f"It's {look['movement']}.")
    parts.append(f"The picture is {c.words[0]}, {c.words[1]} and {c.words[2]}.")
    return " ".join(parts)
