# Sing It - Implementation Plan (spec 06)

Depends on spec 03 (Listener measures) and spec 04 (beat plan, lead).

- [ ] 1. Song targets
  - [ ] 1.1 `song_notes.target_at` from the active beat plan and lead, with tests against known plans
    - _Requirements: 2.1, 6.1_
- [ ] 2. Guide
  - [ ] 2.1 Guide render per section (melody on a voice sound, under the beat) as a job; cached by beat version
    - _Requirements: 1.1, 1.3_
  - [ ] 2.2 Voice Room: guide on/off and level, practice loop per section, count-in
    - _Requirements: 1.2, 1.3, 1.4, 1.6_
- [ ] 3. Tuning to the song
  - [ ] 3.1 `correct_pitch` uses song targets; vibrato kept in gentle modes; per-section report
    - _Requirements: 2.1-2.5_
- [ ] 4. Timing
  - [ ] 4.1 Delay check (browser clicks + backend onset offset), `user_settings` migration
    - _Requirements: 3.1_
  - [ ] 4.2 Upload applies the delay; take records `beat_version_id`, offset, headphones
    - _Requirements: 3.2_
  - [ ] 4.3 Tighten-the-timing per phrase, bounded to a quarter beat; Listener before/after
    - _Requirements: 3.3, 3.4, 3.5_
- [ ] 5. Bleed removal with the accept/keep rule and plain report
  - _Requirements: 4.1-4.4_
- [ ] 6. Phrase comp and per-phrase swap
  - _Requirements: 5.1-5.4_
- [ ] 7. Chord-following harmony, per-section, `is_harmony` migration and backfill
  - _Requirements: 6.1-6.3_
- [ ] 8. Recording engineer after-take message
  - _Requirements: 7.1, 7.2_
- [ ] 9. Use a take as the melody (shares the hum confirm path)
  - _Requirements: 8.1_
- [ ] 10. Voice Room typed actions and take facts in the brief
  - _Requirements: 9.1_
- [ ] 11. Property tests (`tests/test_properties_sing.py`), each proved able to fail
- [ ] 12. Real audio check: a real sung take through tune, align, bleed and comp; listening files prepared
  with the Listening Lab agent (before/after)
