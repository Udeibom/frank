# Refine Loop - Implementation Plan (spec 08)

Depends on 03 (Listener), 04 (typed operations, partial re-render), 07 (team, actions).

- [x] 1. Direction model, proposals table (migration 007)
  - _Requirements: 2.1, 3.1_
  - Evidence: `services/refine/models.py`; `db/migrations/007_refine_proposals.sql` applied Nov 18; `db/refine.py`.
- [x] 2. Proposer from Listener findings; disagreement with a measurement records a mismatch
  - _Requirements: 1.1-1.3, 2.1_
  - Evidence: `services/refine/propose.py` (findings only, one model call, every direction checked by
    `ops.apply_audible`, distinct), `routers/refine.py` `disagree` + `meaning_question`.
- [x] 3. Preview runner (in-memory plan, partial re-render, previews prefix, no writes)
  - _Requirements: 2.2, 2.3_
  - Evidence: `jobs/refine_runner.py`, `beat.render_excerpt`; prod Nov 18: preview + before cut, no version written.
    2.3: two 8-bar sections took 75 s on prod, so previews play one section unless the pair fits 12 bars
    (`propose.PREVIEW_MAX_BARS`). Re-measure after that deploy.
- [x] 4. Commit path and decision record; "how does that feel?"
  - _Requirements: 3.1, 3.2_
  - Evidence: `routers/refine.py` `choose` (operations or mix job, `song_decisions` row, stored conversation turn);
    RefinePanel keeps the other directions and offers more ideas.
- [x] 5. Experiments menu and runner
  - _Requirements: 4.1, 4.2_
  - Evidence: `services/refine/experiments.py experiment_menu`; outcome recorded as a decision marked experiment.
    Speed change left out: typed operations cannot change the speed of a saved song.
- [x] 6. Version resolver and "give it back" action
  - _Requirements: 5.1, 5.2_
  - Evidence: `services/refine/resolve.py`, `POST /versions/resolve`, Beat/Mix conversations resolve before the model.
- [x] 7. UI: direction cards, A/B compare, version history per layer
  - _Requirements: 2.4, 5.3_
  - Evidence: `components/studio/RefinePanel.tsx` (A/B keeps the position), `VersionChoice.tsx`, rename in
    `BeatVersions.tsx` / `MixVersions.tsx`, `PATCH /versions/{layer}/{id}`.
- [x] 8. Property tests, each proved able to fail
  - Evidence: `tests/test_properties_refine.py` (properties 1-4 + model misbehaviour), `scripts/mutate_check.py`:
    5 of 5 mutations caught.
- [x] 9. Demo story 3 end to end on the deployed URL, recorded
  - Evidence: `scripts/ops/e2e.py refine_story`, prod run Nov 18 "E2E OK in 855s" (log in checkpoint 3).
