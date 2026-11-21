"""
Gemini as Frank's ears and eyes (frankenstein spec 14, requirements 2.3 and 6.6).

`listen`: a short bounce of the song plus the Listener's own numbers go to Gemini, which may return at most three
notes about what it hears. Frank acts on a note only when the Listener confirms it (`confirm`); the rest are said
as "I think", never acted on. Audio LLMs still miss a lot (about 50-60 % on hard audio benchmarks), so the numbers
keep the words honest.

`look`: a picture the person shares becomes feeling words and fingerprint hints.

Both are skipped where the Gemini terms do not allow the free tier (services/region.py), and both return None on
any failure so the caller falls back to Frank's own measurements.
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.config import get_settings
from app.services import region
from app.services.team.plain import guard

log = logging.getLogger("frank.gemini")

MODEL = "gemini-flash-latest"
BACKUP_MODEL = "gemini-flash-lite-latest"   # Google's free models are often "overloaded" (503); the lighter one answers
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_NOTES = 3
MAX_INLINE_BYTES = 15 * 1024 * 1024

# Tags a Gemini note may carry; the same tags as the Listener's findings (listener/findings.py CONCERN_WORDS).
TAGS = ("voice_buried", "voice_crowded", "chorus_lift", "timing", "tuning", "clipping", "noise", "level", "flat",
        "brightness", "muddy", "busy", "empty", "other")

LISTEN_PROMPT = """You are the mix engineer in a small studio team, listening to a song a person with no music
training is making. You will hear a short section and read the studio's own measurements of it.
Say what you actually hear, briefly, in everyday words a non-musician understands. Never use technical terms
(no tempo, BPM, key, reverb, compression, EQ, frequencies, dB, LUFS, stems, MIDI).
Return JSON only:
{"heard": "one sentence about the overall feel",
 "notes": [{"tag": one of %s, "plain": "what you hear, one sentence", "confidence": 0.0-1.0}]}
At most %d notes, the most important first. If nothing needs changing, return an empty list.
The person said: %s
The measurements: %s"""

LOOK_PROMPT = """A person making a song shared this picture to show the feeling they want. Describe the feeling,
not the objects, in everyday words. Return JSON only:
{"feeling": "one short sentence, like 'a quiet late-night drive alone'",
 "words": ["three to six feeling words"],
 "energy": 0.0-1.0, "warmth": 0.0-1.0, "brightness": 0.0-1.0, "movement": "still|drifting|moving|rushing"}"""


@dataclass
class Heard:
    heard: str
    notes: list[dict] = field(default_factory=list)


def _post(parts: list[dict]) -> Optional[dict]:
    key = get_settings().gemini_api_key
    if not key or not region.gemini_allowed():
        return None
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    import time

    # The key goes in a header, never the address: addresses end up in error messages and server logs.
    headers = {"x-goog-api-key": key}
    for attempt, model in enumerate((MODEL, MODEL, BACKUP_MODEL, BACKUP_MODEL)):
        try:
            r = httpx.post(URL.format(model=model), headers=headers, json=body, timeout=60.0)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                log.info("gemini %s busy (%s); trying again", model, r.status_code)
                time.sleep(2 + 3 * attempt)
                continue
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(text)
            return out if isinstance(out, dict) else None
        except httpx.TransportError as e:                 # timeout or dropped connection: try the next
            log.info("gemini %s unreachable (%s)", model, type(e).__name__)
            continue
        except Exception as e:  # noqa: BLE001 - odd reply or refusal: fall back to Frank's own measurements
            log.warning("gemini media call failed (%s): %s", model, type(e).__name__)
            return None
    return None


def _inline(data: bytes, mime: str) -> dict:
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}


def parse_heard(raw: Optional[dict]) -> Optional[Heard]:
    """Keep only well-formed notes, at most three, each passed through the plain-language guard."""
    if not raw:
        return None
    notes = []
    for n in raw.get("notes") or []:
        if not isinstance(n, dict) or not isinstance(n.get("plain"), str) or not n["plain"].strip():
            continue
        tag = n.get("tag") if n.get("tag") in TAGS else "other"
        try:
            conf = max(0.0, min(1.0, float(n.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        notes.append({"tag": tag, "plain": guard(n["plain"].strip()), "confidence": conf})
        if len(notes) == MAX_NOTES:
            break
    return Heard(guard(str(raw.get("heard") or "").strip()), notes)


def listen(audio: bytes, mime: str, measurements: dict, said: str = "") -> Optional[Heard]:
    if len(audio) > MAX_INLINE_BYTES:
        return None
    prompt = LISTEN_PROMPT % (", ".join(TAGS), MAX_NOTES, json.dumps(said or "nothing yet"), json.dumps(measurements)[:6000])
    return parse_heard(_post([_inline(audio, mime), {"text": prompt}]))


FINDING_TO_TAG = {"too_quiet": "level", "too_loud": "level", "copy": "flat", "melody_wanders": "tuning"}


def tags_of(finding_ids: set[str]) -> set[str]:
    """Listener finding ids (listener/findings.py) as Gemini note tags."""
    return {FINDING_TO_TAG.get(f, f) for f in finding_ids}


def confirm(heard: Heard, finding_ids: set[str]) -> list[dict]:
    """Mark each note confirmed when the Listener found something with the same tag. Only confirmed notes may
    become actions; 'other' is never confirmed."""
    finding_tags = tags_of(finding_ids)
    out = []
    for n in heard.notes:
        out.append({**n, "confirmed": n["tag"] != "other" and n["tag"] in finding_tags})
    return out


def look(image: bytes, mime: str) -> Optional[dict]:
    if len(image) > MAX_INLINE_BYTES:
        return None
    raw = _post([_inline(image, mime), {"text": LOOK_PROMPT}])
    if not raw:
        return None
    out: dict = {"feeling": guard(str(raw.get("feeling") or "").strip()),
                 "words": [guard(str(w)) for w in (raw.get("words") or [])][:6]}
    for k in ("energy", "warmth", "brightness"):
        try:
            out[k] = max(0.0, min(1.0, float(raw.get(k))))
        except (TypeError, ValueError):
            pass
    if raw.get("movement") in ("still", "drifting", "moving", "rushing"):
        out["movement"] = raw["movement"]
    return out
