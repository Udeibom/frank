# Private Audio — Implementation Plan

- [x] 1. Signing core
  - [x] 1.1 `signing.py`: `parse_storage_url`, `sign_json` (pure), cached batch signer, `fetch_audio_bytes`
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 5.1, 5.2_
  - [x] 1.2 Property tests (`tests/test_properties_signing.py`, 9 tests): parse round-trip, other hosts rejected, only whole-value URLs change, JSON shape preserved, signer failure leaves input intact
    - _Requirements: 2.2, 2.5_

- [x] 2. Middleware
  - [x] 2.1 Pure ASGI middleware rewriting JSON bodies; skips bodies with no storage URL; fixes `content-length`
    - _Requirements: 2.3, 2.4, 5.3_
  - [x] 2.2 Registered inside CORS in `main.py`
    - _Requirements: 2.3_

- [x] 3. Backend reads
  - [x] 3.1 Replaced the four raw `httpx.get(url)` audio downloads with `fetch_audio_bytes`
    - _Requirements: 3.1, 3.2_

- [x] 4. Switch
  - [x] 4.1 All seven buckets set private
    - _Requirements: 1.1_

- [x] 5. Verify
  - [x] 5.1 Public-form URL refused (400) for old and new files; API returns signed URLs that download
    - _Requirements: 1.2, 2.1_
  - [x] 5.2 Harmony, comp, tuning, mix and export jobs read private files and complete
    - _Requirements: 3.1_
  - [x] 5.3 Browser (Integration Tester agent): Voice and Mix rooms fetch signed URLs on play
    - _Requirements: 4.2_

## Notes

- Right after the switch, one already-fetched public URL still returned 200 for a short time (edge cache). A few minutes later every public-form URL returned 400. Expect a short lag after changing a bucket.
- Live-only, not separately tested: the signed-URL cache reuse under load, and the "fail open" path when Storage is down (covered by property tests only).
