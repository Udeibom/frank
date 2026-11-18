# Build progress (read this first after an interruption)

Reference point for resuming: "Continue from .kiro/specs/_build-progress.md, checkpoint 3."

Deployed: frontend https://frank-bay-zeta.vercel.app · backend https://frank-api-pzjo.onrender.com (Render srv-dbtv8e0n74is73evdbdg)
Ops (all in the repo, survive restarts): `backend/scripts/ops/render.py wait|logs|events|env`,
`backend/scripts/ops/e2e.py` (full HTTP walkthrough on prod, now including demo story 3; `E2E_REFINE=0` skips it),
`backend/scripts/ops/sql.py` (needs SUPABASE_ACCESS_TOKEN env), `backend/scripts/mutate_check.py` (proves the refine
properties can fail). Plan of record: `.kiro/specs/_remaining-work.md`.

## Checkpoint 3 (Nov 18): refine loop (spec 08)
- Migration 007 `refine_proposals` applied.
- `services/refine/{models, experiments, propose, resolve}.py`, `jobs/refine_runner.py`, `routers/refine.py`.
- Listen -> findings -> ready-made directions + one model call -> each checked by applying it to a copy and composing
  the score (`ops.apply_audible`: an edit that changes nothing audible is refused in plain words) -> 2-3 distinct.
  No clear cause -> one-change experiments (thinner verses, fuller choruses, new tune idea unless hummed, warmer keys,
  more space on the voice).
- Preview: only the changed section (plus its neighbour when both fit in 12 bars), at the song's stored level, plus a
  "before" cut from the current song for A/B. Writes no version, no pointer (property-tested, and checked on prod).
- Choose: new version + active + decision record. Disagree: decision with the mismatch, one question about the word.
- Version resolver in Beat and Mix conversations ("the second version", "before I changed the chorus", "yesterday");
  rename versions. Frontend: RefinePanel, VersionChoice, "Something feels off" in Beat and Mix Rooms.
- Bugs found and fixed on the way: try_another on a silent part, bigger past the top, swapping to the sound already
  playing (all were silent no-ops); rooms showed the old version after an edit (stale pointer).
- VERIFIED ON PRODUCTION (Nov 18, d65db8f): story 3 passes inside the walkthrough (E2E OK in 855 s). Preview took
  75 s for two 8-bar sections, so previews now play one section unless the pair fits in 12 bars (fix in checkpoint 3b).

## Checkpoint 2 (Nov 19): deployment, typed ops, team conversation basics
- Render Docker + Vercel live; 512 MB fixes; typed operations; stable section identity; planner + energy curve.
- Team: Gemini fallback, plain guard, stored conversations (migration 006), role cards, mention rule, phase switch.

## Known issues
- One intermittent test failure seen once in a 130-test run (did not reproduce). Watch for it.
- Beat render takes about 4 minutes on the free server; committing a beat direction re-renders the whole song.
- `/beat/versions/active` and `/mix/versions/active` don't check the version belongs to the project (fix in spec 13 audit).

## Next, in order
1. Spec 06 sing it. 2. Spec 11 finish and intent. 3. Specs 09, 10, 02 rest, 12, then 13 demo runs.
