# Finish and Intent - Implementation Plan (spec 11)

Depends on song-engine 5.4 (stems), 03 (Listener), 08 (refine loop).

- [ ] 1. Per-part mix model, renderer, legacy one-block path and "rebuild the parts"
  - _Requirements: 1.1, 1.4_
- [ ] 2. Mix conversation over parts (typed actions, max three), stem balance view with every part
  - _Requirements: 1.2, 1.3_
- [ ] 3. Finishing: full-quality source rule, two-pass loudness, true peak, Listener check, before/after
  - _Requirements: 2.1-2.3_
- [ ] 4. Intent statement capture and the intent check before first export
  - _Requirements: 3.1-3.3_
- [ ] 5. Surprise version, once per song
  - _Requirements: 4.1, 4.2_
- [ ] 6. Download separate parts (zip) and final-listen waveform
  - _Requirements: 5.1, 5.2_
- [ ] 7. Property tests and a real-audio before/after listening set
