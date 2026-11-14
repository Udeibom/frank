# Start From Any Input - Implementation Plan

Depends on spec 01 (song-record) tasks 1-3.

- [ ] 1. Models and plumbing
  - [x] 1.1 `MelodySketch` and intake result models in `models/song.py`
    - _Requirements: 3.1, 6.1_
  - [ ] 1.2 Intake routes per input kind, with job wiring and the original input stored. BUILT: `POST /intake/hum` (job), `POST /intake/lyrics`, melody confirm and reject. STILL TO BUILD: rhythm, description, voice memo. (A single route with `kind` routing was dropped on purpose: each kind needs different inputs and different waits.)
    - _Requirements: 1.1, 3.7, 6.6_

- [x] 2. Hum to melody
  - [x] 2.1 Pitch tracking, smoothing, note segmentation
    - _Requirements: 3.1_
  - [x] 2.2 Key estimation with confidence
    - _Requirements: 3.2_
  - [x] 2.3 Tempo from inter-onset intervals with confidence; no silent default
    - _Requirements: 3.3, 6.3_
  - [x] 2.4 Quantise to the grid; quality gate with plain-language reasons
    - _Requirements: 3.6_
  - [x] 2.5 Accuracy measurement on synthetic hums and 3 real hums; decide on Basic Pitch fallback (spec check could not re-verify the real-hum part: the real-hum test is skipped unless FRANK_TEST_HUM_DIR is set, and the hums are not in the repo; synthetic accuracy is covered by 7.2. DECISION Nov 11: not needed. Founder listened to voice-sound playback of all 3 hums: 'close and manageable'; the fast hum improved once playback followed the sung timing)
    - _Requirements: 3.1_
  - [x] 2.6 Playback preview render ("is this your tune?") and confirm / re-record flow
    - _Requirements: 3.4, 3.5_

- [ ] 3. Rhythm
  - [ ] 3.1 Onset detection, tempo, 16-step pattern with confidence
    - _Requirements: 4.1_
  - [ ] 3.2 Drum preview and confirmation; store as groove
    - _Requirements: 4.2, 4.3_

- [ ] 4. Words
  - [x] 4.1 Lyrics understanding call with schema validation and one repair retry (`services/intake/lyrics.py`, route `POST /intake/lyrics`; mood is decided in code from per-section labels because one overall guess flipped between runs on the same words; verified live against the model and the database, and in a browser) Revised Nov 13 after the founder's own lyric (anger and sorrow together) got a needless either-or question: anger is now a feeling, sorrow and anger are one dark mood, and the mood has its own confidence from the sections
    - _Requirements: 2.1, 2.3, 2.4_
  - [x] 4.4 Safeguards on reading the words (found by the Code Reviewer, Nov 13): everything the model writes for the person is checked to be plain (no links, digits, markup or music terms) and sent back once for repair if not; the writer's words are fenced off as data; one sloppy section is dropped without losing the answer; a long song is cut on a whole line and Frank says so; only one read per song at a time; unchanged words are not read again; a failure saving the suggested direction does not turn a good read into a failure
    - _Requirements: 2.1, 2.4, 6.2, 7.1_
  - [x] 4.5 Questions that follow how working producers listen (research: `.kiro/steering/producer-craft.md`): never an either-or ("or should it hold both" is added by code), only when dark versus warm is truly unclear, one question, in the song's own words
    - _Requirements: 2.4, 6.2, 6.5, 7.1_
  - [x] 4.2 Deterministic section repair (partition of lines) (`repair_sections`, plus `guess_sections` from blank lines and repeated stanzas as the fallback)
    - _Requirements: 2.2_
  - [ ] 4.3 (not started) Description and voice-memo path (Whisper then text path)
    - _Requirements: 5.1, 5.2_

- [ ] 5. Merge
  - [x] 5.1 Merge: fill gaps only, name disagreements, never replace a settled value (`services/intake/merge.py`; requirement 6.4 reworded Nov 13 to say exactly this)
    - _Requirements: 6.4, 6.5_
  - [ ] 5.2 (done for the words: the route returns ONE question and the Idea Room says it; NOT done for a tune that disagrees with the words, because hum hints are merged in the browser) Conflict questions surfaced to the conversation
    - _Requirements: 6.2, 6.5_

- [ ] 6. Frontend
  - [ ] 6.1 `StartSurface.tsx` reachable from every room
    - _Requirements: 1.1-1.3_
  - [x] 6.2 Playback confirmation cards; plain-language result messages (hum card done: 'Is this your tune?' with hear again / yes / not quite; verified in a real browser)
    - _Requirements: 3.4, 3.5, 7.1_

- [x] 7. Property-based tests (`backend/tests/test_properties_intake.py`)
  - [x] 7.1 Key transposition equivariance
  - [x] 7.2 Melody round-trip recall within tolerance
  - [x] 7.3 Tempo stability (covers leading silence and a jittered steady pulse; the 'small amplitude changes' part of design property 3 has no test)
  - [x] 7.4 Section partition after repair
  - [x] 7.5 Merge properties: settled values never change, merging twice changes nothing, inputs untouched, disagreements named, a modal direction is not a disagreement (`test_properties_lyrics.py`; broken on purpose to check each can fail)
  - [x] 7.6 Rejection of silence and noise
  - [x] 7.7 Prove each test can fail. Done by breaking the code on purpose and watching a test fail: hum tests (dip splitting, tuning, key, too-few-notes, octave rules, extension safety, length cap, confirm, race retry, brief), lyrics tests (21 breaks: section repair, repair idempotence, repair attempt, fallback, confidence, mood decision, mixed share, dead heat, plain-language filter, fenced words, sloppy sections, line-boundary cut, truncation flag, modal, size limit), fast tracker (3 breaks, on synthetic, breathy and real hums), model-call contract. Three tests were found too weak by this and strengthened (tuning, long-song line lengths, mixed share).
  - [x] 7.8 Model-call contract: our calls are checked against the installed Groq library's real signature (`tests/test_llm_client_contract.py`), because a fake model answer cannot notice a wrong argument name (it broke every read once, caught only by a live run)
    - _Requirements: 2.1_
  - [x] 7.9 Words, mood, filter and merge properties (`tests/test_properties_lyrics.py`, 75 tests)
    - _Requirements: 2.1 to 2.4, 6.2, 6.5, 7.1_
