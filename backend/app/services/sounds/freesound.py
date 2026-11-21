"""
Real recorded atmospheres (frankenstein spec 14, requirement 3.7): rain, room tone, vinyl crackle, a city at night,
from Freesound. Only CC0 and CC BY sounds are used, so the song stays shareable; a CC BY sound's credit goes on the
song's credits page. The API is free with a registered key (non-commercial use).
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.config import get_settings

API = "https://freesound.org/apiv2/search/text/"
LICENSES = '("Creative Commons 0" OR "Attribution")'

# Feeling words to the sounds that carry them. The first that matches the brief wins; "room tone" is the default.
FEELING_SOUNDS = [
    (("rain", "rainy", "storm", "wet"), "rain on window"),
    (("night", "late-night", "city", "street", "drive", "streetlights"), "city night ambience"),
    (("ocean", "sea", "beach", "waves"), "ocean waves"),
    (("forest", "woods", "birds", "morning", "dawn"), "forest morning birds"),
    (("warm", "worn", "old", "nostalgic", "vinyl", "lo-fi", "lofi"), "vinyl crackle"),
    (("church", "gospel", "hall", "big", "wide"), "empty church ambience"),
    (("cafe", "crowd", "party", "people"), "cafe crowd murmur"),
    (("wind", "lonely", "cold", "empty", "winter"), "wind ambience"),
    (("fire", "cosy", "cozy", "home"), "fireplace crackling"),
]


def available() -> bool:
    return bool(get_settings().freesound_api_key)


def query_for(words: list[str]) -> str:
    low = " ".join(words).lower()
    for keys, q in FEELING_SOUNDS:
        if any(k in low for k in keys):
            return q
    return "room tone ambience"


def search(query: str, limit: int = 6) -> list[dict]:
    params = {"query": query, "filter": f"license:{LICENSES} duration:[8 TO 180]", "sort": "rating_desc",
              "fields": "id,name,username,license,previews,duration,url", "page_size": limit,
              "token": get_settings().freesound_api_key}
    r = httpx.get(API, params=params, timeout=15.0)
    r.raise_for_status()
    out = []
    for s in r.json().get("results") or []:
        lic = s.get("license", "")
        cc0 = "publicdomain/zero" in lic or "Creative Commons 0" in lic
        out.append({"id": s["id"], "name": s.get("name"), "by": s.get("username"), "license": lic,
                    "preview": (s.get("previews") or {}).get("preview-hq-mp3"), "seconds": s.get("duration"),
                    "url": s.get("url"),
                    "attribution": None if cc0 else f"\u201c{s.get('name')}\u201d by {s.get('username')} (Freesound, CC BY): {s.get('url')}"})
    return [s for s in out if s["preview"]]


def fetch(sound: dict) -> bytes:
    r = httpx.get(sound["preview"], params={"token": get_settings().freesound_api_key}, timeout=40.0, follow_redirects=True)
    r.raise_for_status()
    return r.content


def pick(words: list[str]) -> Optional[dict]:
    found = search(query_for(words))
    return found[0] if found else None
