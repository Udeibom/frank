"""
Where a job runs (core-path spec 15, requirement 1).

Frank's API runs on a 512 MB server. On 22 Nov a 4-minute take made it run out of memory four times, and every
job it was doing failed. Heavy work now goes to a worker on Frank's own Hugging Face Space, which has far more
memory: the job and its arguments wait in `async_jobs.payload`, and the worker claims them (`claim_job`).

When no worker has checked in recently, the API wakes it and runs the job itself, exactly as before. A queued job
the worker never picks up is rescued by the API (`rescue_if_abandoned`), so nothing waits forever.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import BackgroundTasks

log = logging.getLogger("frank.dispatch")

ALIVE_WITHIN = timedelta(seconds=45)       # a worker beats every 15 s
RESCUE_AFTER = timedelta(seconds=90)       # a queued job nobody took by then runs here instead
INPUTS_BUCKET = "job-inputs"
_alive_cache: dict[str, Any] = {"at": 0.0, "value": False}


def runner_name(fn: Callable) -> str:
    return f"{fn.__module__}:{fn.__qualname__}"


def resolve(name: str) -> Callable:
    module, _, attr = name.partition(":")
    obj: Any = importlib.import_module(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def worker_alive() -> bool:
    """True when a worker has beaten recently. Cached for 10 s so a busy room does not ask on every request."""
    now = time.monotonic()
    if now - _alive_cache["at"] < 10:
        return bool(_alive_cache["value"])
    alive = False
    try:
        from app.db.client import get_supabase

        since = (datetime.now(timezone.utc) - ALIVE_WITHIN).isoformat()
        rows = get_supabase().table("worker_heartbeats").select("worker").gt("beat_at", since).limit(1).execute().data
        alive = bool(rows)
    except Exception:  # noqa: BLE001 - when in doubt, run it here
        log.warning("could not read worker heartbeats", exc_info=True)
    _alive_cache.update(at=now, value=alive)
    return alive


def _wake_worker() -> None:
    """Calling the Space's health endpoint wakes a sleeping Space; the worker starts with it."""
    try:
        from app.services.remote import spaces

        spaces.available("ears")
    except Exception:  # noqa: BLE001
        pass


def _stage(job_id: str, args: list[Any]) -> list[Any]:
    """Bytes cannot sit in a database row: they go to the private inputs bucket and the worker fetches them."""
    from app.db.client import get_supabase

    out: list[Any] = []
    for i, a in enumerate(args):
        if isinstance(a, (bytes, bytearray)):
            path = f"{job_id}/{i}.bin"
            get_supabase().storage.from_(INPUTS_BUCKET).upload(path, bytes(a), {"content-type": "application/octet-stream"})
            out.append({"__bytes__": path})
        else:
            out.append(_jsonable(a))
    return out


def unstage(args: list[Any]) -> list[Any]:
    from app.db.client import get_supabase

    out = []
    for a in args:
        if isinstance(a, dict) and set(a) == {"__bytes__"}:
            out.append(get_supabase().storage.from_(INPUTS_BUCKET).download(a["__bytes__"]))
        else:
            out.append(a)
    return out


def drop_staged(args: list[Any]) -> None:
    paths = [a["__bytes__"] for a in args if isinstance(a, dict) and set(a) == {"__bytes__"}]
    if paths:
        try:
            from app.db.client import get_supabase

            get_supabase().storage.from_(INPUTS_BUCKET).remove(paths)
        except Exception:  # noqa: BLE001
            log.warning("could not remove staged inputs", exc_info=True)


async def start(background: BackgroundTasks, job: dict, fn: Callable, *args: Any) -> None:
    """Queue the job for the worker, or run it here when no worker is available."""
    from app.services import region

    job_id = job["id"]
    if await asyncio.to_thread(worker_alive):
        try:
            staged = await asyncio.to_thread(_stage, job_id, list(args))
            payload = {"runner": runner_name(fn), "args": staged, "region": region.current()}
            from app.db.client import get_supabase

            await asyncio.to_thread(
                lambda: get_supabase().table("async_jobs").update({"payload": payload}).eq("id", job_id).execute())
            return
        except Exception:  # noqa: BLE001 - queueing failed: run it here rather than lose it
            log.warning("could not queue job %s; running it here", job_id, exc_info=True)
    else:
        background.add_task(asyncio.to_thread, _wake_worker)
    background.add_task(fn, job_id, *args)


async def rescue_if_abandoned(job: dict, background: BackgroundTasks) -> bool:
    """
    A queued job that no worker took within RESCUE_AFTER runs here instead (the worker fell asleep or broke).
    Claimed by "api" with a conditional update, so it can never run twice. True when this call started it.
    """
    from app.db.client import get_supabase
    from app.services import region
    from app.services.jobs.staleness import parse_timestamp

    if job.get("status") != "pending" or not job.get("payload") or job.get("claimed_by"):
        return False
    made = parse_timestamp(job.get("created_at"))
    if made is None or datetime.now(timezone.utc) - made < RESCUE_AFTER:
        return False
    taken = await asyncio.to_thread(lambda: get_supabase().table("async_jobs").update(
        {"claimed_by": "api", "claimed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job["id"]).eq("status", "pending").is_("claimed_by", "null").execute().data)
    if not taken:
        return False
    payload = job["payload"]
    args = await asyncio.to_thread(unstage, payload.get("args") or [])
    fn = resolve(payload["runner"])
    log.warning("rescuing job %s (%s): no worker took it", job["id"], payload["runner"])

    async def run() -> None:
        token = region.set_region(payload.get("region"))
        try:
            await fn(job["id"], *args)
        finally:
            region._region.reset(token)
            await asyncio.to_thread(drop_staged, payload.get("args") or [])

    background.add_task(run)
    return True
