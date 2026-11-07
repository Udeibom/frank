"""Database access for the Beat Room: beat versions, sections, and stems."""

from typing import Optional, Any
from app.db.client import get_supabase


# ─── Beat versions ───────────────────────────

def create_beat_version_sync(
    project_id: str, render_url: str, label: str, params: dict[str, Any]
) -> dict:
    """Synchronous insert of a beat version (for use inside worker threads)."""
    supabase = get_supabase()
    result = (
        supabase.table("beat_versions")
        .insert(
            {
                "project_id": project_id,
                "render_url": render_url,
                "label": label,
                "params": params,
            }
        )
        .execute()
    )
    return result.data[0]


async def create_beat_version(
    project_id: str, render_url: str, label: str, params: dict[str, Any]
) -> dict:
    """Record a rendered beat version."""
    return create_beat_version_sync(project_id, render_url, label, params)


async def list_beat_versions(project_id: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("beat_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_beat_version(version_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("beat_versions")
        .select("*")
        .eq("id", version_id)
        .single()
        .execute()
    )
    return result.data


async def update_beat_version_label(version_id: str, label: str) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("beat_versions")
        .update({"label": label})
        .eq("id", version_id)
        .execute()
    )
    return result.data[0]


async def count_beat_versions(project_id: str) -> int:
    supabase = get_supabase()
    result = (
        supabase.table("beat_versions")
        .select("id", count="exact")
        .eq("project_id", project_id)
        .execute()
    )
    return result.count or 0


# ─── Beat stems ──────────────────────────────

def create_stem_sync(
    project_id: str,
    beat_version_id: str,
    stem_type: str,
    section: str,
    audio_url: str,
) -> dict:
    """Synchronous insert of a stem record (for use inside worker threads)."""
    supabase = get_supabase()
    result = (
        supabase.table("beat_stems")
        .insert(
            {
                "project_id": project_id,
                "beat_version_id": beat_version_id,
                "stem_type": stem_type,
                "section": section,
                "audio_url": audio_url,
            }
        )
        .execute()
    )
    return result.data[0]


async def create_stem(
    project_id: str,
    beat_version_id: str,
    stem_type: str,
    section: str,
    audio_url: str,
) -> dict:
    """Record one stem (one instrument in one section) of a beat version."""
    return create_stem_sync(
        project_id, beat_version_id, stem_type, section, audio_url
    )


async def list_stems(beat_version_id: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("beat_stems")
        .select("*")
        .eq("beat_version_id", beat_version_id)
        .order("created_at")
        .execute()
    )
    return result.data or []
