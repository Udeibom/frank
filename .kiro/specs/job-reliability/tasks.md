# Job Reliability — Implementation Plan

- [x] 1. Pure core
  - [x] 1.1 `services/jobs/staleness.py`: `is_stale`, stale limit, retry helper
    - _Requirements: 2.1, 2.3, 2.4, 1.1_
  - [x] 1.2 Property tests (`tests/test_properties_jobs.py`, 6 tests); mutations caught: stale check ignoring status, retry giving up after one try
    - _Requirements: 1.1, 2.1, 2.3_

- [x] 2. Database writes
  - [x] 2.1 `mark_failed` retries
    - _Requirements: 1.1, 1.2_
  - [x] 2.2 Conditional `fail_if_stale` (one job) and `fail_jobs_active_before` (sweep)
    - _Requirements: 2.2, 3.1_

- [x] 3. Wiring
  - [x] 3.1 Status route resolves stale jobs on poll
    - _Requirements: 2.1_
  - [x] 3.2 Startup sweep in the app lifespan, retried, never blocking startup
    - _Requirements: 3.1, 3.2_
  - [x] 3.3 Frontend `pollJob`: 12-minute window, 2 s then 5 s
    - _Requirements: 4.1, 4.2_

- [x] 4. Verify live
  - [x] 4.1 20-minute-old processing and pending jobs → failed on poll; fresh job untouched; old complete job untouched (5/5)
    - _Requirements: 2.1, 2.3_
  - [x] 4.2 Restart marks an old active job failed and leaves a job created after start alone. The first attempt FAILED: a network blip hit the one-shot sweep. Added retries; the rerun passed.
    - _Requirements: 3.1, 3.2_

## Not covered
- The race in 2.2 (a job completing between read and write) is guarded by the conditional update but was not reproduced live.
- No heartbeat: a job that truly runs past 10 minutes is reported failed, though its result is still saved if it later finishes.
