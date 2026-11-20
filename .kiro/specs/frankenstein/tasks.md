# Frankenstein - Implementation Plan (spec 14)

Order: rules and foundations first, then the organs on Render, then the two Spaces, then offline data, then the
rooms. Each task is ticked only with evidence (file, test, live check). Live checks use the deployed services.

## A. Rules and housekeeping
- [ ] 1. Licence and rule review written into `THIRD_PARTY.md` and the review doc (Deezer dropped, Gemini region rule, research-only licences out, video music rule)
  - _Requirements: 9.1, 9.2_
- [ ] 2. Delete the design test account and its two songs (founder approved 19 Nov)
- [ ] 3. Region gate: Vercel route for the country, `X-Frank-Region` header, backend skips Gemini for EEA/CH/GB
  - _Requirements: 9.1_
- [ ] 4. One-time notice that clips go to Google to be listened to, stored per user
  - _Requirements: 9.1_

## B. Foundations
- [ ] 5. Remote organ client `backend/app/services/remote/spaces.py` with wake-up, timeouts and plain fallbacks
  - _Requirements: 1.4_
- [ ] 6. Migration 010: pgvector, `sound_embeddings`, `references`, `provenance`, `vocal_takes.words`, realtime on `async_jobs`
  - _Requirements: 7.1, 7.2, 1.3_
- [ ] 7. Provenance service and its use on change lines and the credits list
  - _Requirements: 1.3_

## C. Organs on Render
- [ ] 8. Word timings from Groq Whisper on every take; "redo this line" uses them
  - _Requirements: 4.4_
- [ ] 9. CMU dictionary syllables, stress and rhymes; Datamuse near rhymes; `POST /lyrics/analyse`
  - _Requirements: 5.1, 5.2_
- [ ] 10. Basic Pitch (ONNX) as a hum tracker beside pyin, with `pitch_compare.py`
  - _Requirements: 2.6_
- [ ] 11. Gemini listening: section bounce plus numbers, at most three notes, confirmed by the Listener
  - _Requirements: 2.3_
- [ ] 12. Gemini looking plus measured colours: photo to feeling words and fingerprint hints
  - _Requirements: 6.6_
- [ ] 13. Open-Meteo "right now" feeling words
  - _Requirements: 6.7_
- [ ] 14. MusicBrainz and ListenBrainz lookup for named songs and artists
  - _Requirements: 6.3_
- [ ] 15. Exa and Firecrawl research for the creative director (needs keys)
  - _Requirements: 6.3_
- [ ] 16. Jamendo reference search and reference upload (in memory, never stored)
  - _Requirements: 6.1_
- [ ] 17. Freesound atmosphere layer (CC0 / CC BY only, attributed; needs key)
  - _Requirements: 3.7_
- [ ] 18. MIDI export: "Download the notes"
  - _Requirements: 8.3_
- [ ] 19. sfizz renderer with CC0 samples for keys and strings, FluidSynth fallback
  - _Requirements: 3.5_
- [ ] 20. Studio plugins (Dragonfly, LSP) through pedalboard for "Add space" and the master, with fallback
  - _Requirements: 3.6_
- [ ] 21. pgvector store for sound embeddings; taste memory matches by sound
  - _Requirements: 7.1, 2.1_

## D. Space frank-ears
- [ ] 22. Space scaffold, deploy script, health endpoint (needs an HF write token)
- [ ] 23. CLAP audio and text embeddings; Feeling ranks directions by the user's words
  - _Requirements: 2.1_
- [ ] 24. Discogs-EffNet style and mood labels; Listener rule for style drift
  - _Requirements: 2.2_
- [ ] 25. Audiobox Aesthetics scores in the refine loop
  - _Requirements: 2.4_
- [ ] 26. allin1 sections and beats; Chordino chords
  - _Requirements: 2.5_
- [ ] 27. BS-RoFormer parts for references (and stronger bleed removal)
  - _Requirements: 6.2_
- [ ] 28. PESTO contour comparison
  - _Requirements: 2.6_
- [ ] 29. GoEmotions lyric emotion arc
  - _Requirements: 5.3_
- [ ] 30. Matchering reference master in Finish
  - _Requirements: 6.4_
- [ ] 31. DeepFilterNet "quiet" derived take
  - _Requirements: 4.3_

## E. Space frank-hands
- [ ] 32. Space scaffold and deploy
- [ ] 33. Anticipatory Music Transformer accompaniment as notes
  - _Requirements: 3.4_
- [ ] 34. DDSP: hum or take becomes an instrument
  - _Requirements: 4.1_
- [ ] 35. DiffSinger guide vocal singing the lyrics
  - _Requirements: 4.2_
- [ ] 36. Kokoro: Frank reads its notes aloud
  - _Requirements: 4.5_
- [ ] 37. Stable Audio 3 Small atmosphere
  - _Requirements: 3.7_
- [ ] 38. Diff-MST mix settings from a reference
  - _Requirements: 6.5_
- [ ] 39. ACE-Step add-one-part blind test prepared under `~/frank-listening/ace-step/`
  - _Requirements: 3.8_

## F. Offline data (Kaggle)
- [ ] 40. Groove MIDI Dataset to `grooves.json`; drums use it; ops looser and tighter
  - _Requirements: 3.1_
- [ ] 41. Chordonomicon to `chord_tables.json`; progressions weighted by it
  - _Requirements: 3.2_
- [ ] 42. Lakh/Slakh MIDI to `arrangement_stats.json`; layers use it
  - _Requirements: 3.3_
- [ ] 43. Song Describer captions calibrate words-to-fingerprint with CLAP
  - _Requirements: 9.4_
- [ ] 44. MTG-Jamendo mood check
  - _Requirements: 9.5_

## G. Rooms
- [ ] 45. Realtime job updates with polling fallback
  - _Requirements: 7.2_
- [ ] 46. WaveSurfer waveforms with regions in Voice and Blend
  - _Requirements: 8.1_
- [ ] 47. Tiptap lyric editor with syllable, stress and rhyme marks
  - _Requirements: 5.1_
- [ ] 48. React Flow song family tree
  - _Requirements: 8.2_
- [ ] 49. Finish: notes download, credits page, reference master comparison
  - _Requirements: 8.3, 6.4_
- [ ] 50. Feeling: photo, "right now", reference song, words-ranked directions
  - _Requirements: 6.1, 6.6, 6.7, 2.1_
- [ ] 51. Voice: headphone check, quiet take, hum as instrument, sung guide, redo a line
  - _Requirements: 8.4, 4.1, 4.2, 4.3, 4.4_
- [ ] 52. Blend: Frank listens (Gemini), mix like the reference, conduct mode (MediaPipe)
  - _Requirements: 2.3, 6.5, 8.5_
- [ ] 53. Music: accompaniment from the tune, atmosphere layer, looser/tighter drums
  - _Requirements: 3.1, 3.4, 3.7_
- [ ] 54. Frank speaks toggle
  - _Requirements: 4.5_

## H. Proof
- [ ] 55. Property tests for every pure mapping in design.md "Testing", and frontend fast-check
- [ ] 56. Live end-to-end run on the deployed services, recorded in `docs/demo-runs/`
