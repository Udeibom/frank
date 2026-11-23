"""
Frank's job worker (core-path spec 15, requirement 1).

Runs next to Frank's Hugging Face Space, which has far more memory than the 512 MB API server. It claims queued
jobs from the database (`claim_job`), runs the very same runner functions the API would, and beats every 15 s
so the API knows to send work here. Started by the Space (spaces/frank-ears/app.py):

    python -m app.worker

Env: the backend's usual settings (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GROQ_API_KEY, ...) plus
WORKER_NAME (default "ears-worker") and WORKER_JOBS (jobs at once, default 2).
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
import signal
import time
from datetime import datetime, timezone

log = logging.getLogger("frank.worker")

NAME = os.environ.get("WORKER_NAME", "ears-worker")
JOBS_AT_ONCE = max(1, int(os.environ.get("WORKER_JOBS", "2")))
BEAT_S = 15
IDLE_S = 2.0
FAILED_PLAINLY = "Something went wrong on my side while working on this. Nothing you made was lost. Want to try again?"
RESTARTED = "Frank restarted while working on this — want to try again?"

_running: set[str] = set()
_stop = asyncio.Event()


def memory_limit_mb() -> int | None:
    """The memory this container may use (cgroup), so the limit is measured, not assumed."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = open(path).read().strip()
        except OSError:
            continue
        if raw.isdigit():
            return int(raw) // (1024 * 1024)
    return None


def _sb():
    from app.db.client import get_supabase

    return get_supabase()


def _beat() -> None:
    from app.services.jobs.heavy import memory_mb

    cur, peak = memory_mb()
    info = {"host": platform.node(), "running": sorted(_running), "mem_mb": cur, "peak_mb": peak,
            "limit_mb": memory_limit_mb(), "jobs_at_once": JOBS_AT_ONCE}
    _sb().rpc("worker_beat", {"p_worker": NAME, "p_info": info}).execute()
    if _running:
        # Keep this worker's jobs fresh, so the API's stale check only ends jobs whose worker really stopped.
        _sb().table("async_jobs").update({"claimed_at": datetime.now(timezone.utc).isoformat()}) \
            .in_("id", sorted(_running)).execute()


async def _heartbeat() -> None:
    while not _stop.is_set():
        try:
            await asyncio.to_thread(_beat)
        except Exception:  # noqa: BLE001 - a missed beat only means the API runs a job itself
            log.warning("heartbeat failed", exc_info=True)
        try:
            await asyncio.wait_for(_stop.wait(), BEAT_S)
        except asyncio.TimeoutError:
            pass


def _fail_my_orphans() -> int:
    """Jobs this worker had claimed before it restarted can never finish: end them plainly."""
    rows = _sb().table("async_jobs").update({"status": "failed", "error": RESTARTED}) \
        .eq("claimed_by", NAME).in_("status", ["pending", "processing"]).execute().data
    return len(rows or [])


async def _run(job: dict) -> None:
    from app.services import region
    from app.services.jobs import dispatch
    from app.services.jobs.heavy import release_memory

    job_id = job["id"]
    payload = job.get("payload") or {}
    _running.add(job_id)
    token = region.set_region(payload.get("region"))
    started = time.monotonic()
    try:
        fn = dispatch.resolve(payload["runner"])
        args = await asyncio.to_thread(dispatch.unstage, payload.get("args") or [])
        log.info("job %s %s starting", job_id, payload["runner"])
        await fn(job_id, *args)
    except Exception:  # noqa: BLE001 - runners record their own plain failure; this only catches the rest
        log.warning("job %s raised", job_id, exc_info=True)
    finally:
        region._region.reset(token)
        _running.discard(job_id)
        await asyncio.to_thread(dispatch.drop_staged, payload.get("args") or [])
        try:
            row = (await asyncio.to_thread(
                lambda: _sb().table("async_jobs").select("status").eq("id", job_id).single().execute().data)) or {}
            if row.get("status") in ("pending", "processing"):
                await asyncio.to_thread(lambda: _sb().table("async_jobs").update(
                    {"status": "failed", "error": FAILED_PLAINLY}).eq("id", job_id).execute())
        except Exception:  # noqa: BLE001
            log.warning("could not check job %s at the end", job_id, exc_info=True)
        release_memory()
        log.info("job %s done in %.0fs", job_id, time.monotonic() - started)


async def _claim() -> dict | None:
    rows = await asyncio.to_thread(lambda: _sb().rpc("claim_job", {"p_worker": NAME}).execute().data)
    return rows[0] if rows else None


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        n = await asyncio.to_thread(_fail_my_orphans)
        log.info("worker %s up (%d jobs at once, memory limit %s MB); ended %d orphaned job(s)",
                 NAME, JOBS_AT_ONCE, memory_limit_mb(), n)
    except Exception:  # noqa: BLE001
        log.warning("could not end orphaned jobs", exc_info=True)
    beat = asyncio.create_task(_heartbeat())
    tasks: set[asyncio.Task] = set()
    while not _stop.is_set():
        tasks = {t for t in tasks if not t.done()}
        job = None
        if len(tasks) < JOBS_AT_ONCE:
            try:
                job = await _claim()
            except Exception:  # noqa: BLE001
                log.warning("claim failed", exc_info=True)
        if job:
            tasks.add(asyncio.create_task(_run(job)))
            continue
        try:
            await asyncio.wait_for(_stop.wait(), IDLE_S)
        except asyncio.TimeoutError:
            pass
    await asyncio.gather(*tasks, return_exceptions=True)
    beat.cancel()


def _stop_now(*_: object) -> None:
    _stop.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop_now)
    asyncio.run(main())
