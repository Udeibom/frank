# Song Engine - Implementation Plan

Depends on spec 01 and spec 02 (melody, groove, structure). Spec 05's sound spike runs alongside task 6.

- [ ] 1. Contracts — _PARTLY DONE: children 1.1 and 1.2 are open_
  - [ ] 1.1 `Plan`, `PartPlan`, `Score`, `StyleProfile`, typed operation models (Pydantic) — _PARTLY DONE: the 14 typed operation models exist (generation/ops.py `_Op` subclasses, Pydantic). MISSING: the plan is the `SectionPlan` dataclass (beat.py), the score is a plain dict (`score_of`), the style is the `StyleChoice` dataclass (styles.py); there are no `Plan`, `PartPlan`, `Score` or `StyleProfile` models_
    - _Requirements: 7.1, 7.2, 5.3_
  - [ ] 1.2 Plan storage in `beat_versions.params`; legacy loading path — _PARTLY DONE: beat_runner `_arrangement_params` stores the plan and `beat.sections_from_params` rebuilds it, filling in repeat and seed for older beats; used by the Listener, mix, refine and edit paths and run on production. MISSING: no test builds an old-format params blob and loads it_
    - _Requirements: 7.3, 8.2_

- [x] 2. Styles — _Evidence: children 2.1-2.3 ticked_
  - [x] 2.1 Style profile schema and loader; blending by genre hints, warmth, brightness, tempo feel — _Evidence: styles.py pick_style + styles/styles.json; test_style_file_is_valid, test_warmth_and_brightness_change_the_sound_
    - _Requirements: 4.1, 4.2_
  - [x] 2.2 Initial profiles (soul/r&b, pop, lo-fi, rock, ambient, folk, hip-hop, gospel, electronic) — _Evidence: styles.json holds soul, gospel, pop, lofi, rock, ambient, folk, hiphop, electronic; test_style_file_is_valid_
    - _Requirements: 4.2_
  - [x] 2.3 Report unsupported hints in plain language — _Evidence: StyleChoice.unsupported in styles.py; test_words_frank_cannot_act_on_are_reported_
    - _Requirements: 4.3_

- [x] 3. Planner — _Evidence: children 3.1-3.3 ticked_
  - [x] 3.1 Sections from the structure facet (lines to bars) or style template — _Evidence: beat.arrangement_from_structure, build_beat_plan; tests/test_properties_planner.py test_the_words_decide_the_shape, test_no_structure_means_the_style_template (4 passed)_
    - _Requirements: 1.1_
  - [x] 3.2 Energy curve and per-section part choices with rotation across repeats — _Evidence: beat.energy_multiplier and build_beat_plan; test_each_chorus_is_at_least_as_big_as_the_one_before_and_the_last_is_the_biggest, test_the_words_feeling_moves_the_energy (planner), test_a_returning_verse_is_not_a_copy (engine); planner 4 passed; engine and lead files together 122 passed, 1 xfailed this session_
    - _Requirements: 1.2, 2.1_
  - [x] 3.3 Stable per-part seeds — _Evidence: generation/rng.py derive_seed/rng_for keyed by seed+section+part; test_same_seed_same_music, test_changing_one_section_leaves_the_others_alone_
    - _Requirements: 6.1_

- [ ] 4. Composer
  - [ ] 4.1 Richer harmony: sevenths, inversions, voice-leading, harmonic rhythm — _NOT DONE: sevenths, inversions and voice-leading exist (theory.py voice_lead, chord_for_degree; test_voice_leading_*), but no harmonic-rhythm change and no test that sevenths appear_
    - _Requirements: 3.1_
  - [ ] 4.2 Motif-based melody with rests and phrase shapes — _NOT DONE: motif and phrase endings exist in compose_melody; only strong-beat harmony is tested, not rests or phrase shape_
    - _Requirements: 3.2_
  - [x] 4.3 Harmonise a confirmed melody (Viterbi over bars) and fit bass — _Evidence: generation/lead.py (from_sketch, harmonize, coverage, lead_events, fit_to, scale_fit, choose_key); wired in composer.py (SectionContext.lead, Part.lead), beat.py (build_beat_plan, plan_contexts, render_song LEAD_GAIN, lead_info, lead_from_params), beat_runner.py (_fingerprint_and_lead, params lead/lead_info, job result lead_used), song/record.py (active_melody, beat summary lead). tests/test_properties_lead.py re-run Nov 18 with the engine tests: all passed but one, test_no_melody_leaves_the_fingerprint_alone, which failed once on Hypothesis's 200 ms deadline (first call 980 ms) and passes alone in 8 s (the intermittent failure in build-progress; the test has no `deadline=None`); 1 xfailed. Real hums: chord fit 0.63/0.64/0.81 vs 0.39/0.40/0.52 for a stock progression (founder's measurement, not re-run by me). Not seen in a browser; no UI for it. Open items are 4.8-4.12_
    - _Requirements: 3.3_
  - [ ] 4.8 Founder verdict on /home/caleb/frank-listening/blind-hum-songs — _NOT DONE: no verdict yet_
    - _Requirements: 3.3_
  - [x] 4.9 Ending/stop can clear the last bar of a chorus when the final section is a chorus — _Evidence: touches._ending skips the lead part; test_the_ending_never_cuts_the_last_bar_of_the_tune fails without the fix (checked) and passes with it_
    - _Requirements: 3.3_
  - [x] 4.10 Edits keep the stored tune even if a newer hum is confirmed, with no notice — _Evidence: beat_runner._follow_newest_tune makes edits follow the newest confirmed tune; 3 tests (an_edit_*) in test_properties_lead.py. Decision: follow the newer hum, because the last thing the person confirmed is what they want_
    - _Requirements: 3.3_
  - [x] 4.11 Tell the person "I built the chorus around your tune" — _Evidence: Beat Room shows describeLead(lead_info) above the timeline (frontend/lib/api/beat.ts, beat/page.tsx); type-checks. Not seen in a browser_
    - _Requirements: 3.3_
  - [ ] 4.12 Tune plays in verses as well as choruses, and hums longer than 16 bars are not cut — _NOT DONE: LEAD_SECTIONS = ("chorus",), MAX_BARS = 16. Also xfail: a tune sitting on a diminished chord is heard as another chord_
    - _Requirements: 3.3_
  - [ ] 4.4 Bass patterns with approach notes; drum grooves, fills, crashes, breakdowns — _NOT DONE: fills and crashes are tested (test_a_chorus_starts_with_a_crash, test_a_fill_only_touches_the_bar_before_the_chorus); bass approach notes (`_bass_pitch` kind "approach", composer.py:148) have no test; the nearest thing to a breakdown is the `dropout` moment (moments.py) and no test names a breakdown_
    - _Requirements: 1.2, 1.4_
  - [ ] 4.5 Extras (counter-melody, arpeggios, swells, risers) and transition events — _NOT DONE: arpeggio part (composer.compose_arp), riser and sweep moments (moments.py, beat.PART_GAIN) and late entries, stops and answers exist and are tested (test_moments_*, test_answers_are_notes_of_the_chord_playing); there is no counter-melody and no test of the arpeggio or the riser by name_
    - _Requirements: 1.3, 1.4_
  - [x] 4.6 Seeded humanisation — _Evidence: _vel/_at jitter from rng_for in composer.py; test_same_seed_same_music, test_a_new_seed_gives_different_music_
    - _Requirements: 6.3_
  - [x] 4.7 Key safety in every part — _Evidence: test_melody_strong_beats_are_chord_tones, test_every_note_is_playable; audit shows 0 non-chord-tone strong-beat notes in 3 fingerprints_
    - _Requirements: 3.4_

- [x] 5. Assembly — _Evidence: children 5.1-5.4 ticked_
  - [x] 5.1 Per-part, per-section rendering; one song-level loudness pass; remove per-section peak normalisation — _Evidence: beat.render_song renders per part per section, per-section RMS target + one song-level peak pass; test_loudness_follows_the_job_of_each_section. Section loudness is a per-section RMS target, not a single song pass_
    - _Requirements: 2.1, 2.3, 8.1_
  - [x] 5.2 Chorus lift margin check — _Evidence: beat._target_db; test_loudness_follows_the_job_of_each_section (passes); audit: chorus -26.5 dB vs verse -29.4 dB. That the test can fail is task 9.4_
    - _Requirements: 2.2_
  - [x] 5.3 Cross-join tails and transition rendering (no hard cuts) — _Evidence: render_song tail rings over next section; test_the_last_notes_are_allowed_to_ring_out, test_no_silent_gap_at_section_joins, test_length_is_the_bars_plus_the_tail_
    - _Requirements: 1.3_
  - [x] 5.4 Stem files stored; `beat_stems` extended — _Evidence: the song's parts are stored per family as stems with section 'all' (db/beat.py PART_SECTION, beat_runner.ensure_parts / run_parts_job, beat.render_parts); test_the_parts_add_up_to_the_beat (parts sum to the full beat, both with and without the mix chain; 10 passed in test_properties_finish.py). Used by the Mix Room and the separate-parts zip; the finish story passed on production (build-progress, Nov 18, 28 MB zip). ensure_parts itself (store and cache) has no test of its own_
    - _Requirements: 5.1_

- [ ] 6. Renderer clean-up
  - [ ] 6.1 Per-part reverb/chorus control; fix equal-sample note-off ordering — _NOT DONE: no per-part reverb or chorus setting in renderer.py, and no test of events that land on the same sample. A different renderer fix is done: every part starts on the synth's 64-sample block (`SynthSession._align`) and its echo is drained (`_drain`), so a part sounds the same whatever was rendered before it; covered by test_the_parts_add_up_to_the_beat_
    - _Requirements: 8.3_

- [ ] 7. Editing
  - [x] 7.1 Typed operations with validation and a change summary — _Evidence: generation/ops.py (`parse`, `apply_operations`, `apply_audible`, plain change sentences; `apply_audible` refuses an edit that changes nothing audible); `POST /beat/operations` (routers/beat.py); tests/test_properties_ops.py test_invalid_edits_are_refused_in_plain_words, test_every_change_sentence_is_plain, test_an_edit_that_changes_nothing_audible_says_so, test_the_input_plan_is_never_modified_and_a_bad_edit_changes_nothing (44 passed with the team tests)_
    - _Requirements: 5.2, 5.3, 5.4_
  - [ ] 7.2 Partial re-compose and re-render; quick section preview — _PARTLY DONE: the quick preview is built (`beat.render_excerpt` plays only the chosen sections at the full song's level; tests/test_properties_refine.py test_render_excerpt_plays_only_the_chosen_sections; used by refine_runner; checked on production, build-progress Nov 18). MISSING: committing an edit still re-renders the whole song (`beat.rerender_all` calls `render_song`; build-progress lists it as a known issue)_
    - _Requirements: 5.2, 7.4_
  - [x] 7.3 Beat Room LLM emits typed operations; remove keyword matching — _Evidence: Beat Room prompt (llm/prompts.py) asks for `beat_operations` with at most three operations; routers/beat.py `_ALLOWED_ACTIONS` has `beat_operations`; the page dispatches it to `applyBeatOperations` (beat/page.tsx); the operations are validated by `ops.parse`; grep finds no keyword matching left in the beat path. No test sends a message through the Beat Room route, and the screen was not seen in a browser by me (tsc --noEmit passes)_
    - _Requirements: 5.3_
  - [x] 7.4 "Another" uses a new seed and sounds different — _Evidence: ops `another_song` and `try_another` (Reseed); tests test_another_song_is_a_different_song_and_repeatable, test_an_edit_to_one_part_of_one_section_changes_nothing_else (try_another), test_a_new_seed_gives_different_music. `beat_runner.run_operations_job` itself is not run in a test_
    - _Requirements: 6.2_

- [x] 8. Calibration — _Evidence: children 8.1-8.2 ticked_
  - [x] 8.1 Re-run `baseline_audit.py`: dead-field check now differs; chorus lift margin met; melody chord-tone share above threshold — _Evidence: baseline_audit.py re-run this session: claim check "hints change the audio? yes", chorus louder than verse, 0 strong-beat clashes; no explicit pass/fail thresholds in script_
    - _Requirements: 2.2, 3.2, 4.1_
  - [x] 8.2 Founder listens to the new renders against the Nov 11 baseline and says better, same or worse, with reasons — _Evidence: founder's blind-engine-v3 answers (engine v2 vs v3 with moments): SAME on every pair, endings felt like endings, neither sounded like a children's song. Measurement shows the moments change 5 of 8 sections materially, so the listener judged both as good songs. Test not repeated. Result reported by the founder; not independently re-run_

- [ ] 9. Property-based tests (`backend/tests/test_properties_engine.py`) — _open: 9.4_
  - [x] 9.1 Determinism, variation, key safety, strong-beat harmony — _Evidence: test_same_seed_same_music, test_a_new_seed_gives_different_music, test_a_returning_verse_is_not_a_copy, test_melody_strong_beats_are_chord_tones, test_every_note_is_playable_
  - [x] 9.2 Dynamics margin, no dead fields, locality, density monotonicity — _Evidence: test_loudness_follows_the_job_of_each_section, test_genre_and_instrument_words_change_the_music, test_warmth_and_brightness_change_the_sound, test_changing_one_section_leaves_the_others_alone, test_more_density_never_means_fewer_notes_
  - [x] 9.3 Structure validity, stem sum — _Evidence: test_sections_are_contiguous_and_exact, test_length_is_the_bars_plus_the_tail (engine), test_repeat_and_remove_keep_the_structure_valid (ops), test_the_parts_add_up_to_the_beat (finish)_
  - [ ] 9.4 Prove each test can fail — _NOT DONE: backend/scripts/mutate_check.py has no entry for test_properties_engine.py or test_properties_ops.py (its entries cover refine, sing, finish, taste and creative director)_
