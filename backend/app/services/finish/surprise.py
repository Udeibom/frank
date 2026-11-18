"""
One surprise, never a replacement (finish-and-intent spec 11, requirement 4).

After the person's version is complete, Frank may offer ONE unexpected alternative: an extra beat version that
differs in one bold way, heard with their voice. It is never made active; the person can use it or skip it.
Offered at most once per song (recorded in the decisions log).
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.generation.beat import SectionPlan

BACKBONE = ("drums", "bass", "pad", "strings", "arp")


def choose_idea(sections: list[SectionPlan]) -> tuple[str, str, list[dict[str, Any]]]:
    """
    (title, plain sentence, typed operations). A full song gets stripped down to keys and tune; a sparse one
    gets a whole new take with the same feeling. Pure, so it can be tested.
    """
    busy = sum(len(s.layers) for s in sections) / max(1, len(sections))
    if busy >= 3.5:
        ops = []
        for part in BACKBONE:
            where = [s.index for s in sections if part in s.layers]
            if where:
                ops.append({"op": "remove_part", "part": part, "section": where})
        if ops:
            return ("Stripped right back", "Just the keys, the tune and your voice: the whole song, bare.", ops[:5])
    return ("A different take", "The same feeling, played a different way from start to finish.", [{"op": "another_song"}])


async def offered_before(project_id: str) -> bool:
    from app.db import song as song_db

    for d in await song_db.list_decisions(project_id, limit=100):
        if (d.options or [{}])[0].get("kind") == "surprise":
            return True
    return False


async def run_surprise_job(job_id: str, project_id: str) -> None:
    """Build the idea as an extra beat version (not active), mix it with the voice as a throwaway preview."""
    import asyncio

    from app.db import jobs as jobs_db
    from app.db import song as song_db
    from app.services.generation import ops as ops_mod
    from app.services.jobs import beat_runner, mix_runner
    from app.services.jobs.heavy import HEAVY

    try:
        await jobs_db.mark_processing(job_id)
        if await offered_before(project_id):
            await jobs_db.mark_failed(job_id, "I've already shown you my one idea for this song.")
            return
        sections, fp, seed, lead = await beat_runner._load_active_arrangement(project_id)
        title, plain, raw = choose_idea(sections)
        new, new_seed, changes, _ = ops_mod.apply_audible(sections, seed, raw, fp, lead)
        async with HEAVY:
            version = await asyncio.to_thread(
                beat_runner._rerender_and_persist_sync, project_id, new, fp, f"Frank's idea: {title.lower()}", new_seed,
                lead, changes, raw,
            )
        layers = await mix_runner._resolve_layers(project_id)
        layers.update(beat_url=version["render_url"], parts={}, beat_sections=version["params"].get("sections", []))
        preview: Optional[dict] = None
        if layers.get("vocal_url"):
            from app.routers.mix import DEFAULT_MIX_PARAMS

            async with HEAVY:
                preview = await asyncio.to_thread(mix_runner._render_preview_sync, layers, dict(DEFAULT_MIX_PARAMS))
        await song_db.insert_decision(project_id, {
            "summary": f"Frank offered one surprise: {title.lower()}", "rationale": plain, "proposed_by": "frank",
            "options": [{"kind": "surprise", "beat_version_id": version["id"], "title": title}],
        })
        await jobs_db.mark_complete(job_id, {
            "title": title, "plain": plain, "beat_version_id": version["id"], "label": version.get("label"),
            "render_url": (preview or {}).get("render_url") or version["render_url"],
            "message": f"Before we finish, I tried one idea: {plain} Your version stays exactly as it is. Want to hear it?",
        })
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "My surprise idea didn't come together. Your song is safe as it is.")
        except Exception:  # noqa: BLE001
            pass
        raise exc
