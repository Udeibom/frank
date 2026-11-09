# Export Room — Implementation Plan

- [x] 1. Final listen UI
  - [x] 1.1 Load and play the active mix on entry with a warm greeting
    - _Requirements: 1.1, 1.2_

- [x] 2. Mastering
  - [x] 2.1 "Make it radio ready" button
    - _Requirements: 2.1_
  - [x] 2.2 Async master job; auto-play result; compare before/after
    - _Requirements: 2.2, 2.3_
  - [x] 2.3 Non-destructive; one-click "go back to the original"
    - _Requirements: 2.4, 2.5_

- [x] 3. Download
  - [x] 3.1 "Download" button triggers full render only if needed
    - _Requirements: 3.1, 3.3_
  - [x] 3.2 Dedup so repeat downloads are instant
    - _Requirements: 3.4, 5.4_
  - [x] 3.3 Filename sanitization; warm closing message on success
    - _Requirements: 3.2, 3.5_

- [x] 4. Export history
  - [x] 4.1 List past exports (date + source mix version), re-download links
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 5. Backend: mastering pipeline
  - [x] 5.1 `services/audio/mastering.py` pedalboard chain (multiband comp, limiter, loudnorm -14 LUFS)
    - _Requirements: 6.1_
  - [x] 5.2 WAV → MP3 320k via FFmpeg; store in private exports/ bucket
    - _Requirements: 6.1, 6.2_

- [x] 6. Backend: export routes
  - [x] 6.1 All three endpoints (export, list, download)
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 6.2 Signed URL generation for download
    - _Requirements: 5.3_
  - [x] 6.3 Export records with mix_version_id + mastered; dedup lookup
    - _Requirements: 4.1, 5.4_

- [ ] 7. Deferred follow-ups (tracked)
  - [ ] 7.1 Waveform on the final-listen screen
    - _Requirements: 1.2_
  - [ ] 7.2 Two-pass loudnorm; true-320k from un-encoded source
    - _Requirements: 6.1_
