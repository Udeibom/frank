# Frankenstein - Implementation Plan (spec 14)

Order: rules and foundations first, then the organs on Render, then the two Spaces, then offline data, then the
rooms. Each task is ticked only with evidence (file, test, live check). Live checks use the deployed services.

## A. Rules and housekeeping
- [x] 1. Licence and rule review written into `THIRD_PARTY.md` and the review doc (Deezer dropped, Gemini region rule, research-only licences out, video music rule) — _Evidence: `THIRD_PARTY.md` licence notes (MIT decision, non-commercial parts, no copyrighted music stored, demo-video music rule, Gemini region rule); review doc Part 4 'What changed when it was built'_
  - _Requirements: 9.1, 9.2_
- [x] 2. Delete the design test account and its two songs (founder approved 19 Nov) — _Evidence: live query on 21 Nov, `select count(*) from auth.users where email='frank-design-test@example.com'` returns 0_
- [x] 3. Region gate: Vercel route for the country, `X-Frank-Region` header, backend skips Gemini for EEA/CH/GB — _Evidence: `backend/app/services/region.py` GEMINI_BLOCKED + `middleware/region.py` (reads `X-Frank-Region`), `frontend/app/api/region/route.ts` (edge route), header sent in `frontend/lib/api/client.ts:43`; tests test_gemini_is_blocked_unless_the_country_is_known_and_outside_eea_ch_uk and test_every_eea_country_switzerland_and_the_uk_are_blocked pass_
  - _Requirements: 9.1_
- [x] 4. One-time notice that clips go to Google to be listened to, stored per user — _Evidence: `frontend/components/studio/GeminiNotice.tsx` (shown once, remembered in localStorage per computer; says nothing is sent in the EEA, CH and GB). Seen as code and type-check only, not in a browser. Stored per browser, not per user account_
  - _Requirements: 9.1_

## B. Foundations
- [x] 5. Remote organ client `backend/app/services/remote/spaces.py` with wake-up, timeouts and plain fallbacks — _Evidence: `backend/app/services/remote/spaces.py` (`call` with timeout thread, `available()` health wake-up, RemoteUnavailable with a plain sentence); live: ears and hands health answered 8-24 s after sleeping in ~/frank-listening/check_all.log, and three Space failures came back as plain sentences in the 21 Nov Kaggle log_
  - _Requirements: 1.4_
- [x] 6. Migration 010: pgvector, `sound_embeddings`, `references`, `provenance`, `vocal_takes.words`, realtime on `async_jobs` — _Evidence: `backend/db/migrations/010_frankenstein.sql` (vector extension, sound_embeddings, song_references, provenance, vocal_takes.words, realtime on async_jobs). The table is `song_references`, not `references`. Live: feel/ranked (reads sound_embeddings) and finish/credits (reads provenance) answered 200 on production in the 21 Nov Kaggle log_
  - _Requirements: 7.1, 7.2, 1.3_
- [x] 7. Provenance service and its use on change lines and the credits list — _Evidence: `backend/app/services/provenance.py` (line_for, note, for_project, credits), called from the beat, voice, refine, listen, atmosphere, export and reference runners; test_every_provenance_line_is_jargon_free passes; live: finish/credits returned the credit lines (Open-Meteo CC BY 4.0 and others) in the 21 Nov Kaggle log_
  - _Requirements: 1.3_

## C. Organs on Render
- [ ] 8. Word timings from Groq Whisper on every take; "redo this line" uses them — _NOT DONE: word timings are done (`services/words/timing.py` transcribe_words with Groq Whisper, saved as `vocal_takes.words` by `voice_runner._words_for_take`; test_line_spans_never_overlap_or_run_backwards passes; each line is marked and playable in `TakeCard.tsx` lineRegions). MISSING: nothing re-records one line from those timings, there is no 'redo this line' action_
  - _Requirements: 4.4_
- [x] 9. CMU dictionary syllables, stress and rhymes; Datamuse near rhymes; `POST /lyrics/analyse` — _Evidence: `backend/app/services/words/sound.py` (CMU dictionary offline, Datamuse near rhymes) and `POST /lyrics/analyse` in `routers/lyrics.py:129`; live: lyrics/analyse and lyrics/rhymes ok (Datamuse sounds_like returned, near list empty) in the 21 Nov Kaggle log_
  - _Requirements: 5.1, 5.2_
- [x] 10. Basic Pitch (ONNX) as a hum tracker beside pyin, with `pitch_compare.py` — _Evidence: `services/intake/basic_pitch_notes.py` plus `scripts/pitch_compare.py`; measured result in `services/intake/melody.py:517` (pyin 0.98, Basic Pitch 0.81 on synthetic hums with known notes, so pyin stays the default and `HUM_TRACKER` switches). Note: KIRO_USAGE.md says the comparison used the founder's real hums; the script builds synthetic ones. That line needs correcting_
  - _Requirements: 2.6_
- [ ] 11. Gemini listening: section bounce plus numbers, at most three notes, confirmed by the Listener — _NOT DONE: code exists (`services/llm/gemini_media.py` listen/confirm; test_at_most_three_notes_and_other_is_never_confirmed passes). MISSING: no live Gemini listen seen. The 21 Nov Kaggle `listen` step returned `heard: None`, consistent with the region gate (Kaggle sends no country)_
  - _Requirements: 2.3_
- [ ] 12. Gemini looking plus measured colours: photo to feeling words and fingerprint hints — _NOT DONE: colours to hints are tested (test_colours_and_their_hints_stay_in_range) and intake/picture answered live from the measured colours, but the Gemini look (`gemini_media.look`) was not seen working live (region gate). MISSING: one live picture read by Gemini from an allowed country_
  - _Requirements: 6.6_
- [x] 13. Open-Meteo "right now" feeling words — _Evidence: `backend/app/services/intake/moment.py` (Open-Meteo, time and weather to words); test_the_moment_is_always_plain_words passes; live: intake/moment ok in the 21 Nov Kaggle log_
  - _Requirements: 6.7_
- [x] 14. MusicBrainz and ListenBrainz lookup for named songs and artists — _Evidence: `backend/app/services/reference/metadata.py` (MusicBrainz find_recording, ListenBrainz tags, one request a second); live: references/named ok in 5 s in the 21 Nov Kaggle log. The log does not show which source supplied the 'soulful' feeling_
  - _Requirements: 6.3_
- [x] 15. Exa and Firecrawl research for the creative director (needs keys) — _Evidence: `services/reference/research.py` with monthly caps and a shared cache (`services/budget.py`, migration 011 `use_service`, `research_cache`); run with the real keys on 21 Nov: 'Feeling Good' gave feeling words (triumphant, defiant, uplifting...) for 1 Exa search and 2 Firecrawl reads, and the second ask cost nothing (service_usage exa 1, firecrawl 2). Keys set on Render 21 Nov_
  - _Requirements: 6.3_
- [ ] 16. Jamendo reference search and reference upload (in memory, never stored) — _NOT DONE: code exists (`services/reference/jamendo.py`, upload route and analysis in memory, `routers/references.py`). MISSING: the 21 Nov Kaggle run's references/jamendo step returned `tracks: []` with 'Picking from free music isn't switched on yet', so production has no Jamendo client id. JAMENDO_CLIENT_ID is set only in the local .env. Upload was not run live_
  - _Requirements: 6.1_
- [x] 17. Freesound atmosphere layer (CC0 / CC BY only, attributed; needs key) — _Evidence: `backend/app/services/sounds/freesound.py` (filter CC0 and CC BY, attribution built for CC BY); I ran `freesound.search('rain')` locally and got 6 results, so the key works. The 21 Nov production step mix/atmosphere failed plainly (no key then); not re-run on production_
  - _Requirements: 3.7_
- [x] 18. MIDI export: "Download the notes" — _Evidence: `backend/app/services/finish/notes_file.py` and `POST /finish/notes` (`routers/finish.py:121`); live: finish/notes returned a file starting `MThd` in the 21 Nov Kaggle log_
  - _Requirements: 8.3_
- [x] 19. sfizz renderer with CC0 samples for keys and strings, FluidSynth fallback — _Evidence: `backend/app/services/generation/sampled.py` (sfizz, VSCO-2 CE CC0 piano and strings, falls back to FluidSynth, `SAMPLED_INSTRUMENTS=off` switch) used from `renderer.py:87`; `backend/Dockerfile` stage 1 builds sfizz_render (local build succeeded, ~/frank-listening/sfizz_build.log). Not shown: that the Render image played them. Heard by the founder: not recorded_
  - _Requirements: 3.5_
- [x] 20. Studio plugins (Dragonfly, LSP) through pedalboard for "Add space" and the master, with fallback — _Evidence: `backend/app/services/audio/plugins.py` (Dragonfly and LSP via pedalboard, `_space` used in `mixing.py:74`, pedalboard Reverb as fallback; Dockerfile installs both packages). Live mix step ok in the 21 Nov Kaggle log; the log does not say which reverb played_
  - _Requirements: 3.6_
- [ ] 21. pgvector store for sound embeddings; taste memory matches by sound — _NOT DONE: table, match_sounds function and `services/memory/sounds.py` exist, and feel/ranked reads the table live. MISSING: no run that stored an embedding and matched it, and no test of rank_by_words_
  - _Requirements: 7.1, 2.1_

## D. Space frank-ears
- [x] 22. Space scaffold, deploy script, health endpoint (needs an HF write token) — _Evidence: `spaces/frank-ears/` (app.py, requirements, packages, README), `tools/spaces/deploy.py`, health endpoint; live: ears `health` OK in ~/frank-listening/check_all.log (Nov 21 03:02)_
- [ ] 23. CLAP audio and text embeddings; Feeling ranks directions by the user's words — _NOT DONE: embed_audio and embed_text answer live (check_all.log, 512 numbers), and `GET /feel/ranked` is built. MISSING: the 21 Nov Kaggle feel/ranked returned `ranked: []`, so ranking by the person's words has not been seen working; no test_
  - _Requirements: 2.1_
- [x] 24. Discogs-EffNet style and mood labels; Listener rule for style drift — _Evidence: `spaces/frank-ears/app.py` labels (Discogs-EffNet), live OK in check_all.log; Listener rule: `services/listener/ears.py:115` and the `style_drift` finding returned by the 21 Nov Kaggle `listen` step ('more happy than you described')_
  - _Requirements: 2.2_
- [x] 25. Audiobox Aesthetics scores in the refine loop — _Evidence: `/aesthetics` live OK in check_all.log (enjoyment 7.69 and others); used by `services/jobs/refine_runner.py:204-211`. Not seen in a recorded refine run_
  - _Requirements: 2.4_
- [ ] 26. allin1 sections and beats; Chordino chords — _NOT DONE: `/structure` (allin1) and `/chords` (Chordino) answer live in check_all.log, and chords reach references through `/describe`. MISSING: no backend code calls `/structure`; sections and beats of references still come from librosa_
  - _Requirements: 2.5_
- [ ] 27. BS-RoFormer parts for references (and stronger bleed removal) — _NOT DONE: `/separate` (BS-RoFormer) answered live once (check_ears.log, Nov 21 02:31) but failed on ZeroGPU quota in check_all.log. MISSING: `organs.separate` has no caller, so references are not split and bleed removal is unchanged_
  - _Requirements: 6.2_
- [ ] 28. PESTO contour comparison — _NOT DONE: `/pitch` (PESTO) answers live (check_all.log). MISSING: `organs.pitch` has no caller; nothing compares contours_
  - _Requirements: 2.6_
- [x] 29. GoEmotions lyric emotion arc — _Evidence: `/emotions` (GoEmotions) in the Space, called from `routers/lyrics.py:182`; live: lyrics/emotions ok in the 21 Nov Kaggle log (one calm section for a one-feeling song)_
  - _Requirements: 5.3_
- [x] 30. Matchering reference master in Finish — _Evidence: `/match_master` (Matchering) called from `services/jobs/export_runner.py:161`; live: export/match returned kind 'matched' with a waveform in 41 s in the 21 Nov Kaggle log_
  - _Requirements: 6.4_
- [x] 31. DeepFilterNet "quiet" derived take — _Evidence: `/denoise` in the Space, used by `voice_runner.py:453` as a derived take; live: voice/quiet ok in 29 s in the 21 Nov Kaggle log_
  - _Requirements: 4.3_

## E. Space frank-hands
- [x] 32. Space scaffold and deploy — _Evidence: `spaces/frank-hands/` (app.py, requirements, packages, README), same deploy script; live: hands `health` OK in check_all.log. The working copy has uncommitted edits to app.py and requirements.txt (the DDSP and Stable Audio fix)_
- [x] 33. Anticipatory Music Transformer accompaniment as notes — _Evidence: `/accompany` in the Space; live: returned notes in check_all.log (Nov 21 03:02) and `beat_runner.run_accompany_job` calls it. Not seen end to end: the 21 Nov beat/accompany step failed plainly because no hum was confirmed, which is the intended behaviour_
  - _Requirements: 3.4_
- [x] 34. DDSP: hum or take becomes an instrument — _Evidence: `/timbre` on frank-hands (`ddsp_worker.py`, own TensorFlow 2.11 env installed at start-up), called by `organs.timbre`; live 21 Nov: a 3-second hum A3-B3-C#4 came back as violin A4-B4-C#5 in 26 s (same notes, violin octave, measured with pyin)_
  - _Requirements: 4.1_
- [x] 35. DiffSinger guide vocal singing the lyrics — _Evidence: `/sing` DiffSinger in the Space (`spaces/frank-hands/diffsinger_worker.py`), `services/audio/sung_guide.py`; live: voice/guide/sung returned a sung guide in 166 s in the 21 Nov Kaggle log. Heard by the founder: not recorded_
  - _Requirements: 4.2_
- [x] 36. Kokoro: Frank reads its notes aloud — _Evidence: `/speak` Kokoro in the Space, `routers/conversation.py:86`; live: conversation/speak returned an audio address in the 21 Nov Kaggle log_
  - _Requirements: 4.5_
- [x] 37. Stable Audio 3 Small atmosphere — _Evidence: `/ambience` on frank-hands (licence accepted on the HF account 21 Nov; pytorch-lightning added, `seconds_start` conditioning); live 21 Nov via `scripts/check_spaces.py hands`: OK, 201 KB of audio in 43 s_
  - _Requirements: 3.7_
- [ ] 38. Diff-MST mix settings from a reference — _CHANGED: dropped. No public Diff-MST checkpoint exists, so there is no mix-like-the-reference prediction. Nothing was built; requirement 6.5 and design.md still name Diff-MST and need the founder's decision_
  - _Requirements: 6.5_
- [ ] 39. ACE-Step add-one-part blind test prepared under `~/frank-listening/ace-step/` — _NOT DONE: the test is prepared (`~/frank-listening/ace-step/` has README.md, make_ace.py, make_frank.py, a `pairs` plan, ANSWER_KEY) but no ACE clips exist: the ZeroGPU quota was spent. Not run, not listened to_
  - _Requirements: 3.8_

## F. Offline data (Kaggle)
- [x] 40. Groove MIDI Dataset to `grooves.json`; drums use it; ops looser and tighter — _Evidence: `services/generation/styles/grooves.json` mined by `scripts/mine_grooves.py` (Groove MIDI Dataset, CC BY 4.0); used in `composer.py:238` and `beat_runner.py:172`; looser and tighter in `generation/ops.py:58-63`; tests test_feel_never_moves_a_hit_more_than_a_third_of_a_step_and_keeps_velocity_sane, test_tighter_is_never_looser_than_natural and test_drums_stay_inside_their_bars_and_in_midi_range pass_
  - _Requirements: 3.1_
- [x] 41. Chordonomicon to `chord_tables.json`; progressions weighted by it — _Evidence: `backend/app/services/generation/styles/chord_tables.json` mined by `scripts/mine_chords.py` (Chordonomicon); `chord_tables.ranked` used in `generation/beat.py:254`. Live beat renders ran on it (21 Nov Kaggle log). No dedicated test of the weighting; the design's 'never an out-of-key chord' property is not written_
  - _Requirements: 3.2_
- [x] 42. Lakh/Slakh MIDI to `arrangement_stats.json`; layers use it — _Evidence: `backend/app/services/generation/styles/arrangement_stats.json` mined by `data/mining/lakh_arrangement/mine.py`; used by `composer._edge_layers` (intro and ending parts). Guarded by the intro-smaller-than-verse property in tests/test_properties_engine.py. Only intros and endings use it, not every layer_
  - _Requirements: 3.3_
- [x] 43. Song Describer captions calibrate words-to-fingerprint with CLAP — _Evidence: `backend/app/services/generation/styles/feeling_words.json` mined by `data/mining/song_describer/mine.py`; used by `services/intake/feeling_table.py` and `description.calibrate`; tests test_feeling_words_only_nudge_the_direction_within_range_and_never_set_speed and test_words_people_tag_differently_are_not_trusted pass. Changed from the plan: it calibrates with measured audio features of the recordings, not CLAP vectors_
  - _Requirements: 9.4_
- [x] 44. MTG-Jamendo mood check — _Evidence: `backend/app/services/generation/styles/feeling_words.json` key `mood_check` (caption words vs MTG-Jamendo mood tags on the same recordings, agreement 0.53 to 0.99 per word); used as the trust rule tested by test_words_people_tag_differently_are_not_trusted_
  - _Requirements: 9.5_

## G. Rooms
- [x] 45. Realtime job updates with polling fallback — _Evidence: `frontend/lib/api/realtime.ts` (Supabase Realtime watchJob) used by `lib/api/jobs.ts`, polling kept; vitest `pollDelay` property in tests/songShape.test.ts passes. Type-checked only: not seen live in a browser, no test of the realtime/poll merge_
  - _Requirements: 7.2_
- [x] 46. WaveSurfer waveforms with regions in Voice and Blend — _Evidence: `frontend/components/audio/Waveform.tsx` (wavesurfer.js with regions), used in `TakeCard.tsx:142` and the Blend room. Type-checked only: not seen in a browser by me_
  - _Requirements: 8.1_
- [x] 47. Tiptap lyric editor with syllable, stress and rhyme marks — _Evidence: `frontend/components/studio/LyricsEditor.tsx` (Tiptap, marks from `POST /lyrics/analyse`); vitest 'rhythm marks' property in tests/songShape.test.ts and organs.test.ts passes. Type-checked only: not seen in a browser by me_
  - _Requirements: 5.1_
- [x] 48. React Flow song family tree — _Evidence: `frontend/components/studio/SongTree.tsx` (@xyflow/react); vitest 'song family tree' properties in frontend/tests pass (13 passed). Type-checked only: not seen in a browser by me_
  - _Requirements: 8.2_
- [x] 49. Finish: notes download, credits page, reference master comparison — _Evidence: `components/studio/FinishOrgans.tsx` and `app/(studio)/[projectId]/export/page.tsx`; backend live: finish/notes, finish/credits and export/match ok in the 21 Nov Kaggle log. The screen was type-checked only_
  - _Requirements: 8.3, 6.4_
- [ ] 50. Feeling: photo, "right now", reference song, words-ranked directions — _NOT DONE: `components/studio/WorldStarts.tsx` (picture, 'Right now, where I am', named song, free music, upload) and `rankedDirections` in feel/page.tsx exist and type-check. MISSING: ranking returned empty live (task 23), Jamendo is off on production (task 16), the Gemini picture read is unproven (task 12); none of it seen in a browser (the Nov 20 screenshot docs/design-audit/after/91-production-feeling.png shows the Feeling room without these)_
  - _Requirements: 6.1, 6.6, 6.7, 2.1_
- [ ] 51. Voice: headphone check, quiet take, hum as instrument, sung guide, redo a line — _NOT DONE: HeadphoneCheck.tsx, quiet take (live ok) and sung guide (live ok) exist. MISSING: 'redo a line' (task 8) and hum as instrument (task 34, failing live)_
  - _Requirements: 8.4, 4.1, 4.2, 4.3, 4.4_
- [ ] 52. Blend: Frank listens (Gemini), mix like the reference, conduct mode (MediaPipe) — _NOT DONE: conduct mode exists (`BlendOrgans.tsx`, MediaPipe in package.json) and type-checks, but: Frank listens through Gemini is unproven live (task 11) and 'mix like the reference' was dropped with Diff-MST (task 38). Conduct mode not tried with a camera_
  - _Requirements: 2.3, 6.5, 8.5_
- [ ] 53. Music: accompaniment from the tune, atmosphere layer, looser/tighter drums — _NOT DONE: looser and tighter drums are in `Arrangement.tsx` (ops tested). MISSING: accompaniment not seen end to end from a hummed tune, and the atmosphere layer failed live on 21 Nov (no Freesound key then; works locally)_
  - _Requirements: 3.1, 3.4, 3.7_
- [x] 54. Frank speaks toggle — _Evidence: toggle in `components/conversation/ConversationPanel.tsx`, `POST` speak in `routers/conversation.py:86` (off by default); live: conversation/speak ok in the 21 Nov Kaggle log. Screen type-checked only_
  - _Requirements: 4.5_

## H. Proof
- [ ] 55. Property tests for every pure mapping in design.md "Testing", and frontend fast-check — _NOT DONE: Hypothesis `tests/test_properties_frankenstein.py` (14 tests) and fast-check `frontend/tests` (13 tests) all pass (backend suite: 504 passed, 1 skipped, 1 xfailed). MISSING from the list in design.md 'Testing': chord weighting never out of key, syllable counts positive and stable, remote fallback never raises, realtime/poll merge_
- [ ] 56. Live end-to-end run on the deployed services, recorded in `docs/demo-runs/` — _NOT DONE: a live run exists (e2e_frankenstein.py on Kaggle, ~/frank-listening/kaggle-checks-20261121-0738.log) but is not recorded in `docs/demo-runs/` (only the three 19 Nov runs are there), and it had 3 plain failures (voice/instrument, beat/accompany, mix/atmosphere) plus Jamendo off, Gemini unseen, feel/ranked empty_

## Found along the way
- [x] 57. Plain Language Auditor on `brief.py` (hook run, 21 Nov): the fingerprint (line ~202) and the beat, vocal and mix records (~210) are dumped raw into the brief with internal keys (tempo_bpm, key, effect names). Translate them to everyday words before they reach the prompt. Done in that run: references' differences pass the jargon filter, and the header bans technical sound terms. — _Evidence: `backend/app/services/song/brief.py`; test_the_brief_describes_direction_beat_vocal_and_mix_in_words in tests/test_properties_song.py passes (with tests/test_brief_wiring.py: 44 passed)_
