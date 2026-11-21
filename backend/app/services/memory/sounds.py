"""
Memory by sound (frankenstein spec 14, requirements 2.1 and 7.1): CLAP vectors in Supabase pgvector.

- Every texture, beat and reference Frank hears is embedded once (frank-ears /embed_audio) and stored.
- Directions in the Feeling room are ranked by how close they sound to the person's own words.
- A texture the person approves is also kept as "taste", so a new song's first directions lean toward sounds
  they have liked before. This sits beside the rule-based taste memory (services/taste), which stays the record
  of what they said; this is the record of what they liked hearing.
All of it is best-effort: with the ears asleep, Frank works exactly as before.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.db.client import get_supabase
from app.services.remote import organs

log = logging.getLogger("frank.memory")
MODEL = "clap-larger-music-speech"


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def remember(kind: str, ref_id: str, embedding: list[float], user_id: Optional[str], project_id: Optional[str],
             meta: Optional[dict] = None) -> None:
    try:
        get_supabase().table("sound_embeddings").upsert({
            "kind": kind, "ref_id": ref_id, "model": MODEL, "embedding": _vec(embedding),
            "user_id": user_id, "project_id": project_id, "meta": meta or {},
        }, on_conflict="kind,ref_id,model").execute()
    except Exception:  # noqa: BLE001
        log.warning("could not store a sound embedding", exc_info=True)


def embedding_of(kind: str, ref_id: str) -> Optional[list[float]]:
    rows = (get_supabase().table("sound_embeddings").select("embedding").eq("kind", kind).eq("ref_id", ref_id)
            .eq("model", MODEL).limit(1).execute().data) or []
    if not rows:
        return None
    raw = rows[0]["embedding"]
    if isinstance(raw, str):
        return [float(x) for x in raw.strip("[]").split(",") if x]
    return list(raw)


def nearest(query: list[float], user_id: str, kinds: list[str], project_id: Optional[str] = None, k: int = 5) -> list[dict]:
    try:
        return get_supabase().rpc("match_sounds", {"query": _vec(query), "for_user": user_id, "for_kinds": kinds,
                                                   "for_project": project_id, "how_many": k}).execute().data or []
    except Exception:  # noqa: BLE001
        log.warning("sound search failed", exc_info=True)
        return []


def embed_and_remember(kind: str, ref_id: str, audio: bytes, ext: str, user_id: Optional[str],
                       project_id: Optional[str], meta: Optional[dict] = None) -> Optional[list[float]]:
    v = organs.try_(organs.embed_audio, audio, ext)
    if v:
        remember(kind, ref_id, v, user_id, project_id, meta)
    return v


def rank_by_words(words: list[str], items: list[tuple[str, list[float]]],
                  liked: Optional[list[list[float]]] = None) -> list[tuple[str, float]]:
    """(id, score) best first. Score = closeness to the person's words, nudged toward sounds they liked before."""
    text = organs.try_(organs.embed_text, [" ".join(words)[:300]]) if words else None
    out = []
    for ref_id, v in items:
        s = organs.cosine(text[0], v) if text else 0.0
        if liked:
            s += 0.25 * max(organs.cosine(l, v) for l in liked)
        out.append((ref_id, round(s, 4)))
    return sorted(out, key=lambda x: -x[1])
