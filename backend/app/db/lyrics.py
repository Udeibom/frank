"""Database access for lyrics versions."""

from typing import Optional
from app.db.client import get_supabase


async def get_latest_version(project_id: str) -> Optional[dict]:
    """Get the most recent lyrics version for a project, if any."""
    supabase = get_supabase()
    result = (
        supabase.table("lyrics_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def create_version(
    project_id: str, content: str, label: Optional[str] = None
) -> dict:
    """Create a new lyrics version."""
    supabase = get_supabase()
    result = (
        supabase.table("lyrics_versions")
        .insert({"project_id": project_id, "content": content, "label": label})
        .execute()
    )
    return result.data[0]


async def list_versions(project_id: str) -> list[dict]:
    """List all lyrics versions for a project, newest first."""
    supabase = get_supabase()
    result = (
        supabase.table("lyrics_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_version(version_id: str) -> Optional[dict]:
    """Get a single lyrics version by ID."""
    supabase = get_supabase()
    result = (
        supabase.table("lyrics_versions")
        .select("*")
        .eq("id", version_id)
        .single()
        .execute()
    )
    return result.data


async def update_label(version_id: str, label: str) -> dict:
    """Update the label on a lyrics version."""
    supabase = get_supabase()
    result = (
        supabase.table("lyrics_versions")
        .update({"label": label})
        .eq("id", version_id)
        .execute()
    )
    return result.data[0]
