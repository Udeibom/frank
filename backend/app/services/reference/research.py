"""
What a named song feels like, from what people have written about it (frankenstein spec 14, requirement 6.3).

Exa finds a few pages about the song; Firecrawl reads them as clean text; one model call turns them into feeling
words and broad facts (slow or fast, sparse or full, acoustic or electronic, close or wide). The founder's rule
holds: no artist names and no lyrics leave this module, and nothing aims at copying anyone's sound. The feeling
words only help Frank ask a better question and offer better directions.

Both services have free tiers with no card (Exa about $10 credit a month, Firecrawl 500 searches); each needs a key.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("frank.research")

MAX_PAGES = 2
MAX_READS = 3            # page reads tried per song, at most (each one costs a Firecrawl credit)
MAX_CHARS = 6000

EXTRACT_SYSTEM = """You read short articles about one song and say how it FEELS and how it is BUILT, in everyday words a
non-musician understands. Never name any person, band, album or song. Never quote lyrics. Never use music terms (no
tempo numbers, keys, chords, BPM, reverb, synth names). Return JSON only:
{"feeling_words": ["three to six words like hushed, late-night, warm, aching"],
 "pace": "slow|easy|steady|quick|fast|unknown", "fullness": "sparse|medium|full|unknown",
 "sound": "acoustic|electronic|mixed|unknown", "space": "close|roomy|wide|unknown",
 "voice": "one short phrase about how the singing feels, or empty",
 "build": "one short sentence on how the song moves from start to end, or empty"}"""


def available() -> bool:
    s = get_settings()
    return bool(s.exa_api_key and s.firecrawl_api_key)


def song_key(title: Optional[str], artist: Optional[str]) -> str:
    norm = lambda v: re.sub(r"[^a-z0-9]+", " ", (v or "").lower()).strip()  # noqa: E731
    return f"{norm(title)}|{norm(artist)}"


def _cached(key: str) -> tuple[bool, Optional[dict]]:
    """(found, result). A song researched before is never paid for again, for anyone."""
    try:
        from app.db.client import get_supabase
        rows = get_supabase().table("research_cache").select("result").eq("song_key", key).limit(1).execute().data
        return (True, rows[0]["result"]) if rows else (False, None)
    except Exception:  # noqa: BLE001
        return False, None


def _remember(key: str, result: Optional[dict]) -> None:
    try:
        from app.db.client import get_supabase
        get_supabase().table("research_cache").upsert({"song_key": key, "result": result}).execute()
    except Exception:  # noqa: BLE001
        log.warning("could not cache song research", exc_info=True)


def search(query: str) -> list[str]:
    key = get_settings().exa_api_key
    r = httpx.post("https://api.exa.ai/search", headers={"x-api-key": key},
                   json={"query": query, "numResults": 5, "type": "auto"}, timeout=20.0)
    r.raise_for_status()
    return [x["url"] for x in r.json().get("results", []) if x.get("url")][:5]


def read_page(url: str) -> str:
    key = get_settings().firecrawl_api_key
    r = httpx.post("https://api.firecrawl.dev/v2/scrape", headers={"Authorization": f"Bearer {key}"},
                   json={"url": url, "formats": ["markdown"], "onlyMainContent": True}, timeout=45.0)
    r.raise_for_status()
    data = r.json().get("data") or {}
    return (data.get("markdown") or "")[:MAX_CHARS]


def scrub(text: str, names: list[str]) -> str:
    """Remove the names we know of before the model sees the text, so they cannot come back out."""
    for n in names:
        for part in [n] + [p for p in re.split(r"[,&]| and | feat\.? ", n) if len(p.strip()) > 2]:
            text = re.sub(re.escape(part.strip()), "the artist", text, flags=re.I)
    return text


def clean(raw: dict, names: list[str]) -> dict:
    from app.services.team.plain import guard

    def ok(word: str) -> bool:
        return not any(n.lower() in word.lower() for n in names if n)

    out = {"feeling_words": [guard(str(w))[:30] for w in (raw.get("feeling_words") or []) if ok(str(w))][:6]}
    for k, allowed in (("pace", {"slow", "easy", "steady", "quick", "fast"}), ("fullness", {"sparse", "medium", "full"}),
                       ("sound", {"acoustic", "electronic", "mixed"}), ("space", {"close", "roomy", "wide"})):
        if raw.get(k) in allowed:
            out[k] = raw[k]
    for k in ("voice", "build"):
        v = str(raw.get(k) or "").strip()
        if v and ok(v):
            out[k] = guard(v)[:160]
    return out


def research(title: Optional[str], artist: Optional[str]) -> Optional[dict]:
    """Feeling words and broad facts about a named song, or None (no keys, nothing found, or a failure)."""
    if not available() or not (title or artist):
        return None
    from app.services.llm.groq_client import chat_json

    from app.services import budget

    names = [n for n in (title, artist) if n]
    key = song_key(title, artist)
    found, cached = _cached(key)
    if found:
        return cached
    if not budget.spend("exa"):
        log.info("Exa allowance for this month is used up; going by the song's tags only")
        return None
    try:
        urls = search(f"{title or ''} {artist or ''} song review sound mood production".strip())
        pages = []
        for u in urls[:MAX_READS]:
            if not budget.spend("firecrawl"):
                log.info("Firecrawl allowance for this month is used up")
                break
            try:
                text = read_page(u)
            except Exception:  # noqa: BLE001
                continue
            if len(text) > 400:
                pages.append(scrub(text, names))
            if len(pages) >= MAX_PAGES:
                break
        if not pages:
            _remember(key, None)
            return None
        raw = json.loads(chat_json(EXTRACT_SYSTEM, "\n\n---\n\n".join(pages)) or "{}")
        result = clean(raw if isinstance(raw, dict) else {}, names) | {"pages_read": len(pages)}
        _remember(key, result)
        return result
    except Exception:  # noqa: BLE001
        log.warning("researching a named song failed", exc_info=True)
        return None
