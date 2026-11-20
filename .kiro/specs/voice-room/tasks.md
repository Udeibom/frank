# Voice Room — Implementation Plan

- [x] 1. Microphone setup — _Evidence: children 1.1-1.3 ticked_
  - [x] 1.1 Permission request flow with warm explanation — _Evidence: hooks/useRecorder.ts (`getUserMedia`, error "Frank needs permission to use your microphone."); components/audio/VocalRecorder.tsx. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me; a real microphone prompt was not checked (build-progress: browser timing not checkable here)_
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 Best-effort headphone detection (non-blocking tip) — _Evidence: VocalRecorder.tsx passes a `headphones` value and says they are suggested, never required; the value is sent with the upload (voice/page.tsx `handleRecorded`). Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 1.3, 1.4_
  - [x] 1.3 `hooks/useRecorder.ts` reusable recording hook — _Evidence: frontend/hooks/useRecorder.ts exists and is used by VocalRecorder.tsx_
    - _Requirements: 2.1_

- [ ] 2. Recording UI — _open: 2.3_
  - [x] 2.1 `components/audio/VocalRecorder.tsx` — record button, timer, level meter, stop — _Evidence: VocalRecorder.tsx with `inputLevel` from useRecorder.ts; Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 2.1, 2.2_
  - [x] 2.2 Beat playback sync; "Record with beat" / "Record without beat" — _Evidence: VocalRecorder.tsx `withBeat`; sing-it spec adds a count-in and a one-time delay check (components/audio/DelayCheck.tsx, `POST /voice/delay-check`; tests test_delay_check_finds_the_delay, test_placing_a_take_puts_each_sound_at_its_song_time). Browser timing with a real microphone not checked (build-progress)_
    - _Requirements: 1.5, 2.2_
  - [ ] 2.3 Take card: waveform, duration, label, play — _PARTLY DONE: components/studio/TakeCard.tsx has the label and a play button per version; it shows no waveform and no duration (the Waveform component is used only in the Export Room)_
    - _Requirements: 2.3_

- [ ] 3. Take management — _open: 3.2_
  - [x] 3.1 Take list with select-to-compare and per-take play — _Evidence: TakeCard.tsx (`picked`, `onPick`, per-version play); voice/page.tsx lists takes with their versions. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 3.1_
  - [ ] 3.2 Label editing; set active take — _PARTLY DONE: set active take works (`POST /voice/active`, `onUse`, voice/page.tsx `updateActiveState`; requirement 2.4 covered by test_resolution_* in test_properties_audio.py). MISSING: there is no way to rename a take: no input in TakeCard.tsx and no rename route in routers/voice.py_
    - _Requirements: 2.5, 3.2_

- [x] 4. Pitch visualization — _Evidence: children 4.1-4.2 ticked_
  - [x] 4.1 `components/audio/PitchDisplay.tsx` — color-coded tuning with non-color cue — _Evidence: PitchDisplay.tsx (bar shape, text legend "Steady / A little wobbly / Worth another try", aria-label summary), used in TakeCard.tsx. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 4.2, 4.3_
  - [x] 4.2 Fetch pitch data after upload — _Evidence: routers/voice.py upload starts the analysis; the take comes back with `pitch_data` (lib/api/voice.ts) and TakeCard shows it; the production walkthrough uploaded and analysed a take (build-progress Nov 18)_
    - _Requirements: 4.1_

- [x] 5. Pitch correction — _Evidence: children 5.1-5.4 ticked_
  - [x] 5.1 Three-mode selector (conversation + buttons) — _Evidence: TakeCard.tsx three buttons ("Tune the obvious bits", "Tighten it up", "Lock it in"); voice/page.tsx `act` with `correctPitch(projectId, take.id, mode)` and the conversation action; `POST /voice/takes/{id}/correct`. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 5.1_
  - [x] 5.2 Async correction job; new "(tuned)" take card; original preserved — _Evidence: routers/voice.py `correct` starts a job; the result is a new take (kind "tuned", parent_take_id); tests test_tuning_really_moves_the_sound_and_keeps_the_original, test_tuning_leaves_close_notes_alone_and_moves_others_closer (mutation-checked in scripts/mutate_check.py); the walkthrough's tune step passed on production_
    - _Requirements: 5.3, 5.4_
  - [x] 5.3 "Lock it in" real per-note snapping with crossfades — _Evidence: services/audio/pitch.py; test_tuning_leaves_close_notes_alone_and_moves_others_closer, test_gentle_tuning_keeps_vibrato, test_properties_pitch.py (3 passed). Not heard by me_
    - _Requirements: 5.2_
  - [x] 5.4 Original vs corrected comparison — _Evidence: TakeCard.tsx shows every version of a take with its own play button, the original first. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 5.5_

- [x] 6. Vocal comp — _Evidence: children 6.1-6.2 ticked_
  - [x] 6.1 Trigger from conversation; score + assemble best segments — _Evidence: services/audio/comp.py (phrase by phrase); `POST /voice/comp`; tests/test_properties_comp.py (9 passed Nov 18) and test_phrase_comp_tiles_the_timeline_and_picks_the_singer_
    - _Requirements: 6.1, 6.2_
  - [x] 6.2 Comp view with segment provenance; accept/adjust/redo — _Evidence: components/studio/CompView.tsx (which take each line comes from, swap a line via `POST /voice/comp/{id}/swap`), use-as-active. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 6.3, 6.4, 6.5_

- [x] 7. Harmony — _Evidence: children 7.1-7.2 ticked_
  - [x] 7.1 Trigger from conversation; higher/lower/both options — _Evidence: TakeCard.tsx harmony controls (above, below, above and below; where in the song); voice/page.tsx harmony action; `POST /voice/harmony`. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 7.1, 7.3_
  - [x] 7.2 Mode-aware interval from fingerprint; stored as a Mix Room layer — _Evidence: services/audio/harmony.py now follows the chords per section (test_every_harmony_note_is_a_chord_note, test_without_chords_the_harmony_is_a_third_in_the_scale, test_harmony_only_in_the_chosen_sections, both mutation-checked); the take is flagged `is_harmony` (migration 008) and the Mix Room treats it as its own layer (mix_runner.py)_
    - _Requirements: 7.2, 7.4_

- [x] 8. Backend: all Voice Room routes — _Evidence: children 8.1-8.4 ticked_
  - [x] 8.1 Upload + async pitch analysis (librosa pyin) — _Evidence: routers/voice.py `POST /voice/takes` and the analysis job (jobs/voice_runner.py), run on production in the walkthrough_
    - _Requirements: 8.1, 4.1_
  - [x] 8.2 Correction job (pylibrb), comp job, harmony job — _Evidence: routers/voice.py `correct`, `comp`, `harmony`; jobs/voice_runner.py; tests above; walkthrough on production: tune, line up, music taken out, harmony, best-of, swap (build-progress Nov 18)_
    - _Requirements: 8.4, 8.5, 5.4_
  - [x] 8.3 Conversation route with patient vocal-producer prompt — _Evidence: routers/voice.py `voice_conversation`; tests/test_team_rooms.py test_each_room_stores_the_exchange_and_uses_the_earlier_summary[voice] (model faked)_
    - _Requirements: 8.7_
  - [x] 8.4 Preservation + storage: originals WAV, derivatives MP3, worker-thread downloads — _Evidence: upload converts with `asyncio.to_thread(to_wav, ...)` (routers/voice.py:110); derived takes are new rows with `parent_take_id` and the original is kept (test_tuning_really_moves_the_sound_and_keeps_the_original, test_harmony_audio_keeps_the_original, test_source_takes_are_not_touched in test_properties_comp.py)_
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9. Active state and sidebar — _Evidence: child 9.1 ticked_
  - [x] 9.1 Update active_vocal_id / active_comp_id; sidebar status — _Evidence: routers/voice.py:129 (upload sets `active_vocal_id`, clears `active_comp_id`) and `POST /voice/active`; status now shown by the Song Strip's voice lane (`components/shell/SongStrip.tsx`, replaced the StudioNav status icons Nov 19; not yet seen in a browser with a real take); 'take after comp wins' checked on the live database (voice-to-export-flow 2.4)_
    - _Requirements: 10.1, 10.2, 10.3_

- [ ] 10. Deferred follow-ups (tracked)
  - [ ] 10.1 Alternating A/B "play both" comparison — _NOT DONE: no alternating-playback code in TakeCard.tsx or voice/page.tsx_
    - _Requirements: 3.1_
  - [ ] 10.2 Pitch display waveform overlay + show/hide toggle — _NOT DONE: PitchDisplay.tsx draws bars only, no waveform overlay and no toggle_
    - _Requirements: 4.2_
