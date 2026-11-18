# Beat Room — Implementation Plan

- [ ] 1. Beat Room entry state — _open: 1.2_
  - [x] 1.1 Detect fingerprint presence; show the right greeting and "Build the beat" — _Evidence: frontend/app/(studio)/[projectId]/beat/page.tsx loads the fingerprint and versions on entry and shows one of three greetings (beat exists, feel ready, nothing yet); generateBeat is called with the fingerprint. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 1.1, 1.2_
  - [ ] 1.2 Beat-First abbreviated feel discovery; create and save a simplified fingerprint — _NOT DONE: the page asks "how do you want it to move?" but nothing in it saves a fingerprint; with none, generateBeat sends an empty one and the server fills defaults. The start screen added by start-from-any-input (components/studio/StartSurface.tsx) is the closest thing and is that spec's, not this one's_
    - _Requirements: 1.3, 1.4_

- [x] 2. Section timeline component — _Evidence: children 2.1-2.2 ticked_
  - [x] 2.1 `components/studio/BeatTimeline.tsx` — colored blocks, scrub, playing highlight — _Evidence: BeatTimeline.tsx (SECTION_TINT blocks, `onSeek`, `playingIndex` from progress). Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 3.1, 3.2_
  - [x] 2.2 Section label editing (label-only persist) — _Evidence: BeatTimeline.tsx label editing; `PATCH /beat/sections/{section_index}` (routers/beat.py `update_section`) changes the label in the stored plan only, no re-render. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me; no test_
    - _Requirements: 3.3, 10.3_

- [ ] 3. Stem layer view — _open: 3.1_
  - [ ] 3.1 `components/studio/BeatTimeline.tsx` — plain-language layers, mute toggle triggers re-render — _NOT DONE: the timeline shows only how many layers each section has ("3 layers"); there is no per-layer list and no mute toggle. `muteStem` and `addStem` in lib/api/beat.ts and the `/beat/mute-stem` and `/beat/add-stem` routes exist but nothing in the Beat Room calls them. Layers can only be changed by talking to Frank (typed operations) or in the Mix Room (components/studio/StemBalance.tsx). Was ticked without evidence_
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 4. Beat versions panel — _Evidence: child 4.1 ticked_
  - [x] 4.1 Collapsible list, per-version play, set active, label editing — _Evidence: components/studio/BeatVersions.tsx (`onSetActive`, `onRename`, `playingId`); `GET /beat/versions`, `POST /beat/versions/active` (routers/beat.py). Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 7.2, 7.3, 7.4_

- [x] 5. Beat conversation — _Evidence: children 5.1-5.4 ticked_
  - [x] 5.1 Wire conversation to `POST /projects/{id}/beat/conversation` — _Evidence: routers/beat.py `beat_conversation`; beat/page.tsx `handleSend`; tests/test_team_rooms.py test_each_room_stores_the_exchange_and_uses_the_earlier_summary[beat] (model faked)_
    - _Requirements: 9.4_
  - [x] 5.2 Handle all actions: generate_full_beat, beat_operations (replaces regenerate, add_stem, mute_stem), restore_version, set_section_label, plus refine and compare_versions — _Evidence: beat/page.tsx `dispatchAction` switch; routers/beat.py `_ALLOWED_ACTIONS`; the typed operations are covered by test_properties_ops.py (song-engine 7.1). The page was not seen in a browser by me_
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.1_
  - [x] 5.3 Async job polling for generation actions — _Evidence: beat/page.tsx `runJobWithStatus` uses `pollJob` (lib/api/jobs.ts); the build and edit jobs ran to completion in scripts/ops/e2e.py against the deployed backend (build-progress Nov 18)_
    - _Requirements: 6.3_
  - [x] 5.4 Version ids + labels in conversation context so restore resolves — _Evidence: beat/page.tsx sends `versions` (id, label) in the beat state; llm/prompts.py build_beat_room_messages lists them with their ids for `restore_version`; routers/beat.py `_version_reply` also resolves "the second version" or "before I changed the chorus" in code against the real versions; tests/test_properties_refine.py test_resolver_returns_a_real_version_or_asks. No test sends a restore request through the Beat Room route_
    - _Requirements: 10.2_

- [x] 6. Backend: procedural generation pipeline — _Evidence: children 6.1-6.4 ticked_
  - [x] 6.1 theory + composer: fingerprint → MIDI per section — _Evidence: services/generation/theory.py, composer.py; tests/test_properties_engine.py (123 passed with test_properties_lead.py Nov 18, one Hypothesis-deadline flake)_
    - _Requirements: 2.1, 2.2_
  - [x] 6.2 renderer: MIDI → FluidSynth + SoundFont, per-stem, memory-frugal — _Evidence: services/generation/renderer.py (`SynthSession`, dynamic sample loading, parts start on the synth's block and the echo is drained); a beat render peaks near 435 MB (measured Nov 17, jobs/heavy.py docstring) and one heavy job runs at a time (`HEAVY`)_
    - _Requirements: 2.3_
  - [x] 6.3 Section-only regeneration and stem-only generation — _Evidence: `/beat/generate-section`, `/beat/add-stem`, `/beat/mute-stem` (routers/beat.py) become typed operations; test_an_edit_to_one_part_of_one_section_changes_nothing_else. The whole song is still re-rendered each time (task 9.2)_
    - _Requirements: 5.4, 6.1, 6.2_
  - [x] 6.4 FFmpeg assembly; Storage upload (MP3) for stems and renders — _Evidence: renderer.to_mp3_bytes, beat_runner `_persist_sync` uploads MP3 to the beats bucket; production walkthrough built and played a beat (build-progress)_
    - _Requirements: 2.4, 11.1_

- [x] 7. Backend: Beat conversation route — _Evidence: children 7.1-7.2 ticked_
  - [x] 7.1 Beat Room system prompt with beat-state context — _Evidence: llm/prompts.py BEAT_ROOM_SYSTEM and build_beat_room_messages; routers/beat.py `beat_conversation` adds the song brief (`system_with_brief`)_
    - _Requirements: 9.4, 10.2_
  - [x] 7.2 All action handlers — _Evidence: routers/beat.py `_ALLOWED_ACTIONS` filter; the actions are carried out by the page (5.2) and the job routes_
    - _Requirements: 10.1, 10.3_

- [x] 8. Backend: beat persistence — _Evidence: children 8.1-8.2 ticked_
  - [x] 8.1 beat_versions + beat_stems records; active_beat_version_id update — _Evidence: db/beat.py (create_beat_version, create_stem_sync, PART_SECTION); beat_runner sets `active_beat_version_id` after each build and edit_
    - _Requirements: 2.4, 7.1, 11.2_
  - [x] 8.2 Sidebar status indicator updates — _Evidence: components/studio/StudioNav.tsx `LayerStatusIcon`; the store's `refresh` and `revision` re-read it after changes (voice-to-export-flow 1.1). Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 11.3_

- [ ] 9. Deferred follow-ups (tracked, not demo-critical)
  - [ ] 9.1 Preview with vocal (temporary overlay) — after Voice Room — _PARTLY DONE: `POST /beat/preview-with-vocal` (routers/beat.py) and a "Hear it with my vocal" button (beat/page.tsx, lib/api/beat.ts `previewWithVocal`) exist and the preview is a throwaway. MISSING: no test, and not seen in a browser; the vocal-preview job is not checked to leave versions untouched (voice-to-export-flow 3.2)_
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 9.2 Per-section re-render optimization — _NOT DONE: `beat.rerender_all` renders every section after any edit. Only the preview (`render_excerpt`) is partial (song-engine 7.2)_
    - _Requirements: 5.1_
  - [ ] 9.3 Reorder / duplicate / remove section UI + endpoints — _PARTLY DONE: the operations exist and are tested (ops `move`, `repeat`, `remove_section`; test_a_moved_section_keeps_its_own_notes, test_repeat_and_remove_keep_the_structure_valid) and are reachable by talking to Frank or `POST /beat/operations`. MISSING: no buttons or drag on the timeline_
    - _Requirements: 3.4_
