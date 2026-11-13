# Start From Any Input - Implementation Plan

Depends on spec 01 (song-record) tasks 1-3.

- [x] 1. Models and plumbing
  - [x] 1.1 `MelodySketch` and intake result models in `models/song.py`
    - _Requirements: 3.1, 6.1_
  - [x] 1.2 `POST /projects/{id}/intake` and job wiring (kind routing, original input stored) (hum endpoint + job + confirm/reject built and verified live; the other input kinds come with their own tasks)
    - _Requirements: 1.1, 3.7, 6.6_

- [x] 2. Hum to melody
  - [x] 2.1 Pitch tracking, smoothing, note segmentation
    - _Requirements: 3.1_
  - [x] 2.2 Key estimation with confidence
    - _Requirements: 3.2_
  - [x] 2.3 Tempo from inter-onset intervals with confidence; no silent default
    - _Requirements: 3.3, 6.3_
  - [x] 2.4 Quantise to the grid; quality gate with plain-language reasons
    - _Requirements: 3.6_
  - [x] 2.5 Accuracy measurement on synthetic hums and 3 real hums; decide on Basic Pitch fallback (DECISION Nov 11: not needed. Founder listened to voice-sound playback of all 3 hums: 'close and manageable'; the fast hum improved once playback followed the sung timing)
    - _Requirements: 3.1_
  - [x] 2.6 Playback preview render ("is this your tune?") and confirm / re-record flow
    - _Requirements: 3.4, 3.5_

- [ ] 3. Rhythm
  - [ ] 3.1 Onset detection, tempo, 16-step pattern with confidence
    - _Requirements: 4.1_
  - [ ] 3.2 Drum preview and confirmation; store as groove
    - _Requirements: 4.2, 4.3_

- [ ] 4. Words
  - [ ] 4.1 Lyrics understanding call with schema validation and one repair retry
    - _Requirements: 2.1, 2.3, 2.4_
  - [ ] 4.2 Deterministic section repair (partition of lines)
    - _Requirements: 2.2_
  - [ ] 4.3 Description and voice-memo path (Whisper then text path)
    - _Requirements: 5.1, 5.2_

- [ ] 5. Merge
  - [ ] 5.1 Merge with confidence and conflict rules
    - _Requirements: 6.4, 6.5_
  - [ ] 5.2 Conflict questions surfaced to the conversation
    - _Requirements: 6.2, 6.5_

- [ ] 6. Frontend
  - [ ] 6.1 `StartSurface.tsx` reachable from every room
    - _Requirements: 1.1-1.3_
  - [x] 6.2 Playback confirmation cards; plain-language result messages (hum card done: 'Is this your tune?' with hear again / yes / not quite; verified in a real browser)
    - _Requirements: 3.4, 3.5, 7.1_

- [ ] 7. Property-based tests (`backend/tests/test_properties_intake.py`)
  - [x] 7.1 Key transposition equivariance
  - [x] 7.2 Melody round-trip recall within tolerance
  - [x] 7.3 Tempo stability
  - [ ] 7.4 Section partition after repair
  - [ ] 7.5 Merge confidence, user-priority, idempotence
  - [x] 7.6 Rejection of silence and noise
  - [x] 7.7 Prove each test can fail (done for hum tests: dip splitting, tuning, key equivariance, too-few-notes; tuning test was too weak at first and was strengthened)
