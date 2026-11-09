# Mix Room — Implementation Plan

- [x] 1. Mix assembly on entry
  - [x] 1.1 Detect available stems on entry
    - _Requirements: 1.1_
  - [x] 1.2 Auto-assemble and play initial mix with default gains
    - _Requirements: 1.2, 1.4_
  - [x] 1.3 Missing-stem notification when beat or vocal is absent
    - _Requirements: 1.3_

- [x] 2. Mix conversation
  - [x] 2.1 Wire conversation to `POST /projects/{id}/mix/conversation`
    - _Requirements: 7.4_
  - [x] 2.2 Handle all action types (adjust_levels, apply_effect, section_adjust, render_preview, analyze_mix)
    - _Requirements: 7.5, 2.1, 2.2, 2.3, 2.5_
  - [x] 2.3 "Something feels off" → analyze and suggest a specific change
    - _Requirements: 2.4_
  - [x] 2.4 Trigger preview render after adjustments; show progress and play result
    - _Requirements: 2.6, 4.3_

- [x] 3. Mix versions panel
  - [x] 3.1 Collapsible list; play, set active, label; plain-text summary in label
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Stem balance view
  - [x] 4.1 Read-only stem list with harmony on/off toggle; no numeric levels
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 5. Backend: mix rendering pipeline
  - [x] 5.1 `services/audio/mixing.py` FFmpeg overlay with gains
    - _Requirements: 8.1_
  - [x] 5.2 pedalboard effects chain (API confirmed via Context7)
    - _Requirements: 8.1_
  - [x] 5.3 Preview (64k) vs full (320k) render; async job
    - _Requirements: 4.1, 4.2, 7.1_
  - [x] 5.4 Real per-section gain by time-windowing the beat
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 5.5 Accumulate-and-release memory-frugal rendering
    - _Requirements: 8.2_
  - [x] 5.6 Dedicated vocal-preview job (no version, no active change)
    - _Requirements: 9.1, 9.2_

- [x] 6. Backend: mix conversation and analysis
  - [x] 6.1 Mix Room system prompt
    - _Requirements: 7.4_
  - [x] 6.2 `analyze_mix` → plain language, no raw numbers
    - _Requirements: 8.3_

- [x] 7. Active state and sidebar
  - [x] 7.1 Update active_mix_id; sidebar status indicator
    - _Requirements: 10.1, 10.2_
