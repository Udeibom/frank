"""Database access for the Voice Room: takes and comps."""

from typing import Optional, Any
from app.db.client import get_supabase


# ─── Vocal takes ─────────────────────────────

def create_take_sync(
    project_id: str, audio_url: str, label: Optional[str] = None, *, kind: str = "take",
    parent_take_id: Optional[str] = None, params: Optional[dict] = None, facts: Optional[dict] = None,
    is_harmony: bool = False,
) -> dict:
    """
    Synchronous insert of a vocal take (for use inside worker threads). A derived version (tuned, lined up,
    beat taken out, harmony) is its own row with `parent_take_id`, so the take it came from never changes.
    """
    row: dict[str, Any] = {"project_id": project_id, "audio_url": audio_url, "label": label, "kind": kind,
                           "is_harmony": is_harmony, "params": params or {}, "facts": facts or {}}
    if parent_take_id:
        row["parent_take_id"] = parent_take_id
    result = get_supabase().table("vocal_takes").insert(row).execute()
    return result.data[0]


async def create_take(project_id: str, audio_url: str, label: Optional[str] = None, **kw: Any) -> dict:
    return create_take_sync(project_id, audio_url, label, **kw)


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


# ─── Device delay and guide cache (sing-it spec 06) ─────────────

def get_input_delay_ms(user_id: str) -> Optional[float]:
    rows = get_supabase().table("user_settings").select("input_delay_ms").eq("user_id", user_id).limit(1).execute().data
    return float(rows[0]["input_delay_ms"]) if rows and rows[0].get("input_delay_ms") is not None else None


def set_input_delay_ms(user_id: str, delay_ms: float) -> None:
    get_supabase().table("user_settings").upsert({"user_id": user_id, "input_delay_ms": delay_ms}, on_conflict="user_id").execute()


def get_guide(beat_version_id: str) -> Optional[str]:
    rows = get_supabase().table("guide_renders").select("audio_url").eq("beat_version_id", beat_version_id).limit(1).execute().data
    return rows[0]["audio_url"] if rows else None


def put_guide(beat_version_id: str, audio_url: str) -> None:
    get_supabase().table("guide_renders").upsert({"beat_version_id": beat_version_id, "audio_url": audio_url},
                                                 on_conflict="beat_version_id").execute()


def update_comp_segments_sync(comp_id: str, segments: list[dict]) -> None:
    get_supabase().table("vocal_comps").update({"segments": segments}).eq("id", comp_id).execute()
