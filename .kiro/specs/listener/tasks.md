# Listener - Implementation Plan

Depends on spec 01 (record) and, for per-part measures, spec 04 (stems).

- [ ] 1. Core measurements
  - [ ] 1.1 Loudness per section (gated, K-weighted) and per part
    - _Requirements: 1.1, 1.3_
  - [ ] 1.2 Density, colour, section-to-section change
    - _Requirements: 1.1_
  - [ ] 1.3 Repetition (chroma/MFCC self-similarity, melody similarity)
    - _Requirements: 1.4_
  - [ ] 1.4 Melody measures (range, movement, chord-tone fit)
    - _Requirements: 1.5_
  - [ ] 1.5 Safety measures (clipping, noise, silence) and the "could not measure" path
    - _Requirements: 3.1_

- [ ] 2. Voice measures
  - [ ] 2.1 Vocal tuning against the song's notes
    - _Requirements: 1.2_
  - [ ] 2.2 Vocal-to-beat timing offset
    - _Requirements: 1.2_
  - [ ] 2.3 Vocal/beat competition in the voice range
    - _Requirements: 1.3_

- [ ] 3. Findings
  - [ ] 3.1 Finding model, rule functions, threshold config with provenance comments
    - _Requirements: 2.1, 2.4_
  - [ ] 3.2 Plain-language templates (no jargon, no units)
    - _Requirements: 2.2_
  - [ ] 3.3 "No clear cause" path and confidence
    - _Requirements: 3.2, 3.3_

- [ ] 4. Service
  - [ ] 4.1 `measure_song`, `find_issues`, `compare`, read-only guarantee
    - _Requirements: 4.1, 4.2_
  - [ ] 4.2 `listener_cache` table and caching by version id
    - _Requirements: 5.1_
  - [ ] 4.3 `POST /projects/{id}/listen` job with progress text and scoped runs
    - _Requirements: 5.2, 5.3_
  - [ ] 4.4 Mismatch recording hook for taste signals (stores; spec 09 reads)
    - _Requirements: 6.1_

- [ ] 5. Calibration
  - [ ] 5.1 Run on the baseline renders (frank-listening/baseline) and confirm it flags the known problems: weak chorus lift, wandering melody
    - _Requirements: 1.1, 1.5, 2.1_
  - [ ] 5.2 Founder check: do the findings match what the founder hears?

- [ ] 6. Property-based tests (`backend/tests/test_properties_listener.py`)
  - [ ] 6.1 Gain invariance, identity, timing recovery
  - [ ] 6.2 Silence, determinism, read-only, honesty
  - [ ] 6.3 Prove each test can fail
