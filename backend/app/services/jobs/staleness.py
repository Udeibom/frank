"""
Deciding when a background job has been abandoned (job-reliability spec).

async_jobs.updated_at is set by a database trigger on every update, so it is the
time of the job's last status change. A job still active long after that has no
live worker behind it. Pure functions only, so they can be property-tested.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

ACTIVE_STATUSES = ("pending", "processing")
# Slowest normal job measured is ~3 min (a beat on a slow uplink). Wide margin.
STALE_AFTER = timedelta(minutes=10)

STALE_MESSAGE = "This took too long and stopped partway — want to try again?"
RESTART_MESSAGE = "Frank restarted while working on this — want to try again?"


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a Supabase timestamp (ISO string or datetime) to aware UTC, or None."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_stale(
    job: dict, now: datetime, stale_after: timedelta = STALE_AFTER
) -> bool:
    """True when the job is still active and has not changed for > stale_after.
    A job whose timestamp can't be read is never called stale (don't guess)."""
    if job.get("status") not in ACTIVE_STATUSES:
        return False
    changed = parse_timestamp(job.get("updated_at"))
    if changed is None:
        return False
    return now - changed > stale_after


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    attempts: int = 4,
    base_delay: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run `fn`, retrying on any exception with linear backoff. Re-raises the
    last error after `attempts` tries."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — caller decides what's fatal
            last = exc
            if i < attempts - 1:
                await sleep(base_delay * (i + 1))
    assert last is not None
    raise last
