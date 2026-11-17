"""
One heavy audio job at a time, across every kind of job (ship-it spec 13, requirement 2.1).

The free server has 512 MB. A beat render peaks around 435 MB on its own (measured Nov 17), so two heavy jobs
at once (a beat and a mix, or a hum and an export) would be killed for memory. Every CPU- or memory-heavy step
goes through this one gate; other requests (polling, conversation) keep flowing while a job waits its turn.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

T = TypeVar("T")
HEAVY = asyncio.Semaphore(1)


async def run_heavy(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run blocking work in a worker thread, after any other heavy job has finished."""
    async with HEAVY:
        return await asyncio.to_thread(fn, *args, **kwargs)
