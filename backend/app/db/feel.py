"""Database access for the Feel Lab: fingerprints and texture samples."""

from typing import Optional
from app.db.client import get_supabase


# ─── Fingerprints ────────────────────────────

async def save_fingerprint(
    project_id: str, fingerprint: dict, conversation_summary: Optional[str] = None
) -> dict:
    """Persist a fingerprint snapshot."""
    supabase = get_supabase()
    result = (
        supabase.table("feel_fingerprints")
        .insert(
            {
                "project_id": project_id,
                "fingerprint": fingerprint,
                "conversation_summary": conversation_summary,
            }
        )
        .execute()
    )
    return result.data[0]


async def get_latest_fingerprint(project_id: str) -> Optional[dict]:
    """Most recent fingerprint for a project, if any."""
    supabase = get_supabase()
    result = (
        supabase.table("feel_fingerprints")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ─── Texture samples ─────────────────────────

async def save_texture(
    project_id: str,
    audio_url: str,
    cache_key: str,
    fingerprint_id: Optional[str] = None,
) -> dict:
    """Record a generated texture sample with its deterministic cache key."""
    supabase = get_supabase()
    result = (
        supabase.table("texture_samples")
        .insert(
            {
                "project_id": project_id,
                "audio_url": audio_url,
                "cache_key": cache_key,
                "fingerprint_id": fingerprint_id,
            }
        )
        .execute()
    )
    return result.data[0]


async def find_cached_texture(project_id: str, cache_key: str) -> Optional[dict]:
    """
    Look for an existing texture generated with identical parameters, matched
    on the explicit indexed cache_key column (not a URL substring).
    """
    supabase = get_supabase()
    result = (
        supabase.table("texture_samples")
        .select("*")
        .eq("project_id", project_id)
        .eq("cache_key", cache_key)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def mark_texture_approved(texture_id: str) -> None:
    supabase = get_supabase()
    supabase.table("texture_samples").update({"approved": True}).eq(
        "id", texture_id
    ).execute()
