"""Song Record routes (song-record spec 01). Mounted under the project ownership check."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import projects as projects_db
from app.db import song as song_db
from app.models.song import (
    FACETS,
    USER_AUTHOR,
    ActivateFacetRequest,
    Decision,
    FacetVersionResponse,
    RecordDecisionRequest,
    RestoreFacetRequest,
    SetPhaseRequest,
    SongRecord,
    WriteFacetRequest,
)
from app.services.song import record as record_svc
from app.services.song import store
from app.services.song.versions import VersionError

router = APIRouter(prefix="/projects/{project_id}/song", tags=["song"])


def _check_facet(facet: str) -> None:
    if facet not in FACETS:
        raise HTTPException(status_code=404, detail="I don't know that part of the song.")


def _plain_error(exc: VersionError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="I couldn't save that change. Want to try again?",
    )


@router.get("", response_model=SongRecord)
async def get_song(project_id: str) -> SongRecord:
    """Everything Frank knows about this song, for the studio summary."""
    return await record_svc.get_record(project_id)


@router.post("/facets/{facet}", response_model=FacetVersionResponse, status_code=201)
async def write_facet(project_id: str, facet: str, body: WriteFacetRequest) -> FacetVersionResponse:
    """Add a new version of a facet. Written by the person using the studio."""
    _check_facet(facet)
    try:
        v = await store.write_facet(
            project_id,
            facet,
            body.content,
            author=USER_AUTHOR,
            operation=body.operation,
            parent_id=body.parent_id,
            op_params=body.op_params,
            label=body.label,
            activate=body.activate,
        )
    except VersionError as exc:
        raise _plain_error(exc) from exc
    return FacetVersionResponse(**v.model_dump(), is_active=body.activate)


@router.get("/facets/{facet}/versions", response_model=list[FacetVersionResponse])
async def list_facet_versions(project_id: str, facet: str) -> list[FacetVersionResponse]:
    _check_facet(facet)
    versions = await song_db.list_versions(project_id, facet)
    active = (await song_db.get_active_map(project_id)).get(facet)
    return [
        FacetVersionResponse(**v.model_dump(), is_active=(v.id == active))
        for v in reversed(versions)
    ]


@router.post("/facets/{facet}/restore", response_model=FacetVersionResponse, status_code=201)
async def restore_facet(project_id: str, facet: str, body: RestoreFacetRequest) -> FacetVersionResponse:
    _check_facet(facet)
    try:
        v = await store.restore_facet(project_id, facet, body.version_id, author=USER_AUTHOR)
    except VersionError as exc:
        raise _plain_error(exc) from exc
    return FacetVersionResponse(**v.model_dump(), is_active=True)


@router.post("/facets/{facet}/activate")
async def activate_facet(project_id: str, facet: str, body: ActivateFacetRequest) -> dict:
    _check_facet(facet)
    try:
        await store.activate_facet_version(project_id, facet, body.version_id)
    except VersionError as exc:
        raise _plain_error(exc) from exc
    return {"ok": True}


@router.get("/decisions", response_model=list[Decision])
async def list_decisions(project_id: str) -> list[Decision]:
    return await song_db.list_decisions(project_id)


@router.post("/decisions", response_model=Decision, status_code=201)
async def record_decision(project_id: str, body: RecordDecisionRequest) -> Decision:
    return await song_db.insert_decision(project_id, body.model_dump())


@router.patch("/phase")
async def set_phase(project_id: str, body: SetPhaseRequest) -> dict:
    """Move between creating and refining. Only the person can do this."""
    await projects_db.update_project_active_state(project_id, {"phase": body.phase})
    return {"phase": body.phase}
