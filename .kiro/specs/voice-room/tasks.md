# Voice Room — Implementation Plan

- [x] 1. Microphone setup
  - [x] 1.1 Permission request flow with warm explanation
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 Best-effort headphone detection (non-blocking tip)
    - _Requirements: 1.3, 1.4_
  - [x] 1.3 `hooks/useRecorder.ts` reusable recording hook
    - _Requirements: 2.1_

- [x] 2. Recording UI
  - [x] 2.1 `components/audio/VocalRecorder.tsx` — record button, timer, level meter, stop
    - _Requirements: 2.1, 2.2_
  - [x] 2.2 Beat playback sync; "Record with beat" / "Record without beat"
    - _Requirements: 1.5, 2.2_
  - [x] 2.3 Take card: waveform, duration, label, play
    - _Requirements: 2.3_

- [x] 3. Take management
  - [x] 3.1 Take list with select-to-compare and per-take play
    - _Requirements: 3.1_
  - [x] 3.2 Label editing; set active take
    - _Requirements: 2.5, 3.2_

- [x] 4. Pitch visualization
  - [x] 4.1 `components/audio/PitchDisplay.tsx` — color-coded tuning with non-color cue
    - _Requirements: 4.2, 4.3_
  - [x] 4.2 Fetch pitch data after upload
    - _Requirements: 4.1_

- [x] 5. Pitch correction
  - [x] 5.1 Three-mode selector (conversation + buttons)
    - _Requirements: 5.1_
  - [x] 5.2 Async correction job; new "(tuned)" take card; original preserved
    - _Requirements: 5.3, 5.4_
  - [x] 5.3 "Lock it in" real per-note snapping with crossfades
    - _Requirements: 5.2_
  - [x] 5.4 Original vs corrected comparison
    - _Requirements: 5.5_

- [x] 6. Vocal comp
  - [x] 6.1 Trigger from conversation; score + assemble best segments
    - _Requirements: 6.1, 6.2_
  - [x] 6.2 Comp view with segment provenance; accept/adjust/redo
    - _Requirements: 6.3, 6.4, 6.5_

- [x] 7. Harmony
  - [x] 7.1 Trigger from conversation; higher/lower/both options
    - _Requirements: 7.1, 7.3_
  - [x] 7.2 Mode-aware interval from fingerprint; stored as a Mix Room layer
    - _Requirements: 7.2, 7.4_

- [x] 8. Backend: all Voice Room routes
  - [x] 8.1 Upload + async pitch analysis (librosa pyin)
    - _Requirements: 8.1, 4.1_
  - [x] 8.2 Correction job (pylibrb), comp job, harmony job
    - _Requirements: 8.4, 8.5, 5.4_
  - [x] 8.3 Conversation route with patient vocal-producer prompt
    - _Requirements: 8.7_
  - [x] 8.4 Preservation + storage: originals WAV, derivatives MP3, worker-thread downloads
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9. Active state and sidebar
  - [x] 9.1 Update active_vocal_id / active_comp_id; sidebar status
    - _Requirements: 10.1, 10.2, 10.3_

- [ ] 10. Deferred follow-ups (tracked)
  - [ ] 10.1 Alternating A/B "play both" comparison
    - _Requirements: 3.1_
  - [ ] 10.2 Pitch display waveform overlay + show/hide toggle
    - _Requirements: 4.2_
