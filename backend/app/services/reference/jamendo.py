"""
Reference songs Frank may listen to (frankenstein spec 14, requirement 6.1): Jamendo's catalogue of
Creative Commons music. The API is free for non-commercial use with a client id; every track carries its licence,
and the credit goes on the song's credits page. Streams are analysed in memory and not kept.

(Deezer and iTunes previews were ruled out: Deezer's developer terms forbid using its audio with AI and making
copies, and both are commercial recordings Frank has no licence to analyse.)
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.config import get_settings

API = "https://api.jamendo.com/v3.0/tracks/"


def available() -> bool:
    return bool(get_settings().jamendo_client_id)


def _track(t: dict) -> dict:
    tags = (t.get("musicinfo") or {}).get("tags") or {}
    return {
        "id": str(t["id"]), "title": t.get("name"), "artist": t.get("artist_name"),
        "seconds": t.get("duration"), "license": t.get("license_ccurl"),
        "attribution": f"\u201c{t.get('name')}\u201d by {t.get('artist_name')} (Jamendo, {t.get('license_ccurl')})",
        "stream": t.get("audio"), "image": t.get("image") or t.get("album_image"),
        "moods": tags.get("vartags") or [], "genres": tags.get("genres") or [],
    }


def search(text: str, limit: int = 8) -> list[dict]:
    """Tracks for a feeling or a search ("late night soul", "rainy piano"). Fuzzy tags make feelings work."""
    params = {"client_id": get_settings().jamendo_client_id, "format": "json", "limit": limit,
              "include": "musicinfo", "audioformat": "mp32", "order": "popularity_total",
              "fuzzytags": "+".join(w for w in text.lower().split() if len(w) > 2)[:120]}
    r = httpx.get(API, params=params, timeout=15.0)
    r.raise_for_status()
    found = r.json().get("results") or []
    if not found:
        params.pop("fuzzytags")
        params["search"] = text[:120]
        found = httpx.get(API, params=params, timeout=15.0).json().get("results") or []
    return [_track(t) for t in found if t.get("audio")]


def get(track_id: str) -> Optional[dict]:
    params = {"client_id": get_settings().jamendo_client_id, "format": "json", "id": track_id,
              "include": "musicinfo", "audioformat": "mp32"}
    r = httpx.get(API, params=params, timeout=15.0)
    r.raise_for_status()
    res = r.json().get("results") or []
    return _track(res[0]) if res else None


def fetch_audio(track: dict, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    with httpx.stream("GET", track["stream"], timeout=60.0, follow_redirects=True) as r:
        r.raise_for_status()
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf.extend(chunk)
            if len(buf) > max_bytes:
                break
    return bytes(buf)
