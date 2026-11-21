"""
Hearing a reference song (frankenstein spec 14, requirement 6.2).

Local (on Render, CPU, in memory): speed, loudness, brightness, low end, busyness, the colour of its notes (key
estimate), how much it builds. Remote (frank-ears Space, when awake): CLAP embedding and words, style and mood
labels, sections and beats, chords, and its parts split apart so the voice and the music can be heard separately.

Output is a target, not a copy: feeling words, a few fingerprint hints, and plain differences from the person's
song. The audio itself is never stored (uploads) and never kept (Jamendo, which is Creative Commons and is
attributed). The founder's rule holds: nothing aims at sounding like anyone; the reference only steers the feeling.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.services.listener import dsp

log = logging.getLogger("frank.reference")

SR = 22050
MAX_SECONDS = 360
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def decode(data: bytes, ext: str = "mp3") -> np.ndarray:
    from app.services.listener.service import decode as listener_decode

    y = listener_decode(data, SR)
    return y[: MAX_SECONDS * SR]


def key_of(y: np.ndarray) -> tuple[str, str, float]:
    """Krumhansl key profile over the whole song's chroma. (root, mode, confidence 0..1)."""
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=2048).mean(axis=1)
    best, second = (-2.0, "C", "major"), -2.0
    for i in range(12):
        for mode, prof in (("major", _MAJOR), ("minor", _MINOR)):
            r = float(np.corrcoef(np.roll(prof, i), chroma)[0, 1])
            if r > best[0]:
                second = best[0]
                best = (r, NOTE_NAMES[i], mode)
            elif r > second:
                second = r
    return best[1], best[2], float(np.clip((best[0] - second) * 5, 0, 1))


def tempo_of(y: np.ndarray) -> tuple[float, float]:
    import librosa

    onset = librosa.onset.onset_strength(y=y, sr=SR, hop_length=512)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=SR, hop_length=512)
    bpm = float(np.atleast_1d(tempo)[0])
    if beats is None or len(beats) < 8:
        return bpm, 0.0
    ibi = np.diff(beats)
    conf = float(np.clip(1 - np.std(ibi) / (np.mean(ibi) + 1e-9), 0, 1))
    return bpm, conf


def build_of(y: np.ndarray) -> float:
    """How much louder the loudest stretch is than the quietest (loudness units), a song's sense of lift."""
    win = SR * 8
    levels = [dsp.loudness(y[i:i + win], SR) for i in range(0, max(1, y.size - win), win)]
    levels = [l for l in levels if l is not None and l > -60]
    return float(np.percentile(levels, 90) - np.percentile(levels, 10)) if len(levels) >= 3 else 0.0


def measure(y: np.ndarray) -> dict:
    bpm, tconf = tempo_of(y)
    root, mode, kconf = key_of(y)
    seconds = y.size / SR
    bars = seconds / (4 * 60.0 / max(bpm, 40))
    return {
        "seconds": round(seconds, 1), "bpm": round(bpm, 1), "tempo_confidence": round(tconf, 2),
        "key": f"{root} {mode}", "mode": mode, "key_confidence": round(kconf, 2),
        "loudness": dsp.loudness(y, SR), "brightness_hz": dsp.brightness_hz(y, SR),
        "low_share": dsp.band_share(y, SR, 20, 150), "busyness": dsp.onsets_per_bar(y, SR, bars),
        "build": round(build_of(y), 1),
    }


def feeling_words(m: dict) -> list[str]:
    words = []
    bpm = m.get("bpm") or 0
    words.append("slow" if bpm < 80 else "easy-paced" if bpm < 100 else "moving" if bpm < 122 else "fast")
    b = m.get("brightness_hz") or 0
    words.append("dark and warm" if b < 1600 else "bright" if b > 3000 else "soft-edged")
    busy = m.get("busyness") or 0
    words.append("sparse" if busy < 6 else "busy" if busy > 14 else "steady")
    if (m.get("low_share") or 0) > 0.35:
        words.append("deep low end")
    if (m.get("build") or 0) > 6:
        words.append("builds a lot")
    elif (m.get("build") or 0) < 2.5:
        words.append("stays in one place")
    words.append("minor-feeling" if m.get("mode") == "minor" else "major-feeling")
    return words


def hints(m: dict) -> dict:
    """Fingerprint hints from a reference, only where it is clear. Speed and colour need real confidence."""
    out: dict = {}
    if (m.get("tempo_confidence") or 0) >= 0.6 and m.get("bpm"):
        bpm = m["bpm"]
        while bpm > 150:
            bpm /= 2
        while bpm < 60:
            bpm *= 2
        out["tempo_bpm"] = int(round(bpm))
    if (m.get("key_confidence") or 0) >= 0.4:
        out["mode"] = m["mode"]
    b = m.get("brightness_hz")
    if b:
        out["brightness"] = round(float(np.clip((b - 1000) / 3000, 0.05, 0.95)), 2)
    busy = m.get("busyness")
    if busy is not None:
        out["density"] = round(float(np.clip(busy / 20, 0.1, 0.9)), 2)
    if m.get("loudness") is not None and m.get("build") is not None:
        out["energy_level"] = round(float(np.clip(0.3 + (m["loudness"] + 20) / 20 + m["build"] / 30, 0.1, 0.95)), 2)
    return out


def compare(ref: dict, song: dict) -> list[str]:
    """At most three plain differences between the reference and the person's song (both are `measure` dicts)."""
    out = []
    if ref.get("bpm") and song.get("bpm"):
        r = ref["bpm"] / song["bpm"]
        if r > 1.12:
            out.append("Theirs moves faster than yours.")
        elif r < 0.88:
            out.append("Theirs takes its time more than yours does.")
    if ref.get("brightness_hz") and song.get("brightness_hz"):
        r = ref["brightness_hz"] / song["brightness_hz"]
        if r > 1.25:
            out.append("Theirs sounds brighter and more open on top.")
        elif r < 0.8:
            out.append("Theirs sounds darker and softer than yours.")
    if ref.get("busyness") is not None and song.get("busyness") is not None:
        if ref["busyness"] > song["busyness"] * 1.4 + 1:
            out.append("There's more going on in theirs at any moment.")
        elif song["busyness"] > ref["busyness"] * 1.4 + 1:
            out.append("Theirs leaves more space around each sound.")
    if ref.get("build") is not None and song.get("build") is not None and ref["build"] - song["build"] > 3:
        out.append("Theirs grows more from its quiet parts to its big moments.")
    if ref.get("low_share") and song.get("low_share") and ref["low_share"] > song["low_share"] * 1.4:
        out.append("Theirs has a deeper, heavier bottom.")
    return out[:3]


def remote_ears(audio: bytes, ext: str) -> dict:
    """What the frank-ears Space hears: words for its sound, styles and moods, sections, chords. {} if asleep."""
    from app.services.remote import spaces

    out: dict = {}
    f = None
    try:
        f = spaces.audio_file(audio, ext)
        r = spaces.call("ears", "/describe", f, timeout=240)
        if isinstance(r, dict):
            out = r
    except spaces.RemoteUnavailable as e:
        out = {"unavailable": e.plain}
    except Exception:  # noqa: BLE001
        log.warning("remote ears failed on a reference", exc_info=True)
    finally:
        if f is not None:
            spaces.cleanup(f)
    return out


def analyse(audio: bytes, ext: str = "mp3", remote: bool = True) -> dict:
    y = decode(audio, ext)
    m = measure(y)
    del y
    result = {"measured": m, "feeling_words": feeling_words(m), "hints": hints(m)}
    if remote:
        ears = remote_ears(audio, ext)
        if ears:
            result["ears"] = ears
            for w in ears.get("feeling_words") or []:
                if w not in result["feeling_words"]:
                    result["feeling_words"].append(w)
            if ears.get("styles"):
                result["hints"]["genre_proximity"] = [s["name"] for s in ears["styles"][:3]]
    return result
