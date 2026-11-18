# Voice-to-Export Flow — Implementation Plan

- [x] 1. Shared state across rooms — _Evidence: child 1.1 ticked_
  - [x] 1.1 Project store `refresh()` + `revision`; layout re-syncs on route change; rooms re-read on revision — _Evidence: frontend/store/project.ts (`refresh`, `revision` bumped on every state update); the studio layout.tsx calls `refresh(projectId)` on route change; beat/page.tsx and voice/page.tsx depend on `revision`. Not seen in a browser by me (tsc --noEmit passes)_
    - _Requirements: 1.1, 1.2_

- [x] 2. A new take becomes the vocal the Mix Room uses — _Evidence: children 2.1-2.4 ticked_
  - [x] 2.1 `upload_take` sets `active_vocal_id` (earlier fix) — _Evidence: routers/voice.py:129 `update_project_active_state(... active_vocal_id ...)`_
    - _Requirements: 2.1_
  - [x] 2.2 Uploading or choosing a take clears `active_comp_id` (last chosen wins) — _Evidence: routers/voice.py:129 (upload) and :284 (`POST /voice/active` clears the other pointer); services/audio/vocal_resolution.py `resolve_vocal_url`; test_properties_audio.py test_resolution_returns_one_of_the_available_urls_or_none, test_with_no_comp_the_tuned_take_always_wins, test_an_available_vocal_is_never_silently_dropped (8 passed Nov 18)_
    - _Requirements: 2.2, 2.4_
  - [x] 2.3 Move FFmpeg conversion in `upload_take` off the event loop (found by the audio-architecture hook) — _Evidence: routers/voice.py:110 `await asyncio.to_thread(to_wav, ...)`_
    - _Requirements: 2.1_
  - [x] 2.4 Verified against the live database (take after comp wins; browser Mix Room loads). The mic step used the API, not the browser.
    - _Requirements: 2.2, 2.3, 2.5_

- [ ] 3. Previews never change saved state — _open: 3.2_
  - [x] 3.1 Dedicated vocal-preview job, no mix version and no pointer change — _Evidence: `POST /beat/preview-with-vocal` starts jobs/mix_runner.py `run_vocal_preview_job`, which contains no mix-version insert and no active-pointer update (read, not tested). Refine previews have their own tested rule (test_a_preview_writes_no_version_and_no_pointer), which does not cover this job_
    - _Requirements: 4.1, 4.2_
  - [ ] 3.2 Automated check that a preview leaves the mix list unchanged (needs DB; covered by the browser test in 5.1) — _NOT DONE: no test for the vocal preview job; 5.1 is not done either_
    - _Requirements: 4.3_

- [ ] 4. Close the Mix Room resolution gaps
  - [x] 4.1 Resolve the comp by `active_comp_id`, not `get_latest_comp` — _Evidence: services/jobs/mix_runner.py:161 reads `active_comp_id`; routers/voice.py:241 uses `get_latest_comp` only when no comp is active (the read-only `GET /voice/comp/active`)_
    - _Requirements: 2.3, 2.4_
  - [ ] 4.2 Add an `is_harmony` flag instead of matching the label prefix — _PARTLY DONE: `is_harmony` exists (migration 008, backfilled from the label; set on harmony takes by the voice runner), and mix_runner.py:180 uses it. MISSING: the label-prefix match is still there beside it (mix_runner.py:180, routers/beat.py preview), kept for older takes_
    - _Requirements: 2.4_
  - [x] 4.3 Extract vocal resolution into a pure function (`vocal_resolution.py`) — _Evidence: services/audio/vocal_resolution.py `resolve_vocal_url`, used by mix_runner.py:165_
    - _Requirements: 2.4, 2.5_

- [ ] 5. Browser-driven integration test (Playwright MCP)
  - [ ] 5.1 Click through Voice → Beat → Mix and compare each room with `project_active_state` — _NOT DONE: needs a browser. scripts/ops/e2e.py walks the same rooms over HTTP against the deployed backend and passed (build-progress Nov 18), but it is not a browser run and does not read `project_active_state` after each step_
    - _Requirements: 1.2, 3.1, 3.2, 7.1_
  - [ ] 5.2 Export Room loads `active_mix_id` and records `mix_version_id` — _PARTLY DONE: export/page.tsx picks `active_mix_id` and `run_export_job` stores `mix_version_id` on the export (export_db.create_export_sync); the export step of e2e.py passed on production. MISSING: the browser check this task asks for; requirement 5.2 (no mix: explain and link to the Mix Room) not checked_
    - _Requirements: 5.1, 5.3, 5.4_

- [ ] 6. Property-based tests
  - [x] 6.1 Vocal resolution properties (`backend/tests/test_properties_audio.py`) — _Evidence: test_resolution_returns_one_of_the_available_urls_or_none, test_with_no_comp_the_tuned_take_always_wins, test_an_available_vocal_is_never_silently_dropped; 8 passed Nov 18_
    - _Requirements: 2.4_
  - [ ] 6.2 Pointer moves never delete rows or files — _NOT DONE: no test; `DELETE /voice/takes/{id}` exists (routers/voice.py:169) and its soft-delete behaviour is not tested_
    - _Requirements: 6.1, 6.2_
