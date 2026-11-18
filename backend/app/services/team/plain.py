"""
Plain-language guard (team-conversation spec 07, requirement 6; conversation-layer steering "Plain Language Rules").

Every reply Frank shows passes through `guard`. Music jargon is swapped for the plain words the steering file
gives (BPM -> the speed of the song, reverb -> space, ...). Units and technical names with no plain equivalent
(Hz, dB, MIDI, DAW, VST, LUFS) are removed with the number that goes with them. This is code, not a request to the
model, so it always holds; the model is still told the rules in every prompt, so the guard rarely has work to do.
"""
from __future__ import annotations

import re

# (pattern, replacement). Order matters: longer phrases first. Word boundaries keep "keyboard" or "modest" safe.
REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bbeats per minute\b", "speed"),
    (r"\b\d+(\.\d+)?\s*bpm\b", "this speed"),
    (r"\bbpm\b", "speed"),
    (r"\btempo\b", "speed"),
    (r"\bminor key\b", "darker colour"),
    (r"\bmajor key\b", "brighter colour"),
    (r"\b(in|change|the|a|its|this) key\b", r"\1 colour of the notes"),
    (r"\breverb\b", "space"),
    (r"\bcompress(ion|or|ed|ing)?\b", "smoothing"),
    (r"\bequali[sz](ation|er|ing)\b", "tone shaping"),
    (r"\beq\b", "tone"),
    (r"\bquanti[sz](ation|e|ed|ing)\b", "locking to the beat"),
    (r"\bstems\b", "parts"),
    (r"\bstem\b", "part"),
    (r"\bpads\b", "soft background sounds"),
    (r"\bmixdown\b", "mix"),
]
# Units and tool names with no plain equivalent: drop them, with any number in front.
REMOVE: list[str] = [r"\b-?\d+(\.\d+)?\s*(k?hz|db|lufs)\b", r"\b(k?hz|db|lufs)\b", r"\b(midi|daw|vst)s?\b"]

_RX = [(re.compile(p, re.I), r) for p, r in REPLACEMENTS]
_RM = [re.compile(p, re.I) for p in REMOVE]
JARGON = re.compile(r"\b(bpm|tempo|reverb|compress\w*|eq|quanti[sz]\w*|stems?|midi|daw|vst|lufs|k?hz|db)\b", re.I)


def find_jargon(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in JARGON.finditer(text or "")})


def guard(text: str) -> str:
    """The same reply with jargon replaced by plain words. Text without jargon comes back unchanged."""
    if not text or not JARGON.search(text):
        return text
    out = text
    for rx, rep in _RX:
        out = rx.sub(rep, out)
    for rx in _RM:
        out = rx.sub("", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return out.strip()
