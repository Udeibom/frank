# Build progress (read this first after an interruption)

Reference point for resuming: "Continue from .kiro/specs/_build-progress.md, checkpoint 5."

Deployed: frontend https://frank-bay-zeta.vercel.app · backend https://frank-api-pzjo.onrender.com (Render srv-dbtv8e0n74is73evdbdg)
Ops (all in the repo, survive restarts): `backend/scripts/ops/render.py wait|logs|events|env`,
`backend/scripts/ops/e2e.py` (full HTTP walkthrough on prod, now including demo story 3; `E2E_REFINE=0` skips it),
`backend/scripts/ops/sql.py` (needs SUPABASE_ACCESS_TOKEN env), `backend/scripts/mutate_check.py` (proves the refine
properties can fail). Plan of record: `.kiro/specs/_remaining-work.md`.

## Checkpoint 5 (Nov 18): finish and intent (spec 11), taste memory (spec 09)
- Spec 11: parts mixed separately (cached for the beat in use), finishing from an uncompressed render (two-pass
  loudness, true peak, Listener check), before/after, waveform, intent check in their words, one surprise, parts zip.
  VERIFIED ON PRODUCTION: E2E with the finish story OK in 1156 s (loudness -14.7, no clipping; zip 28 MB).
  Renderer fix: parts start on the synth's 64-sample block and their echo is drained (renders no longer depend on
  what was rendered before). Migration 009 is taste (008 went to sing-it).
- Spec 09: signals, promotion/retirement, taste in briefs and direction order, taste page.
  VERIFIED ON PRODUCTION: scripts/ops/rls_check.py "RLS OK" (two users).
- Set-active beat/mix routes now check the version belongs to the song.

## Checkpoint 4 (Nov 18): sing it (spec 06)
- Migration 008 applied (vocal_takes kind/parent/is_harmony/params/facts, user_settings, guide_renders).
- `services/audio/{song_notes, vocal_notes, align, bleed, engineer, guide}.py`; pitch/harmony/comp extended;
  voice routes rewritten with ownership checks; Voice Room: recorder with start point, count-in, practice loop,
  sing-along guide, headphones, one-time delay check, take cards with versions, best-of view with line swap.
- VERIFIED ON PRODUCTION (Nov 18, e6f9140+): walkthrough with the vocal session passes (E2E OK in 669 s):
  placed take, engineer warning on the leaky take, tune, line up, music taken out (7.8 dB), harmony, guide,
  best-of, swap, mix, listen, export.
- Real hums through the tools: listening files in `listening/sing-it-2026-11-18/` (git-ignored) for the founder.
- Not checkable here: the browser timing (lead-in + delay check) with a real microphone.

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

## Next, in order
1. Spec 10 creative director. 2. Spec 02 rest. 3. Spec 12. 4. Spec 13 demo runs.
