from typing import Optional
from uuid import UUID
from app.db.client import get_supabase


async def create_project(user_id: str, title: str = "Untitled Song") -> dict:
    """Create a new project and its active state record."""
    supabase = get_supabase()

    project = (
        supabase.table("projects")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    project_data = project.data[0]
    project_id = project_data["id"]

    # Create the active state row for this project
    supabase.table("project_active_state").insert(
        {"project_id": project_id}
    ).execute()

    return project_data


async def get_project(project_id: str) -> Optional[dict]:
    """Get a single project by ID."""
    supabase = get_supabase()
    result = (
        supabase.table("projects")
        .select("*")
        .eq("id", project_id)
        .single()
        .execute()
    )
    return result.data


async def list_projects_by_user(user_id: str) -> list[dict]:
    """List all non-archived projects for a user, newest first."""
    supabase = get_supabase()
    result = (
        supabase.table("projects")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data or []


async def update_project(project_id: str, updates: dict) -> dict:
    """Update project fields (title, status). Returns updated record."""
    supabase = get_supabase()
    result = (
        supabase.table("projects")
        .update(updates)
        .eq("id", project_id)
        .execute()
    )
    return result.data[0]


async def get_project_active_state(project_id: str) -> Optional[dict]:
    """Get the active state pointers for a project."""
    supabase = get_supabase()
    result = (
        supabase.table("project_active_state")
        .select("*")
        .eq("project_id", project_id)
        .single()
        .execute()
    )
    return result.data


async def update_project_active_state(project_id: str, updates: dict) -> dict:
    """
    Update which version is active for a given layer.
    updates example: {"active_lyrics_id": "uuid-here"}
    """
    supabase = get_supabase()
    result = (
        supabase.table("project_active_state")
        .update(updates)
        .eq("project_id", project_id)
        .execute()
    )
    return result.data[0]
