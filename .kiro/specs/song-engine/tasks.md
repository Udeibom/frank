# Song Engine - Implementation Plan

Depends on spec 01 and spec 02 (melody, groove, structure). Spec 05's sound spike runs alongside task 6.

- [ ] 1. Contracts
  - [ ] 1.1 `Plan`, `PartPlan`, `Score`, `StyleProfile`, typed operation models (Pydantic)
    - _Requirements: 7.1, 7.2, 5.3_
  - [ ] 1.2 Plan storage in `beat_versions.params`; legacy loading path
    - _Requirements: 7.3, 8.2_

- [ ] 2. Styles
  - [ ] 2.1 Style profile schema and loader; blending by genre hints, warmth, brightness, tempo feel
    - _Requirements: 4.1, 4.2_
  - [ ] 2.2 Initial profiles (soul/r&b, pop, lo-fi, rock, ambient, folk, hip-hop, gospel, electronic)
    - _Requirements: 4.2_
  - [ ] 2.3 Report unsupported hints in plain language
    - _Requirements: 4.3_

- [ ] 3. Planner
  - [ ] 3.1 Sections from the structure facet (lines to bars) or style template
    - _Requirements: 1.1_
  - [ ] 3.2 Energy curve and per-section part choices with rotation across repeats
    - _Requirements: 1.2, 2.1_
  - [ ] 3.3 Stable per-part seeds
    - _Requirements: 6.1_

- [ ] 4. Composer
  - [ ] 4.1 Richer harmony: sevenths, inversions, voice-leading, harmonic rhythm
    - _Requirements: 3.1_
  - [ ] 4.2 Motif-based melody with rests and phrase shapes
    - _Requirements: 3.2_
  - [ ] 4.3 Harmonise a confirmed melody (Viterbi over bars) and fit bass
    - _Requirements: 3.3_
  - [ ] 4.4 Bass patterns with approach notes; drum grooves, fills, crashes, breakdowns
    - _Requirements: 1.2, 1.4_
  - [ ] 4.5 Extras (counter-melody, arpeggios, swells, risers) and transition events
    - _Requirements: 1.3, 1.4_
  - [ ] 4.6 Seeded humanisation
    - _Requirements: 6.3_
  - [ ] 4.7 Key safety in every part
    - _Requirements: 3.4_

- [ ] 5. Assembly
  - [ ] 5.1 Per-part, per-section rendering; one song-level loudness pass; remove per-section peak normalisation
    - _Requirements: 2.1, 2.3, 8.1_
  - [ ] 5.2 Chorus lift margin check
    - _Requirements: 2.2_
  - [ ] 5.3 Cross-join tails and transition rendering (no hard cuts)
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
  - [ ] 7.4 "Another" uses a new seed and sounds different
    - _Requirements: 6.2_

- [ ] 8. Calibration
  - [ ] 8.1 Re-run `baseline_audit.py`: dead-field check now differs; chorus lift margin met; melody chord-tone share above threshold
    - _Requirements: 2.2, 3.2, 4.1_
  - [ ] 8.2 Founder listens to the new renders against the Nov 11 baseline and says better, same or worse, with reasons

- [ ] 9. Property-based tests (`backend/tests/test_properties_engine.py`)
  - [ ] 9.1 Determinism, variation, key safety, strong-beat harmony
  - [ ] 9.2 Dynamics margin, no dead fields, locality, density monotonicity
  - [ ] 9.3 Structure validity, stem sum
  - [ ] 9.4 Prove each test can fail
