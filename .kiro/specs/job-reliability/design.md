# Job Reliability — Design

## Overview

`async_jobs.updated_at` is set by a database trigger on every update, so it records the last status change. A job still active long after its last change has been abandoned. Three layers:

```
worker fails ─▶ mark_failed with retries ───────────────────────── (most failures end here)
poll         ─▶ is_stale(job)? ─▶ conditional update → failed ──── (worker died / write lost)
startup      ─▶ fail jobs active since before this process began ─ (restart / free-tier sleep)
```

## Decisions

- **Stale limit: 10 minutes.** The slowest normal job measured is a beat on a slow uplink: render ~15 s plus 9 uploads at ~17 s each, about 3 minutes. 10 minutes leaves wide margin.
- **Conditional write.** The update filters on `id`, `status in (pending, processing)` and `updated_at < cutoff` together. A job that completed between the read and the write doesn't match, so nothing is clobbered.
- **Startup cutoff is the process start time**, not "everything". Jobs from this process (created after start) are untouched, which keeps it correct even if several workers start together.
- **Pure core.** `is_stale` and the retry helper do no I/O and are property-tested.
- **Browser polls up to 12 minutes**, every 2 s for the first minute and then every 5 s, so it hears the server's "failed" instead of timing out first.

## Limits

- There is no heartbeat. A job that genuinely runs past 10 minutes is reported failed. If it later finishes, its result is still saved (`mark_complete` is unconditional), so no work is lost, but the user was told it failed.
- In a rolling deploy, where a new process starts while an old one is still working, the startup sweep could fail the old process's live jobs. That doesn't apply to a single free-tier instance.
