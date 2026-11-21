"""Background job for the Listener: measure the song, then report findings (listener spec 03, req 5.2)."""
from __future__ import annotations

from typing import Optional

from app.db import jobs as jobs_db
from app.services.jobs.heavy import HEAVY, log_memory
from app.db.client import get_supabase
from app.services.listener import findings
from app.services.listener import project as listen_project
from app.services.listener import ears
from app.services import provenance


async def _progress(job_id: str, text: str) -> None:
    """Progress text rides in the job's result while it is still working, so the page can show it."""
    try:
        get_supabase().table("async_jobs").update({"result": {"progress": text}}).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001  progress is a courtesy
        pass


async def run_listen_job(job_id: str, project_id: str, scope: Optional[list[str]], concern: Optional[str]) -> None:
    try:
        await jobs_db.mark_processing(job_id)

        async def say(text: str) -> None:
            log_memory(f"listen: {text}")
            await _progress(job_id, text)

        await say("Waiting for my ears to be free...")
        async with HEAVY:
            report = await listen_project.measure_song(project_id, scope, progress=say)
        found = findings.find_issues(report, concern)
        await say("Having a proper listen...")
        heard = await ears.hear(project_id, report, found, scope, concern)
        if heard:
            provenance.note(project_id, "listen", None, "listened")
        styles = await ears.style_check(project_id)
        if styles and styles.get("finding"):
            from app.services.listener.models import Finding

            found.findings.append(Finding(**styles["finding"]))
            provenance.note(project_id, "listen", None, "style")
        await jobs_db.mark_complete(job_id, {"measurements": report.model_dump(), "findings": found.model_dump(),
                                             "heard": heard, "sounds_like": styles})
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't listen to the song just now — want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
