"""
Reference jobs (frankenstein spec 14, requirement 6): hear a song the person pointed at, keep only what Frank heard
in it, and let it steer the feeling of their song.

Every path ends in the same place: a `song_references` row (analysis, licence, attribution), one item in the
`references` facet marked feeling-only with the feeling words and plain differences, and confident hints filling
gaps in the song's direction. Audio is never stored.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.db import feel as feel_db
from app.db import jobs as jobs_db
from app.db import projects as projects_db
from app.db.client import get_supabase
from app.services import provenance
from app.services.intake import merge as merge_svc
from app.services.jobs.heavy import HEAVY, log_memory
from app.services.reference import analyse

log = logging.getLogger("frank.reference_job")


async def _progress(job_id: str, text: str) -> None:
    try:
        get_supabase().table("async_jobs").update({"result": {"progress": text}}).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001
        pass


async def _song_measure(project_id: str) -> Optional[dict]:
    """The person's own song, measured the same way, for the plain differences."""
    from app.db import beat as beat_db
    from app.db import mix as mix_db
    from app.services.storage.signing import fetch_audio_bytes

    state = await projects_db.get_project_active_state(project_id) or {}
    mix = await mix_db.get_mix_version(state["active_mix_id"]) if state.get("active_mix_id") else None
    beat = await beat_db.get_beat_version(state["active_beat_version_id"]) if state.get("active_beat_version_id") else None
    url = (mix or {}).get("render_url") or (beat or {}).get("render_url")
    if not url:
        return None
    data = await asyncio.to_thread(fetch_audio_bytes, url)
    y = await asyncio.to_thread(analyse.decode, data, "mp3")
    del data
    return await asyncio.to_thread(analyse.measure, y)


async def _keep(project_id: str, source: str, meta: dict, result: dict, differences: list[str]) -> dict:
    from app.services.song import record as song_record
    from app.services.song import store

    row = get_supabase().table("song_references").insert({
        "project_id": project_id, "source": source, "title": meta.get("title"), "artist": meta.get("artist"),
        "license": meta.get("license"), "attribution": meta.get("attribution"), "external_id": meta.get("external_id"),
        "analysis": {**result, "differences": differences},
    }).execute().data[0]
    refs = dict(await song_record.active_facet(project_id, "references") or {"items": []})
    items = [i for i in refs.get("items", []) if i.get("reference_id") != row["id"]]
    name = " by ".join(x for x in (meta.get("title"), meta.get("artist")) if x) or "a song you picked"
    items.append({"name": name, "use": "feeling_only", "reference_id": row["id"], "source": source,
                  "loved": result.get("feeling_words", [])[:6], "differences": differences, "active": True})
    await store.write_facet(project_id, "references", {"items": items[-6:]}, author="creative_director",
                            operation=f"reference_{source}", label="A song you pointed at")
    filled: list[str] = []
    if result.get("hints"):
        latest = await feel_db.get_latest_fingerprint(project_id)
        merged, filled, _ = merge_svc.merge_fingerprint((latest or {}).get("fingerprint"), result["hints"])
        if filled:
            saved = await feel_db.save_fingerprint(project_id, merged, (latest or {}).get("conversation_summary"))
            await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
    if meta.get("attribution"):
        await asyncio.to_thread(provenance.note, project_id, "reference", row["id"], "reference",
                                "Reference: a song you pointed at, listened to for its feeling", meta["attribution"])
    return {"reference_id": row["id"], "feeling_words": result.get("feeling_words", []), "differences": differences,
            "filled": filled, "message": message_for(result, differences)}


def message_for(result: dict, differences: list[str]) -> str:
    words = result.get("feeling_words", [])[:4]
    msg = "I listened. It feels " + ", ".join(words) + "." if words else "I listened to it."
    if differences:
        msg += " Next to your song: " + " ".join(differences)
    return msg + " I'll keep that feeling in mind, not copy it. Want me to try a direction with more of it?"


async def run_reference_job(job_id: str, project_id: str, source: str, data: Optional[bytes], ext: str, meta: dict) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        await _progress(job_id, "Waiting for my ears to be free...")
        async with HEAVY:
            log_memory("reference start")
            if data is None and source == "jamendo":
                from app.services.reference import jamendo

                await _progress(job_id, "Fetching the song...")
                data = await asyncio.to_thread(jamendo.fetch_audio, meta["track"])
            await _progress(job_id, "Listening to it closely...")
            result = await asyncio.to_thread(analyse.analyse, data, ext, True)
            del data
            await _progress(job_id, "Comparing it with your song...")
            mine = await _song_measure(project_id)
        differences = analyse.compare(result["measured"], mine) if mine else []
        out = await _keep(project_id, source, meta, result, differences)
        await jobs_db.mark_complete(job_id, out)
    except Exception as exc:  # noqa: BLE001
        log.warning("reference job failed", exc_info=True)
        await jobs_db.mark_failed(job_id, "I couldn't listen to that song just now. Nothing was lost. Want to try again?")
        raise exc


async def run_named_job(job_id: str, project_id: str, text: str) -> None:
    """A song they named: looked up and researched into feeling words. No audio is fetched."""
    from app.services.reference import metadata, research

    try:
        await jobs_db.mark_processing(job_id)
        await _progress(job_id, "Looking that song up...")
        found = await asyncio.to_thread(metadata.look_up, text)
        title = (found or {}).get("title")
        artist = (found or {}).get("artist")
        if not found:
            title, artist = metadata.split_named(text)
        words = list((found or {}).get("feeling_words", []))
        hints: dict = {}
        if (found or {}).get("genre_proximity"):
            hints["genre_proximity"] = found["genre_proximity"]
        await _progress(job_id, "Reading what people say it feels like...")
        notes = await asyncio.to_thread(research.research, title, artist)
        if notes:
            words += [w for w in notes.get("feeling_words", []) if w not in words]
            if notes.get("fullness") in ("sparse", "full"):
                hints["density"] = 0.25 if notes["fullness"] == "sparse" else 0.75
            if notes.get("pace") in ("slow", "fast"):
                words.append("slow" if notes["pace"] == "slow" else "fast")
        result = {"feeling_words": words[:8], "hints": hints, "lookup": found and {k: found[k] for k in ("mbid", "tags")},
                  "research": notes}
        out = await _keep(project_id, "named", {"title": title, "artist": artist, "external_id": (found or {}).get("mbid")},
                          result, [])
        if not words:
            out["message"] = ("I found the song but couldn't tell much about how it feels from here. "
                              "What is it about it that pulls you in: how close and quiet it is, how big, or the way it moves?")
        await jobs_db.mark_complete(job_id, out)
    except Exception as exc:  # noqa: BLE001
        log.warning("named reference job failed", exc_info=True)
        await jobs_db.mark_failed(job_id, "I couldn't look that song up just now. Want to tell me what you love about it instead?")
        raise exc
