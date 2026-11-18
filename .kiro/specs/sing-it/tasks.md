# Sing It - Implementation Plan (spec 06)

Depends on spec 03 (Listener measures) and spec 04 (beat plan, lead).

- [x] 1. Song targets
  - [x] 1.1 `song_notes.target_at` from the active beat plan and lead, with tests against known plans
    - _Requirements: 2.1, 6.1_
    - Evidence: `services/audio/song_notes.py` (`from_plan`, `SongNotes.at`, `target_note`);
      `test_song_notes_cover_the_song_and_belong_to_it`, `test_target_is_a_song_note_or_the_tune`.
    - Decision (Nov 18, measured on the founder's real hums): "within two steps of the tune" moved notes up to
      1.8 steps onto the engine tune, rewriting the person's melody. Tuning now only moves a note that does not
      belong to the song, to its closer neighbour; the tune breaks near ties. Real hums: max move 0.94 steps.
- [x] 2. Guide
  - [x] 2.1 Guide render (melody on a voice sound) as a job; cached by beat version
    - _Requirements: 1.1, 1.3_
    - Evidence: `services/audio/guide.py`, `POST /voice/guide`, `guide_renders` (migration 008); prod Nov 18 "guide: ready".
      GM 53 (voice oohs) used rather than 54: it is the clearer singing sound.
  - [x] 2.2 Voice Room: guide on/off and level, practice loop per section, count-in
    - _Requirements: 1.2, 1.3, 1.4, 1.6_
    - Evidence: `components/audio/VocalRecorder.tsx`, `lib/audio/sessionPlayer.ts` (beat + guide in one
      AudioContext, sample-accurate; one bar of the beat, or four clicks at the top). Not yet tried with a real
      microphone in a browser (no device here): the founder's first session is the check.
- [x] 3. Tuning to the song
  - [x] 3.1 `correct_pitch` uses song targets; vibrato kept in gentle modes; per-section report
    - _Requirements: 2.1-2.5_
    - Evidence: `pitch.plan_moves` / `pitch.tune`; properties 1-2, vibrato test; prod "I nudged eight notes in the
      intro"; new `tuned` take row, original kept (hash test).
- [x] 4. Timing
  - [x] 4.1 Delay check (browser clicks + backend onset offset), `user_settings` migration
    - _Requirements: 3.1_
    - Evidence: `align.detect_delay`, `POST /voice/delay-check`, `components/audio/DelayCheck.tsx`; property 3.
  - [x] 4.2 Upload applies the delay; take records `beat_version_id`, offset, headphones
    - _Requirements: 3.2_
    - Evidence: `align.place_in_song`, `POST /voice/takes` form fields; prod walkthrough asserts `song_time`.
  - [x] 4.3 Tighten-the-timing per phrase, bounded to a quarter beat; Listener before/after
    - _Requirements: 3.3, 3.4, 3.5_
    - Evidence: `align.phrase_moves` / `tighten`, `sits_ms` (Listener `timing_offset_ms`); property test; prod run.
- [x] 5. Bleed removal with the accept/keep rule and plain report
  - _Requirements: 4.1-4.4_
  - Evidence: `services/audio/bleed.py` (beat-explained frames find the gaps; pyin hears beat bass as voice);
    property 4; prod 7.8 dB removed, voice unchanged; real hums 18.4 / 10.4 dB removed.
- [x] 6. Phrase comp and per-phrase swap
  - _Requirements: 5.1-5.4_
  - Evidence: `comp.build_phrase_comp` / `swap`, `POST /voice/comp/{id}/swap`, `GET /voice/comp/active`,
    `components/studio/CompView.tsx`; property 5; prod swap.
- [x] 7. Chord-following harmony, per-section, `is_harmony` migration and backfill
  - _Requirements: 6.1-6.3_
  - Evidence: `harmony.plan_harmony` / `chord_harmony`; property 6 (+ no-chord case); migration 008 applied; Mix
    Room and Beat Room read `is_harmony`.
- [x] 8. Recording engineer after-take message
  - _Requirements: 7.1, 7.2_
  - Evidence: `services/audio/engineer.py`; prod: the leaky take got "The beat is getting into your mic…".
- [x] 9. Use a take as the melody (shares the hum confirm path)
  - _Requirements: 8.1_
  - Evidence: `POST /voice/takes/{id}/use-as-melody` -> hum intake job; Voice Room confirm card.
- [x] 10. Voice Room typed actions and take facts in the brief
  - _Requirements: 9.1_
  - Evidence: `VOICE_ROOM_SYSTEM` actions, `build_voice_room_messages(takes=...)`, `record._vocal_summary` facts.
- [x] 11. Property tests (`tests/test_properties_sing.py`), each proved able to fail
  - Evidence: 16 tests; `scripts/mutate_check.py` sing mutations 6 of 6 caught (11 of 11 overall).
- [x] 12. Real audio check: a real sung take through tune, align, bleed and comp; listening files prepared
  with the Listening Lab agent (before/after)
  - Evidence: `listening/sing-it-2026-11-18/` (git-ignored): blind tuning pairs with controls, harmony, bleed and
    timing before/after, README for the founder, separate ANSWER_KEY. Waiting on the founder's ears.
