# Core Path — Tasks (spec 15)

Ticked only with evidence. Order agreed with the founder (23 Nov): steps 1 to 7.

## Step 1. Nothing crashes
- [x] 1. Migration 012: job payload, claim, heartbeats, `job-inputs` bucket — _Evidence: migration 012 applied live (`payload`, `claim_job`, `worker_heartbeats`, `job-inputs`); tested: claim on an empty queue returns nothing_
  - _Requirements: 1.2, 1.4_
- [x] 2. `dispatch.py`; every router uses it (bytes staged in storage) — _Evidence: `services/jobs/dispatch.py`; all 26 router call sites use `dispatch.start`; route tests 182 passed; live run: every job queued and claimed (docs/demo-runs/2026-11-23-core-path.md)_
  - _Requirements: 1.1, 1.3_
- [x] 3. Worker on the frank-ears Space (own env, system libraries, assets, secrets); memory limit measured — _Evidence: `app/worker.py`, `spaces/frank-ears/worker_setup.sh` (Python 3.12, sfizz, Dragonfly, SoundFont, samples); heartbeat reports a 99,182 MB limit; live run: all jobs `claimed_by = ears-worker`, peak 1,272 MB_
  - _Requirements: 1.1_
- [x] 4. Restart sweep and stale check respect claimed jobs — _Evidence: `db/jobs.fail_jobs_active_before` skips queued and worker jobs; worker ends only its own orphans; `QUEUED_STALE_AFTER` with test_a_job_waiting_in_the_queue_is_only_given_up_on_after_the_longer_limit_
  - _Requirements: 1.4_
- [x] 5. Queue position shown to the person — _Evidence: `waiting` in `/jobs/{id}/status` (routers/jobs.py `_waiting_line`); live run printed it for every job_
  - _Requirements: 1.2_

## Step 2. Speed
- [x] 6. Hum speed: no double or half reading; consistent hums win; feeling decides between candidates — _Evidence: `services/intake/pace.py`, used on confirm (routers/intake.py `_counted_for_the_song`); tests test_the_founders_worship_hum_is_counted_at_a_gentle_speed and test_recounting_a_tune_never_changes_how_it_sounds; live: hum read at 138 became 69. Changed from design: the confirmed hum decides, counted to fit the feeling, rather than voting across hums_
  - _Requirements: 2.1_
- [x] 7. `slower` / `faster` operations that change the beat's speed — _Evidence: `ops.apply_speed` (`slower`, `faster`) in `beat_runner.run_operations_job`, speed kept in the feeling; test_slower_and_faster_change_the_speed_the_way_they_say; live: 69 -> 61_
  - _Requirements: 2.2_
- [x] 8. Reply claim check: Frank never says it did what it didn't — _Evidence: `services/team/claims.py` in the beat chat; test_the_founders_speed_requests_become_a_real_slower_change, test_a_reply_never_claims_speed_when_nothing_changes_speed; live: 'too fast' produced `slower`_
  - _Requirements: 2.3_

## Step 3. Length
- [x] 9. New beat at least as long as the recording; mix never leaves the voice alone — _Evidence: `beat.fit_arrangement`, `beat.extend_sections`, `beat_runner.lengthen_to_voice` before every mix; tests test_a_new_beat_is_at_least_as_long_as_the_singing, test_lengthening_a_beat_keeps_every_section_it_had; live: 240 s voice, 269 s music_
  - _Requirements: 3.1, 3.2_

## Step 4. Directions
- [x] 10. "Try something different" moves the sound on purpose; no stored copy of a heard direction — _Evidence: `texture.PALETTES`, `contrast`, `wants_different`; Feel chat applies it; cache key uses the sound family; tests test_a_different_direction_changes_sound_energy_and_movement_and_is_never_the_stored_copy, test_asking_for_different_again_and_again_goes_through_every_sound_before_repeating; local render brightness 1315 vs 3145; live: not cached, new family_
  - _Requirements: 4.1_

## Step 5. Words and next step
- [x] 11. One next step per room; plain labels in Voice and Blend — _Evidence: `lib/nextStep.ts` + `components/shell/NextStepBar.tsx` in every room (vitest tests/nextStep.test.ts); 'Recording' labels (`lib/recordingName.ts`, routers/voice.py), 'Change this recording…' explained, best-of only with two recordings, Blend main choices; plain-language check 0 findings. Type-checked and built; not seen in a browser by me_
  - _Requirements: 5.1, 5.2_

## Step 6. Honest status
- [x] 12. Waking banner clears when the server answers — _Evidence: `components/studio/WakingUp.tsx` (8 s check timeout; clears on any answer below 500 via `SERVER_ANSWERED` in lib/api/client.ts). Type-checked and built; not seen in a browser by me_
  - _Requirements: 6.1_
- [x] 13. Reactions are never saved as the song's description — _Evidence: `finish/intent.REACTION`; test_the_founders_reactions_are_not_the_songs_description, test_real_descriptions_are_still_kept; live: the reaction was not kept_
  - _Requirements: 6.2_

## Step 7. Proof
- [x] 14. Live run of the founder's path, recorded in `docs/demo-runs/` — _Evidence: docs/demo-runs/2026-11-23-core-path.md: 16 of 16 PASS on production, 395 s_
  - _Requirements: 7.1_
