# Feel Lab — Implementation Plan

- [x] 1. Feel Lab conversation
  - [x] 1.1 Wire the conversation panel to `POST /projects/{id}/feel/conversation`
    - _Requirements: 1.1, 1.2, 5.1_
  - [x] 1.2 Handle `generate_texture`: show "Finding a sound...", poll the job, render the texture
    - _Requirements: 2.3, 5.2, 5.3, 8.2_
  - [x] 1.3 Handle `approve_direction`: confirm and commit the fingerprint
    - _Requirements: 3.5, 5.1_

- [x] 2. Texture playback component
  - [x] 2.1 `components/audio/TexturePlayer.tsx` — waveform + play/pause, auto-play, loop once then stop
    - _Requirements: 2.1, 2.2_
  - [x] 2.2 Replayable texture cards in the conversation history
    - _Requirements: 2.4_

- [x] 3. Hum recording
  - [x] 3.1 "Hum it" button reusing the recorder hook
    - _Requirements: 1.4_
  - [x] 3.2 Upload to `POST /projects/{id}/feel/hum`, show analysis in the conversation
    - _Requirements: 1.5, 5.4_

- [x] 4. Fingerprint state management
  - [x] 4.1 Update the project store with the fingerprint as it evolves (accumulating merge, clamped fields)
    - _Requirements: 3.1, 3.2, 3.7_
  - [x] 4.2 Save the fingerprint on approval; set reference_texture_id / hum_reference_file
    - _Requirements: 3.3, 3.4, 3.6, 5.5_
  - [x] 4.3 Load an existing fingerprint on Feel Lab entry
    - _Requirements: 4.1_

- [x] 5. Backend: Feel Lab conversation route
  - [x] 5.1 Feel Lab system prompt in `services/llm/prompts.py`
    - _Requirements: 5.1_
  - [x] 5.2 LLM call with fingerprint context and structured output parsing
    - _Requirements: 5.1_
  - [x] 5.3 Fingerprint-update extraction and merge
    - _Requirements: 3.2_

- [x] 6. Backend: procedural texture generation
  - [x] 6.1 `services/generation/fingerprint.py` — fingerprint → params + deterministic cache_key
    - _Requirements: 6.1, 6.4_
  - [x] 6.2 Render via the procedural engine (composer → FluidSynth renderer) to MP3
    - _Requirements: 6.1, 6.3_
  - [x] 6.3 Async job creation/execution and Storage upload
    - _Requirements: 6.2, 8.1_
  - [x] 6.4 Cache check (indexed cache_key) before generating
    - _Requirements: 6.4_

- [x] 7. Backend: hum analysis
  - [x] 7.1 FFmpeg conversion to WAV
    - _Requirements: 7.1_
  - [x] 7.2 librosa pyin pitch contour + librosa tempo detection
    - _Requirements: 7.2_
  - [x] 7.3 Plain-language description + fingerprint hints; store under hums/
    - _Requirements: 7.3, 7.4_

- [x] 8. Backend: fingerprint persistence
  - [x] 8.1 `POST /feel/fingerprint` saves to `feel_fingerprints` and sets active_fingerprint_id
    - _Requirements: 3.6, 5.5_
  - [x] 8.2 Sidebar status indicator updates to "has content"
    - _Requirements: 3.6_

- [x] 9. Async job system
  - [x] 9.1 Job lifecycle with guarded failure writes; `GET /jobs/{id}/status` polling
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 10. Return-visit handling
  - [x] 10.1 Detect existing fingerprint, load summary, greet with what was established
    - _Requirements: 4.1_
  - [x] 10.2 "Keep going" vs "start fresh" (old fingerprint preserved)
    - _Requirements: 4.2, 4.3_
