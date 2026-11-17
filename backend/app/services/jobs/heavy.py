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
        log_memory(f"start {getattr(fn, '__name__', 'job')}")
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        finally:
            log_memory(f"end {getattr(fn, '__name__', 'job')}")


def memory_mb() -> tuple[int, int]:
    """(current, peak) resident memory of this process in MB; (0, 0) where /proc is not available."""
    cur = peak = 0
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    cur = int(line.split()[1]) // 1024
                elif line.startswith("VmHWM:"):
                    peak = int(line.split()[1]) // 1024
    except OSError:
        pass
    return cur, peak


def log_memory(label: str) -> None:
    """One line in the server log per heavy step, so memory on the deployed server is measured, not guessed."""
    cur, peak = memory_mb()
    print(f"[memory] {label}: now {cur} MB, peak {peak} MB", flush=True)
