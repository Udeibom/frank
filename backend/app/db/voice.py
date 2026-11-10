"""Database access for the Voice Room: takes and comps."""

from typing import Optional, Any
from app.db.client import get_supabase


# ─── Vocal takes ─────────────────────────────

def create_take_sync(
    project_id: str, audio_url: str, label: Optional[str] = None
) -> dict:
    """Synchronous insert of a vocal take (for use inside worker threads)."""
    supabase = get_supabase()
    result = (
        supabase.table("vocal_takes")
        .insert({"project_id": project_id, "audio_url": audio_url, "label": label})
        .execute()
    )
    return result.data[0]


async def create_take(
    project_id: str, audio_url: str, label: Optional[str] = None
) -> dict:
    return create_take_sync(project_id, audio_url, label)


async def list_takes(project_id: str) -> list[dict]:
    """All non-deleted takes for a project, newest first."""
    supabase = get_supabase()
    result = (
        supabase.table("vocal_takes")
        .select("*")
        .eq("project_id", project_id)
        .eq("deleted", False)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_take(take_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("vocal_takes").select("*").eq("id", take_id).single().execute()
    )
    return result.data


def update_take_sync(take_id: str, updates: dict[str, Any]) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("vocal_takes").update(updates).eq("id", take_id).execute()
    )
    return result.data[0]


async def update_take(take_id: str, updates: dict[str, Any]) -> dict:
    return update_take_sync(take_id, updates)


async def soft_delete_take(take_id: str) -> None:
    """Mark a take deleted (the audio file is kept — never destroy work)."""
    supabase = get_supabase()
    supabase.table("vocal_takes").update({"deleted": True}).eq(
        "id", take_id
    ).execute()


def count_takes_sync(project_id: str) -> int:
    supabase = get_supabase()
    result = (
        supabase.table("vocal_takes")
        .select("id", count="exact")
        .eq("project_id", project_id)
        .execute()
    )
    return result.count or 0


# ─── Vocal comps ─────────────────────────────

def create_comp_sync(
    project_id: str, audio_url: str, segments: list[dict]
) -> dict:
    supabase = get_supabase()
    result = (
        supabase.table("vocal_comps")
        .insert(
            {"project_id": project_id, "audio_url": audio_url, "segments": segments}
        )
        .execute()
    )
    return result.data[0]


async def get_latest_comp(project_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("vocal_comps")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def get_comp(comp_id: str) -> Optional[dict]:
    """A specific comp by id (the active comp, not just the newest one)."""
    supabase = get_supabase()
    result = (
        supabase.table("vocal_comps")
        .select("*")
        .eq("id", comp_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
