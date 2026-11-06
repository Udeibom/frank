from fastapi import APIRouter, HTTPException, Depends
from app.models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectWithState,
    ProjectActiveState,
)
from app.db import projects as db
from app.config import get_settings, Settings

router = APIRouter(prefix="/projects", tags=["projects"])


def get_current_user_id(settings: Settings = Depends(get_settings)) -> str:
    """
    Dev stub: returns the hardcoded dev user ID.
    Replaced with real JWT extraction in Spec 08 (auth).
    """
    return settings.dev_user_id


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    """Create a new song project."""
    project = await db.create_project(user_id=user_id, title=body.title)
    return ProjectResponse(**project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user_id: str = Depends(get_current_user_id),
) -> list[ProjectResponse]:
    """List all projects for the current user, newest first."""
    projects = await db.list_projects_by_user(user_id=user_id)
    return [ProjectResponse(**p) for p in projects]


@router.get("/{project_id}", response_model=ProjectWithState)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
) -> ProjectWithState:
    """Get a single project with its active state pointers."""
    project = await db.get_project(project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your project")

    active_state = await db.get_project_active_state(project_id=project_id)

    return ProjectWithState(
        project=ProjectResponse(**project),
        active_state=ProjectActiveState(**active_state) if active_state else None,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    """Update a project's title or status."""
    existing = await db.get_project(project_id=project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
    if existing["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your project")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return ProjectResponse(**existing)

    updated = await db.update_project(project_id=project_id, updates=updates)
    return ProjectResponse(**updated)
