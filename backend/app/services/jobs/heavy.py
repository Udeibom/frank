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


def release_memory() -> None:
    """
    Give freed memory back to the system. Worker threads leave freed audio buffers inside malloc's arenas: measured
    Nov 18, a beat then a listen kept 353 MB resident with threads, 277 MB after malloc_trim. On the 512 MB server
    that difference is what made the next job (an export) run out of memory.
    """
    import ctypes
    import gc

    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass                                    # not glibc (macOS dev machine): nothing to trim


class _HeavyGate:
    """One heavy job at a time; memory is released and logged when each one ends."""

    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(1)

    async def __aenter__(self) -> "_HeavyGate":
        await self._sem.acquire()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        try:
            release_memory()
            log_memory("after heavy job")
        finally:
            self._sem.release()

    def locked(self) -> bool:
        return self._sem.locked()


HEAVY = _HeavyGate()


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
