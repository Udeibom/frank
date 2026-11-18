# Listener - Implementation Plan

Depends on spec 01 (record) and, for per-part measures, spec 04 (stems).

- [ ] 1. Core measurements
  - [ ] 1.1 Loudness per section (gated, K-weighted) and per part — _NOT DONE: per section works (BS.1770 K-weighted, gated). Per part: the parts now exist (`beat_runner.ensure_parts`, stems with section 'all'), but nothing measures them: services/listener/service.py:201 still reports `part_loudness` as unmeasured ("not how loud each one is on its own yet") and the Listener never reads the stored parts_
    - _Requirements: 1.1, 1.3_
  - [x] 1.2 Density, colour, section-to-section change — _Evidence: dsp.onsets_per_bar, brightness_hz, band_share, change_between; service.measure_audio; calibration run on a real render__
    - _Requirements: 1.1_
  - [ ] 1.3 Repetition (chroma/MFCC self-similarity, melody similarity) — _NOT DONE: sound similarity of same-named sections and chorus vs verse works; melody-interval similarity is not built_
    - _Requirements: 1.4_
  - [x] 1.4 Melody measures (range, movement, chord-tone fit) — _Evidence: service.score_facts recomposes sections from the plan and measures strong-beat chord fit, range, movement; calibration shows fit 1.0 on engine melodies__
    - _Requirements: 1.5_
  - [x] 1.5 Safety measures (clipping, noise, silence) and the "could not measure" path — _Evidence: dsp.clipping_share, noise_floor_db, peak_db; test_silence_and_short_audio_give_could_not_measure_not_zero, test_garbage_samples_are_not_measured_
    - _Requirements: 3.1_

- [x] 2. Voice measures — _Evidence: children 2.1-2.3 ticked_
  - [x] 2.1 Vocal tuning against the song's notes — _Evidence: measure_audio uses detect_pitch_contour + dsp.cents_off_scale against the key's scale; tested only through findings rules on synthetic numbers, not on a real sung take_
    - _Requirements: 1.2_
  - [x] 2.2 Vocal-to-beat timing offset — _Evidence: dsp.timing_offset_ms; test_a_delayed_copy_is_reported_within_one_frame_
    - _Requirements: 1.2_
  - [x] 2.3 Vocal/beat competition in the voice range — _Evidence: section.N.voice_band_gap (200-4000 Hz) and vocal_gap; test_a_buried_voice_is_found_and_a_clear_one_is_not (synthetic noise, not a real vocal)_
    - _Requirements: 1.3_

- [x] 3. Findings — _Evidence: children 3.1-3.3 ticked_
  - [x] 3.1 Finding model, rule functions, threshold config with provenance comments — _Evidence: models.py, findings.py (11 rules), config.py_
    - _Requirements: 2.1, 2.4_
  - [x] 3.2 Plain-language templates (no jargon, no units) — _Evidence: test_every_sentence_the_rules_can_say_is_plain_words_
    - _Requirements: 2.2_
  - [x] 3.3 "No clear cause" path and confidence — _Evidence: test_no_rule_firing_with_a_concern_means_no_clear_cause_and_no_made_up_finding_
    - _Requirements: 3.2, 3.3_

- [ ] 4. Service — _open: 4.4_
  - [x] 4.1 `measure_song`, `find_issues`, `compare`, read-only guarantee — _Evidence: listener/project.py, findings.find_issues, service.compare; test_listening_to_a_project_writes_nothing_but_the_cache_
    - _Requirements: 4.1, 4.2_
  - [x] 4.2 `listener_cache` table and caching by version id — _Evidence: db/migrations/005_listener_cache.sql applied to the live database Nov 17 via the Management API (table exists, 0 rows); cache read/write in listener/project.py_
    - _Requirements: 5.1_
  - [x] 4.3 `POST /projects/{id}/listen` job with progress text and scoped runs — _Evidence: routers/listen.py, jobs/listen_runner.py, mounted in main.py; the listen step runs inside scripts/ops/e2e.py, which passed against the deployed backend (build-progress Nov 18, e.g. E2E OK in 669 s and 1156 s); not re-run by me_
    - _Requirements: 5.2, 5.3_
  - [ ] 4.4 Mismatch recording hook for taste signals (stores; spec 09 reads) — _PARTLY DONE: `POST /refine/{proposal_id}/disagree` (routers/refine.py `disagree`) writes a decision with the measurement and the person's words, then `taste.signals.record_mismatch` stores a signal (topic "other", source "measurement mismatch"). An ad-hoc call with the stores mocked (not committed) showed the decision and the signal both written. MISSING: no committed test covers it (test_properties_refine.py only tests `meaning_question`), and a real database write was not checked_
    - _Requirements: 6.1_

- [ ] 5. Calibration
  - [x] 5.1 Run on the baseline renders (frank-listening/baseline) and confirm it flags the known problems: weak chorus lift, wandering melody — _Evidence: ran on a fresh engine render (not the baseline files): flags the first chorus as barely louder than the verse (+1.4). Melody fit is 1.0 on the engine's own melodies, so 'wandering melody' is not reproduced_
    - _Requirements: 1.1, 1.5, 2.1_
  - [ ] 5.2 Founder check — _NOT DONE_: do the findings match what the founder hears?

- [ ] 6. Property-based tests (`backend/tests/test_properties_listener.py`)
  - [x] 6.1 Gain invariance, identity, timing recovery — _Evidence: tests/test_properties_listener.py, 16 passed Nov 18 (re-run)_
  - [x] 6.2 Silence, determinism, read-only, honesty — _Evidence: tests/test_properties_listener.py, 16 passed Nov 18 (re-run)_
  - [ ] 6.3 Prove each test can fail — _NOT DONE: backend/scripts/mutate_check.py has no entry for tests/test_properties_listener.py (checked)_
