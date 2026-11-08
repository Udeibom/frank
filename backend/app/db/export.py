"""Database access for the Export Room: export records."""

from typing import Optional
from app.db.client import get_supabase


def create_export_sync(
    project_id: str,
    audio_url: str,
    storage_path: str,
    mix_version_id: str,
    mastered: bool,
    fmt: str = "mp3",
    quality: str = "320k",
) -> dict:
    """Synchronous insert of an export record (for use inside worker threads)."""
    supabase = get_supabase()
    result = (
        supabase.table("exports")
        .insert(
            {
                "project_id": project_id,
                "audio_url": audio_url,
                "storage_path": storage_path,
                "mix_version_id": mix_version_id,
                "mastered": mastered,
                "format": fmt,
                "quality": quality,
            }
        )
        .execute()
    )
    return result.data[0]


def find_existing_export_sync(
    project_id: str, mix_version_id: str, mastered: bool
) -> Optional[dict]:
    """
    Find an export already rendered for this exact mix version + mastering
    choice, so Download is instant and we don't create duplicate rows.
    """
    supabase = get_supabase()
    result = (
        supabase.table("exports")
        .select("*")
        .eq("project_id", project_id)
        .eq("mix_version_id", mix_version_id)
        .eq("mastered", mastered)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def list_exports(project_id: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("exports")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_export(export_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("exports")
        .select("*")
        .eq("id", export_id)
        .single()
        .execute()
    )
    return result.data
