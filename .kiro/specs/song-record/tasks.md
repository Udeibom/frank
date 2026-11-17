# Song Record - Implementation Plan

- [x] 1. Data layer
  - [x] 1.1 Migration 003 (applied to the live database Nov 11 and verified: tables, RLS on, phase default): `song_facet_versions`, `song_facet_active`, `song_decisions`, `phase` column; RLS like 002
    - _Requirements: 1.1, 3.1, 3.2, 4.1, 5.1, 7.3_
  - [x] 1.2 `models/song.py` Pydantic models for every facet and decision
    - _Requirements: 1.1, 2.1_
  - [x] 1.3 `db/song.py` append-only version writes, active pointer, decisions
    - _Requirements: 3.1-3.5, 4.1_

- [x] 2. Record and brief
  - [x] 2.1 `services/song/record.py` assembles the record from facets plus existing tables
    - _Requirements: 1.1-1.3, 7.3_
  - [x] 2.2 `services/song/brief.py` pure brief builder with budget trimming and role views
    - _Requirements: 2.3, 4.3, 5.4, 6.1-6.4_

- [x] 3. API
  - [x] 3.1 `routers/song.py` routes (record, facet versions, restore, branch, decisions, phase)
    - _Requirements: 3.3, 3.4, 4.1, 5.2, 5.3_
  - [x] 3.2 Ownership check on every route (same rule as auth spec)
    - _Requirements: 7.1_

- [x] 4. Frontend
  - [x] 4.1 `types/song.ts`, `store/song.ts`, refresh on project revision
    - _Requirements: 7.1_
  - [x] 4.2 "Where your song is" plain-language summary in the studio layout
    - _Requirements: 7.2_
  - [x] 4.3 Phase prompt: offer refining when a first complete draft exists; user toggle
    - _Requirements: 5.2, 5.3_

- [x] 5. Property-based tests (`backend/tests/test_properties_song.py`)
  - [x] 5.1 Append-only and lineage properties
    - _Requirements: 3.1, 3.2_
  - [x] 5.2 Restore round-trip property
    - _Requirements: 3.3_
  - [x] 5.3 Brief determinism, budget, and trimming-order properties
    - _Requirements: 6.2, 6.3, 2.3, 5.4_
  - [x] 5.4 Prove each test can fail (revert a fix and watch it fail)

- [x] 6. Wire-in (shared with spec 07)
  - [x] 6.1 Idea and Feel conversations use `build_brief` — _Evidence: record.system_with_brief used in routers/conversation.py and feel.py; tests/test_brief_wiring.py. Not run against a live LLM or project (no network in this session)_
  - [x] 6.2 Beat, Voice, Mix conversations use `build_brief` — _Evidence: same helper in routers/beat.py, voice.py, mix.py; tests/test_brief_wiring.py_
    - _Requirements: 6.1_
