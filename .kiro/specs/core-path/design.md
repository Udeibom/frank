# Core Path — Design (spec 15)

## 1. The worker (requirement 1)
- `async_jobs` gains `payload jsonb` (runner name, JSON arguments, region), `claimed_by`, `claimed_at`.
  A `worker_heartbeats` table holds each worker's last beat. `claim_job(worker)` takes the oldest pending job
  with a payload, using `FOR UPDATE SKIP LOCKED`.
- `services/jobs/dispatch.py` replaces every `background.add_task(runner, job_id, ...)`. Bytes arguments are
  staged in the private `job-inputs` bucket and replaced by a reference. When a worker has beaten in the last
  45 s, the job is left for it. Otherwise the API pings the worker awake and runs the job itself, as before.
- `app/worker.py` runs on the frank-ears Space (Python 3.11) in its own environment with the backend's
  requirements and system libraries. It claims jobs, runs the same runner functions, beats every 15 s, and
  runs up to 2 jobs at once. On start it fails only jobs claimed by a worker that has stopped beating.
- The API's startup sweep fails only unclaimed jobs. The poll-time stale check ignores claimed jobs whose
  worker is still beating.

## 2. Speed (requirement 2)
- Hum speed: candidate speeds are the reading, half and double. Choose the one closest to what the feeling
  suggests (gentle/slow feelings about 60-80, steady about 80-110, driving 110-140). Across several hums, the
  most consistent reading wins, not the last.
- Ops `slower` and `faster` change `fingerprint.tempo_bpm` for the whole song (about 12% a step, limits
  55-160) and re-render. The prompt lists them and asks for them when the person mentions speed or pace.
- Claim check: after a beat change, the reply is compared with the change lines. A reply that claims a speed
  change when none was made is replaced by the plain change lines.

## 3. Length (requirement 3)
- When the active take is longer than the planned song, sections are added (an extra chorus and verse, then a
  longer outro) until the music is at least as long as the voice. The mix lengthens the beat's last section
  rather than leaving silence under the voice.

## 4. Directions (requirement 4)
- "Try something different" sends the directions already heard. The texture generator moves to a different
  sound and energy on purpose (another instrument family, another movement), and the cache key includes that
  variation.

## 5-6. Words, next step, status
- A `NextStep` line per room, chosen from the song's state. Plain labels. The waking banner listens for the
  health answer and clears. The "first description" is only saved from a real description, never a reaction.

## 7. Proof
- `scripts/ops/e2e_core.py` runs the founder's path with a 4-minute take, from Kaggle (this machine's network
  drops large requests to Render), and writes `docs/demo-runs/`.
