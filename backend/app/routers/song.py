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


# ── the shape of a sound, for drawing it (frankenstein spec 14, requirement 8.1) ──────────────────────────

from functools import lru_cache as _lru  # noqa: E402

PEAK_BUCKETS = {"vocals", "mixes", "beats", "textures", "hums", "exports", "voice-memos"}


@_lru(maxsize=256)
def _peaks(bucket: str, path: str, points: int) -> tuple[float, ...]:
    import subprocess

    import numpy as np

    from app.db.client import get_supabase

    data = get_supabase().storage.from_(bucket).download(path)
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"],
                         input=data, capture_output=True, timeout=60, check=True).stdout
    del data
    a = np.abs(np.frombuffer(pcm, dtype=np.int16).astype(np.float32)) / 32768.0
    if a.size == 0:
        return ()
    step = max(1, a.size // points)
    p = a[: step * (a.size // step)].reshape(-1, step).max(axis=1)
    top = float(p.max()) or 1.0
    return tuple(round(float(x) / top, 3) for x in p)


@router.get("/peaks")
async def sound_peaks(project_id: str, url: str, points: int = 600) -> dict:
    """The loudest moment per slice of one of Frank's stored sounds, 0..1. The browser only draws it."""
    import asyncio

    from app.config import get_settings
    from app.services.storage.signing import parse_storage_url

    ref = parse_storage_url(url.split("?")[0].replace("/object/sign/", "/object/public/"), get_settings().supabase_url)
    if not ref or ref[0] not in PEAK_BUCKETS:
        raise HTTPException(status_code=400, detail="That isn't one of your song's sounds.")
    try:
        peaks = await asyncio.to_thread(_peaks, ref[0], ref[1], max(50, min(2000, points)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="I couldn't draw that sound just now.") from exc
    return {"peaks": list(peaks)}
