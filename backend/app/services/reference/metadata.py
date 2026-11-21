"""
A named song, looked up (frankenstein spec 14, requirement 6.3): MusicBrainz finds the recording; ListenBrainz and
MusicBrainz give the community's tags for it. Tags become feeling words; the name itself never reaches a prompt
(founder decision, producer-craft skill: no "sounds like" game).

MusicBrainz asks for one request a second and a descriptive User-Agent; both are honoured here.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Optional

import httpx

UA = "Frank/1.0 (https://github.com/Udeibom/frank; music production for non-musicians)"
MB = "https://musicbrainz.org/ws/2"
LB = "https://api.listenbrainz.org/1"
_lock = threading.Lock()
_last = 0.0

# Community tags that say something about feeling, mapped to Frank's plain words.
TAG_FEELING = {
    "chill": "relaxed", "chillout": "relaxed", "mellow": "mellow", "melancholic": "melancholy", "melancholy": "melancholy",
    "sad": "sad", "happy": "happy", "uplifting": "uplifting", "energetic": "energetic", "dark": "dark", "atmospheric": "spacious",
    "ambient": "spacious", "dreamy": "dreamy", "dream pop": "dreamy", "lo-fi": "warm and worn", "lofi": "warm and worn",
    "acoustic": "acoustic", "intimate": "close", "romantic": "tender", "party": "danceable", "dance": "danceable",
    "groovy": "groovy", "funk": "groovy", "soul": "soulful", "gospel": "uplifting", "aggressive": "hard-hitting",
    "heavy": "heavy", "epic": "big", "cinematic": "big", "minimal": "sparse", "slow": "slow", "upbeat": "upbeat",
    "nostalgic": "nostalgic", "summer": "sunny", "night": "late-night", "rainy": "rainy", "lonely": "lonely",
}
GENRE_WORDS = {"soul", "r&b", "rnb", "pop", "rock", "hip hop", "hip-hop", "rap", "electronic", "folk", "jazz", "gospel",
               "lo-fi", "ambient", "afrobeats", "afrobeat", "reggae", "country", "indie", "house", "trap", "drill"}


def _get(url: str, params: dict) -> dict:
    global _last
    with _lock:
        wait = 1.05 - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
    r = httpx.get(url, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=12.0)
    r.raise_for_status()
    return r.json()


def split_named(text: str) -> tuple[Optional[str], Optional[str]]:
    """'Nights by Frank Ocean' / 'Frank Ocean - Nights' -> (title, artist). Either part may be None."""
    t = text.strip().strip('"\u201c\u201d')
    m = re.match(r"^(.+?)\s+by\s+(.+)$", t, re.I)
    if m:
        return m.group(1).strip(' "'), m.group(2).strip(' "')
    m = re.match(r"^(.+?)\s+[-\u2013\u2014]\s+(.+)$", t)
    if m:
        return m.group(2).strip(' "'), m.group(1).strip(' "')
    return t or None, None


def find_recording(title: Optional[str], artist: Optional[str]) -> Optional[dict]:
    q = []
    if title:
        q.append(f'recording:"{title}"')
    if artist:
        q.append(f'artist:"{artist}"')
    if not q:
        return None
    data = _get(f"{MB}/recording", {"query": " AND ".join(q), "limit": 5, "fmt": "json"})
    recs = data.get("recordings") or []
    if not recs:
        return None
    r = recs[0]
    return {"mbid": r["id"], "title": r.get("title"), "artist": ", ".join(a.get("name", "") for a in r.get("artist-credit", []) if isinstance(a, dict)),
            "length_s": (r.get("length") or 0) / 1000 or None,
            "tags": [t["name"] for t in sorted(r.get("tags") or [], key=lambda t: -t.get("count", 0))][:15]}


def listenbrainz_tags(mbid: str) -> list[str]:
    try:
        data = _get(f"{LB}/metadata/recording/", {"recording_mbids": mbid, "inc": "tag"})
        tags = ((data.get(mbid) or {}).get("tag") or {})
        out = []
        for group in ("recording", "artist", "release_group"):
            for t in tags.get(group) or []:
                name = t.get("tag")
                if name and name not in out:
                    out.append(name)
        return out[:25]
    except Exception:  # noqa: BLE001
        return []


def feeling_from_tags(tags: list[str]) -> dict:
    low = [t.lower() for t in tags]
    feelings = list(dict.fromkeys(TAG_FEELING[t] for t in low if t in TAG_FEELING))[:8]
    genres = [t for t in low if t in GENRE_WORDS][:4]
    return {"feeling_words": feelings, "genre_proximity": genres}


def look_up(text: str) -> Optional[dict]:
    """A named song to {title, artist, mbid, tags, feeling_words, genre_proximity}, or None when not found."""
    title, artist = split_named(text)
    rec = find_recording(title, artist)
    if rec is None and artist is None and title:
        rec = find_recording(None, title)            # maybe they named an artist, not a song
    if rec is None:
        return None
    tags = list(dict.fromkeys(rec["tags"] + listenbrainz_tags(rec["mbid"])))
    return {**rec, "tags": tags, **feeling_from_tags(tags)}
