# Beat Room — Implementation Plan

- [x] 1. Beat Room entry state
  - [x] 1.1 Detect fingerprint presence; show the right greeting and "Build the beat"
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 Beat-First abbreviated feel discovery; create and save a simplified fingerprint
    - _Requirements: 1.3, 1.4_

- [x] 2. Section timeline component
  - [x] 2.1 `components/studio/BeatTimeline.tsx` — colored blocks, scrub, playing highlight
    - _Requirements: 3.1, 3.2_
  - [x] 2.2 Section label editing (label-only persist)
    - _Requirements: 3.3, 10.3_

- [x] 3. Stem layer view
  - [x] 3.1 `components/studio/BeatLayers.tsx` — plain-language layers, mute toggle triggers re-render
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 4. Beat versions panel
  - [x] 4.1 Collapsible list, per-version play, set active, label editing
    - _Requirements: 7.2, 7.3, 7.4_

- [x] 5. Beat conversation
  - [x] 5.1 Wire conversation to `POST /projects/{id}/beat/conversation`
    - _Requirements: 9.4_
  - [x] 5.2 Handle all actions: regenerate, add_stem, mute_stem, generate_full_beat, restore_version, set_section_label
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.1_
  - [x] 5.3 Async job polling for generation actions
    - _Requirements: 6.3_
  - [x] 5.4 Version ids + labels in conversation context so restore resolves
    - _Requirements: 10.2_

- [x] 6. Backend: procedural generation pipeline
  - [x] 6.1 theory + composer: fingerprint → MIDI per section
    - _Requirements: 2.1, 2.2_
  - [x] 6.2 renderer: MIDI → FluidSynth + SoundFont, per-stem, memory-frugal
    - _Requirements: 2.3_
  - [x] 6.3 Section-only regeneration and stem-only generation
    - _Requirements: 5.4, 6.1, 6.2_
  - [x] 6.4 FFmpeg assembly; Storage upload (MP3) for stems and renders
    - _Requirements: 2.4, 11.1_

- [x] 7. Backend: Beat conversation route
  - [x] 7.1 Beat Room system prompt with beat-state context
    - _Requirements: 9.4, 10.2_
  - [x] 7.2 All action handlers
    - _Requirements: 10.1, 10.3_

- [x] 8. Backend: beat persistence
  - [x] 8.1 beat_versions + beat_stems records; active_beat_version_id update
    - _Requirements: 2.4, 7.1, 11.2_
  - [x] 8.2 Sidebar status indicator updates
    - _Requirements: 11.3_

- [ ] 9. Deferred follow-ups (tracked, not demo-critical)
  - [ ] 9.1 Preview with vocal (temporary overlay) — after Voice Room
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 9.2 Per-section re-render optimization
    - _Requirements: 5.1_
  - [ ] 9.3 Reorder / duplicate / remove section UI + endpoints
    - _Requirements: 3.4_
