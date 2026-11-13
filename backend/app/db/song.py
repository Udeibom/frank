"""Database access for the Song Record. Version and decision rows are append-only (the database refuses UPDATEs)."""

from __future__ import annotations

from typing import Optional

from app.db.client import get_supabase
from app.models.song import Decision, FacetVersion


def _to_version(row: dict) -> FacetVersion:
    return FacetVersion(**row)


def _to_decision(row: dict) -> Decision:
    return Decision(**row)


async def list_versions(project_id: str, facet: Optional[str] = None) -> list[FacetVersion]:
    """All versions for a project (optionally one facet), oldest first."""
    query = (
        get_supabase()
        .table("song_facet_versions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at")
    )
    if facet:
        query = query.eq("facet", facet)
    return [_to_version(r) for r in (query.execute().data or [])]


async def get_versions(project_id: str, version_ids: list[str]) -> list[FacetVersion]:
    """Only the versions asked for (the active ones), however long the history has grown."""
    if not version_ids:
        return []
    result = (
        get_supabase()
        .table("song_facet_versions")
        .select("*")
        .eq("project_id", project_id)
        .in_("id", version_ids)
        .execute()
    )
    return [_to_version(r) for r in (result.data or [])]


async def insert_version(version: FacetVersion) -> FacetVersion:
    """Store a version built by services.song.versions. Never updates an existing row."""
    row = version.model_dump(mode="json", exclude={"created_at"})
    result = get_supabase().table("song_facet_versions").insert(row).execute()
    return _to_version(result.data[0])


async def get_active_map(project_id: str) -> dict[str, str]:
    """facet -> active version id."""
    result = (
        get_supabase()
        .table("song_facet_active")
        .select("facet, version_id")
        .eq("project_id", project_id)
        .execute()
    )
    return {r["facet"]: r["version_id"] for r in (result.data or [])}


async def set_active(project_id: str, facet: str, version_id: str) -> None:
    """Move a facet's active pointer. Instant: no processing."""
    get_supabase().table("song_facet_active").upsert(
        {"project_id": project_id, "facet": facet, "version_id": version_id},
        on_conflict="project_id,facet",
    ).execute()


async def insert_decision(project_id: str, data: dict) -> Decision:
    result = (
        get_supabase()
        .table("song_decisions")
        .insert({"project_id": project_id, **data})
        .execute()
    )
    return _to_decision(result.data[0])


async def list_decisions(project_id: str, limit: int = 50) -> list[Decision]:
    """Newest first."""
    result = (
        get_supabase()
        .table("song_decisions")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_to_decision(r) for r in (result.data or [])]
