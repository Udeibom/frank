"""Database access for the Mix Room: mix versions."""

from typing import Optional, Any
from app.db.client import get_supabase


def create_mix_version_sync(
    project_id: str, render_url: str, label: str, mix_params: dict[str, Any]
) -> dict:
    """Synchronous insert of a mix version (for use inside worker threads)."""
    supabase = get_supabase()
    result = (
        supabase.table("mix_versions")
        .insert(
            {
                "project_id": project_id,
                "render_url": render_url,
                "label": label,
                "mix_params": mix_params,
            }
        )
        .execute()
    )
    return result.data[0]


async def list_mix_versions(project_id: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("mix_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_mix_version(version_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("mix_versions")
        .select("*")
        .eq("id", version_id)
        .single()
        .execute()
    )
    return result.data


async def get_latest_mix(project_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("mix_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def count_mix_versions_sync(project_id: str) -> int:
    supabase = get_supabase()
    result = (
        supabase.table("mix_versions")
        .select("id", count="exact")
        .eq("project_id", project_id)
        .execute()
    )
    return result.count or 0
