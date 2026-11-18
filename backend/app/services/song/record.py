"""
Assemble the Song Record: the new facets plus links to what already exists
(lyrics, fingerprint, beat, vocal, mix). Reads only; nothing here writes.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.db import beat as beat_db
from app.db import feel as feel_db
from app.db import lyrics as lyrics_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.db import song as song_db
from app.db import voice as voice_db
from postgrest.exceptions import APIError
from app.models.song import FACETS, SongRecord


def _beat_summary(version: Optional[dict]) -> Optional[dict[str, Any]]:
    if not version:
        return None
    params = version.get("params") or {}
    sections = [
        {
            "index": s.get("index"),
            "name": s.get("label") or s.get("name"),
            "bars": s.get("bars"),
            "layers": s.get("layers"),
        }
        for s in params.get("sections", [])
    ]
    return {"label": version.get("label"), "sections": sections, "lead": params.get("lead_info")}


def _vocal_summary(take_count: int, take: Optional[dict], comp: Optional[dict]) -> Optional[dict[str, Any]]:
    if not take_count and not comp:
        return None
    active = "best-of-takes version" if comp else ("a recorded take" if take else "none chosen")
    return {
        "takes_recorded": take_count,
        "active": active,
        "tuned": bool(take and take.get("processed_url")),
    }


def _mix_summary(version: Optional[dict]) -> Optional[dict[str, Any]]:
    if not version:
        return None
    return {"label": version.get("label"), "params": version.get("mix_params") or {}}


async def _parallel(*coros):
    """
    Run independent database reads at the same time. The database client is blocking, so each
    read runs in its own worker thread; the reads do not depend on each other. Each read costs
    a round trip, and doing eight of them one after another made the sidebar summary slow.
    """
    return await asyncio.gather(*(asyncio.to_thread(asyncio.run, c) for c in coros))


async def _state_or_empty(project_id: str) -> dict:
    """The project's pointers, or nothing if the row is missing (an older project made another way)."""
    try:
        return await projects_db.get_project_active_state(project_id) or {}
    except APIError:
        return {}


def _maybe(coro_fn, key: Optional[str]):
    """A read that only happens when there is something to read."""
    async def _run():
        return await coro_fn(key) if key else None
    return _run()


async def get_record(project_id: str) -> SongRecord:
    """Read everything Frank knows about this song. Empty things stay empty."""
    # Stage 1: everything that needs only the project id.
    state, active_map, fingerprint_row, takes, decisions = await _parallel(
        _state_or_empty(project_id),
        song_db.get_active_map(project_id),
        feel_db.get_latest_fingerprint(project_id),
        voice_db.list_takes(project_id),
        song_db.list_decisions(project_id),
    )

    # Stage 2: things the active pointers point at. Only the active facet versions are read,
    # so a long history never hides the live one (a plain list read is capped at 1000 rows).
    active_ids = [vid for vid in active_map.values() if vid]
    versions, lyrics_row, beat_row, take_row, comp_row, mix_row = await _parallel(
        song_db.get_versions(project_id, active_ids),
        _maybe(lyrics_db.get_version, state.get("active_lyrics_id")),
        _maybe(beat_db.get_beat_version, state.get("active_beat_version_id")),
        _maybe(voice_db.get_take, state.get("active_vocal_id")),
        _maybe(voice_db.get_comp, state.get("active_comp_id")),
        _maybe(mix_db.get_mix_version, state.get("active_mix_id")),
    )
    by_id = {v.id: v for v in versions}

    facets: dict[str, Optional[dict[str, Any]]] = {}
    for facet in FACETS:
        vid = active_map.get(facet)
        facets[facet] = by_id[vid].content if vid in by_id else None

    return SongRecord(
        project_id=project_id,
        phase=state.get("phase") or "creating",
        facets=facets,
        lyrics=(lyrics_row or {}).get("content") or None,
        fingerprint=(fingerprint_row or {}).get("fingerprint") or None,
        beat=_beat_summary(beat_row),
        vocal=_vocal_summary(len(takes), take_row, comp_row),
        mix=_mix_summary(mix_row),
        decisions=decisions,
    )


async def active_facet(project_id: str, facet: str) -> Optional[dict[str, Any]]:
    """Content of the active version of a facet, or None."""
    active_map = await song_db.get_active_map(project_id)
    vid = active_map.get(facet)
    if not vid:
        return None
    versions = await song_db.get_versions(project_id, [vid])
    return versions[0].content if versions else None


async def active_melody(project_id: str) -> Optional[tuple[str, dict[str, Any]]]:
    """(version id, content) of the active melody, or None when there is none."""
    active_map = await song_db.get_active_map(project_id)
    vid = active_map.get("melody")
    if not vid:
        return None
    versions = await song_db.get_versions(project_id, [vid])
    return (vid, versions[0].content) if versions else None


def has_first_draft(record: SongRecord) -> bool:
    """A first complete draft: a beat plus a vocal or a confirmed melody (spec 01, requirement 5.2)."""
    melody = record.facets.get("melody") or {}
    has_music = record.beat is not None
    has_voice_or_tune = record.vocal is not None or bool(melody.get("confirmed"))
    return has_music and has_voice_or_tune


async def system_with_brief(project_id: str, system: str, role: Optional[str] = None) -> str:
    """
    The room's system prompt plus the shared song brief, so every room speaks from the same song
    (song-record spec 01, task 6). If the record cannot be read the room still works with its own prompt.
    """
    import logging

    from app.services.song.brief import build_brief

    from app.services.team import roles as team

    log = logging.getLogger(__name__)
    room = next((r for r, br in team.ROLE_FOR_BRIEF.items() if br == role), "feel")
    try:
        record = await get_record(project_id)
        # The song moves to "refining" by itself once a first full draft exists (spec 07, requirement 4.3).
        if record.phase == "creating" and has_first_draft(record):
            try:
                await projects_db.update_project_active_state(project_id, {"phase": "refining"})
                record.phase = "refining"
            except Exception:  # noqa: BLE001
                log.warning("could not switch the song to refining", exc_info=True)
        brief = build_brief(record, role)
        phase = record.phase
    except Exception:  # noqa: BLE001
        log.warning("could not build the song brief", exc_info=True)
        return f"{system}\n\n{team.team_block(room, 'creating', False)}"
    from app.services.team import conversation_store as convo

    try:
        previous = [t["content"] for t in (await convo.history(project_id, room)) if t["role"] == "assistant"]
    except Exception:  # noqa: BLE001
        previous = []
    return (f"{system}\n\n{team.team_block(room, phase, team.may_mention(previous))}"
            f"\n\n--- THE SONG SO FAR (the whole team shares this; do not contradict it) ---\n{brief}")
