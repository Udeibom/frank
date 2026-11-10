# Voice-to-Export Flow — Implementation Plan

- [x] 1. Shared state across rooms
  - [x] 1.1 Project store `refresh()` + `revision`; layout re-syncs on route change; rooms re-read on revision
    - _Requirements: 1.1, 1.2_

- [x] 2. A new take becomes the vocal the Mix Room uses
  - [x] 2.1 `upload_take` sets `active_vocal_id` (earlier fix)
    - _Requirements: 2.1_
  - [x] 2.2 Uploading or choosing a take clears `active_comp_id` (last chosen wins)
    - _Requirements: 2.2, 2.4_
  - [x] 2.3 Move FFmpeg conversion in `upload_take` off the event loop (found by the audio-architecture hook)
    - _Requirements: 2.1_
  - [ ] 2.4 Verify in the browser and database that a take recorded after a comp is what the Mix Room plays
    - _Requirements: 2.2, 2.3, 2.5_

- [x] 3. Previews never change saved state
  - [x] 3.1 Dedicated vocal-preview job, no mix version and no pointer change
    - _Requirements: 4.1, 4.2_
  - [ ] 3.2 Automated check that a preview leaves the mix list unchanged (needs DB; covered by the browser test in 5.1)
    - _Requirements: 4.3_

- [ ] 4. Close the Mix Room resolution gaps
  - [x] 4.1 Resolve the comp by `active_comp_id`, not `get_latest_comp`
    - _Requirements: 2.3, 2.4_
  - [ ] 4.2 Add an `is_harmony` flag instead of matching the label prefix (needs a schema migration; deferred to the auth migration)
    - _Requirements: 2.4_
  - [x] 4.3 Extract vocal resolution into a pure function (`vocal_resolution.py`)
    - _Requirements: 2.4, 2.5_

- [ ] 5. Browser-driven integration test (Playwright MCP)
  - [ ] 5.1 Click through Voice → Beat → Mix and compare each room with `project_active_state`
    - _Requirements: 1.2, 3.1, 3.2, 7.1_
  - [ ] 5.2 Export Room loads `active_mix_id` and records `mix_version_id`
    - _Requirements: 5.1, 5.3, 5.4_

- [ ] 6. Property-based tests
  - [x] 6.1 Vocal resolution properties (`backend/tests/test_properties_audio.py`)
    - _Requirements: 2.4_
  - [ ] 6.2 Pointer moves never delete rows or files
    - _Requirements: 6.1, 6.2_
