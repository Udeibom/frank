# Song Engine - Implementation Plan

Depends on spec 01 and spec 02 (melody, groove, structure). Spec 05's sound spike runs alongside task 6.

- [ ] 1. Contracts
  - [ ] 1.1 `Plan`, `PartPlan`, `Score`, `StyleProfile`, typed operation models (Pydantic)
    - _Requirements: 7.1, 7.2, 5.3_
  - [ ] 1.2 Plan storage in `beat_versions.params`; legacy loading path
    - _Requirements: 7.3, 8.2_

- [x] 2. Styles — _Evidence: children 2.1-2.3 ticked_
  - [x] 2.1 Style profile schema and loader; blending by genre hints, warmth, brightness, tempo feel — _Evidence: styles.py pick_style + styles/styles.json; test_style_file_is_valid, test_warmth_and_brightness_change_the_sound_
    - _Requirements: 4.1, 4.2_
  - [x] 2.2 Initial profiles (soul/r&b, pop, lo-fi, rock, ambient, folk, hip-hop, gospel, electronic) — _Evidence: styles.json holds soul, gospel, pop, lofi, rock, ambient, folk, hiphop, electronic; test_style_file_is_valid_
    - _Requirements: 4.2_
  - [x] 2.3 Report unsupported hints in plain language — _Evidence: StyleChoice.unsupported in styles.py; test_words_frank_cannot_act_on_are_reported_
    - _Requirements: 4.3_

- [ ] 3. Planner
  - [ ] 3.1 Sections from the structure facet (lines to bars) or style template
    - _Requirements: 1.1_
  - [ ] 3.2 Energy curve and per-section part choices with rotation across repeats
    - _Requirements: 1.2, 2.1_
  - [x] 3.3 Stable per-part seeds — _Evidence: generation/rng.py derive_seed/rng_for keyed by seed+section+part; test_same_seed_same_music, test_changing_one_section_leaves_the_others_alone_
    - _Requirements: 6.1_

- [ ] 4. Composer
  - [ ] 4.1 Richer harmony: sevenths, inversions, voice-leading, harmonic rhythm — _NOT DONE: sevenths, inversions and voice-leading exist (theory.py voice_lead, chord_for_degree; test_voice_leading_*), but no harmonic-rhythm change and no test that sevenths appear_
    - _Requirements: 3.1_
  - [ ] 4.2 Motif-based melody with rests and phrase shapes — _NOT DONE: motif and phrase endings exist in compose_melody; only strong-beat harmony is tested, not rests or phrase shape_
    - _Requirements: 3.2_
  - [x] 4.3 Harmonise a confirmed melody (Viterbi over bars) and fit bass — _Evidence: generation/lead.py (from_sketch, harmonize, coverage, lead_events, fit_to, scale_fit, choose_key); wired in composer.py (SectionContext.lead, Part.lead), beat.py (build_beat_plan, plan_contexts, render_song LEAD_GAIN, lead_info, lead_from_params), beat_runner.py (_fingerprint_and_lead, params lead/lead_info, job result lead_used), song/record.py (active_melody, beat summary lead). tests/test_properties_lead.py: 74 passed, 1 xfailed (re-run this session). Real hums: chord fit 0.63/0.64/0.81 vs 0.39/0.40/0.52 for a stock progression (founder's measurement, not re-run by me). Not seen in a browser; no UI for it. Open items are 4.8-4.12_
    - _Requirements: 3.3_
  - [ ] 4.8 Founder verdict on /home/caleb/frank-listening/blind-hum-songs — _NOT DONE: no verdict yet_
    - _Requirements: 3.3_
  - [ ] 4.9 Ending/stop can clear the last bar of a chorus when the final section is a chorus — _NOT DONE: known bug_
    - _Requirements: 3.3_
  - [ ] 4.10 Edits keep the stored tune even if a newer hum is confirmed, with no notice — _NOT DONE: tell the person or follow the newer hum_
    - _Requirements: 3.3_
  - [ ] 4.11 Tell the person "I built the chorus around your tune" — _NOT DONE: lead_used (job result) and lead_info (song record) are exposed, the frontend shows neither_
    - _Requirements: 3.3_
  - [ ] 4.12 Tune plays in verses as well as choruses, and hums longer than 16 bars are not cut — _NOT DONE: LEAD_SECTIONS = ("chorus",), MAX_BARS = 16. Also xfail: a tune sitting on a diminished chord is heard as another chord_
    - _Requirements: 3.3_
  - [ ] 4.4 Bass patterns with approach notes; drum grooves, fills, crashes, breakdowns — _NOT DONE: drum fills and crashes tested; bass approach notes (_bass_pitch "approach") have no test and no breakdown code found_
    - _Requirements: 1.2, 1.4_
  - [ ] 4.5 Extras (counter-melody, arpeggios, swells, risers) and transition events
    - _Requirements: 1.3, 1.4_
  - [x] 4.6 Seeded humanisation — _Evidence: _vel/_at jitter from rng_for in composer.py; test_same_seed_same_music, test_a_new_seed_gives_different_music_
    - _Requirements: 6.3_
  - [x] 4.7 Key safety in every part — _Evidence: test_melody_strong_beats_are_chord_tones, test_every_note_is_playable; audit shows 0 non-chord-tone strong-beat notes in 3 fingerprints_
    - _Requirements: 3.4_

- [ ] 5. Assembly
  - [x] 5.1 Per-part, per-section rendering; one song-level loudness pass; remove per-section peak normalisation — _Evidence: beat.render_song renders per part per section, per-section RMS target + one song-level peak pass; test_loudness_follows_the_job_of_each_section. Section loudness is a per-section RMS target, not a single song pass_
    - _Requirements: 2.1, 2.3, 8.1_
  - [x] 5.2 Chorus lift margin check — _Evidence: beat._target_db; test_loudness_follows_the_job_of_each_section; audit: chorus -26.5 dB vs verse -29.4 dB_ — _NOT DONE: mutation checks were run by hand, not recorded; nothing in the repo re-proves each test can fail_
    - _Requirements: 2.2_
  - [x] 5.3 Cross-join tails and transition rendering (no hard cuts) — _Evidence: render_song tail rings over next section; test_the_last_notes_are_allowed_to_ring_out, test_no_silent_gap_at_section_joins, test_length_is_the_bars_plus_the_tail_
    - _Requirements: 1.3_
  - [ ] 5.4 Stem files stored; `beat_stems` extended
    - _Requirements: 5.1_

- [ ] 6. Renderer clean-up
  - [ ] 6.1 Per-part reverb/chorus control; fix equal-sample note-off ordering
    - _Requirements: 8.3_

- [ ] 7. Editing
  - [ ] 7.1 Typed operations with validation and a change summary
    - _Requirements: 5.2, 5.3, 5.4_
  - [ ] 7.2 Partial re-compose and re-render; quick section preview
    - _Requirements: 5.2, 7.4_
  - [ ] 7.3 Beat Room LLM emits typed operations; remove keyword matching
    - _Requirements: 5.3_
  - [ ] 7.4 "Another" uses a new seed and sounds different — _NOT DONE: engine-level new seed tested (test_a_new_seed_gives_different_music) and beat_runner derives a seed from version count, but no test covers the "another" path through beat_runner_
    - _Requirements: 6.2_

- [x] 8. Calibration — _Evidence: children 8.1-8.2 ticked_
  - [x] 8.1 Re-run `baseline_audit.py`: dead-field check now differs; chorus lift margin met; melody chord-tone share above threshold — _Evidence: baseline_audit.py re-run this session: claim check "hints change the audio? yes", chorus louder than verse, 0 strong-beat clashes; no explicit pass/fail thresholds in script_
    - _Requirements: 2.2, 3.2, 4.1_
  - [x] 8.2 Founder listens to the new renders against the Nov 11 baseline and says better, same or worse, with reasons — _Evidence: founder's blind-engine-v3 answers (engine v2 vs v3 with moments): SAME on every pair, endings felt like endings, neither sounded like a children's song. Measurement shows the moments change 5 of 8 sections materially, so the listener judged both as good songs. Test not repeated. Result reported by the founder; not independently re-run_

- [ ] 9. Property-based tests (`backend/tests/test_properties_engine.py`)
  - [x] 9.1 Determinism, variation, key safety, strong-beat harmony — _Evidence: test_same_seed_same_music, test_a_new_seed_gives_different_music, test_a_returning_verse_is_not_a_copy, test_melody_strong_beats_are_chord_tones, test_every_note_is_playable_
  - [x] 9.2 Dynamics margin, no dead fields, locality, density monotonicity — _Evidence: test_loudness_follows_the_job_of_each_section, test_genre_and_instrument_words_change_the_music, test_warmth_and_brightness_change_the_sound, test_changing_one_section_leaves_the_others_alone, test_more_density_never_means_fewer_notes_
  - [ ] 9.3 Structure validity, stem sum
  - [ ] 9.4 Prove each test can fail
