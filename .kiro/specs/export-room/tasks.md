# Export Room — Implementation Plan

- [x] 1. Final listen UI — _Evidence: child 1.1 ticked_
  - [x] 1.1 Load and play the active mix on entry with a warm greeting — _Evidence: frontend/app/(studio)/[projectId]/export/page.tsx loads the mix versions, picks `active_mix_id`, shows "Here's your song" with one play button over the active mix. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 1.1, 1.2_

- [ ] 2. Mastering — _open: 2.2_
  - [x] 2.1 "Make it radio ready" button — _Evidence: it is now "Finish it, ready to share" (export/page.tsx `finish`), which creates the export with mastering on (`createExport(..., true)`). Renamed by finish-and-intent spec 11. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 2.1_
  - [ ] 2.2 Async master job; auto-play result; compare before/after — _PARTLY DONE: `finish` starts the export job and polls it (export_runner.py `run_export_job`); "As you mixed it" and "Finished" buttons switch between the two at the same moment of the song. MISSING: the finished version does not start playing by itself; the player only carries on if it was already playing_
    - _Requirements: 2.2, 2.3_
  - [x] 2.3 Non-destructive; one-click "go back to the original" — _Evidence: export_runner.py makes the plain and the finished versions as separate export records and never changes the mix version; the "As you mixed it" button plays the original at once (export/page.tsx). Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 2.4, 2.5_

- [ ] 3. Download — _open: 3.2_
  - [x] 3.1 "Download" button triggers full render only if needed — _Evidence: export/page.tsx `download` only appears after `finish`; `run_export_job` reuses an existing export for the same mix version (`find_existing_export_sync`); the download step of scripts/ops/e2e.py passed on the deployed backend (build-progress Nov 18)_
    - _Requirements: 3.1, 3.3_
  - [ ] 3.2 Dedup so repeat downloads are instant — _NOT DONE as evidence: export_runner.py looks for an existing export for the mix version and returns it with `reused: True`, but no test and no walkthrough exercises that path_
    - _Requirements: 3.4, 5.4_
  - [x] 3.3 Filename sanitization; warm closing message on success — _Evidence: routers/export.py `_safe_filename` (ad-hoc check: "My Song: ../../etc/passwd!" gives my-song-etcpasswd.mp3, empty gives song.mp3; no committed test); export/page.tsx shows "It's yours. Good luck with it.". Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 3.2, 3.5_

- [x] 4. Export history — _Evidence: child 4.1 ticked_
  - [x] 4.1 List past exports (date + source mix version), re-download links — _Evidence: `GET /export` (routers/export.py list_exports returns created_at and mix_version_id); export/page.tsx "Past downloads" list with a download button each. Screen type-checks (tsc --noEmit passes Nov 18); not seen in a browser by me_
    - _Requirements: 4.1, 4.2, 4.3_

- [ ] 5. Backend: mastering pipeline — _open: 5.2_
  - [x] 5.1 `services/audio/mastering.py` pedalboard chain (multiband comp, limiter, loudnorm -14 LUFS) — _Evidence: mastering.py `_master_chain`, TARGET_LUFS = -14.0; tests/test_properties_mastering.py (9 passed Nov 18: test_loudness_lands_on_target, test_peaks_stay_under_ceiling); test_finishing_reaches_streaming_loudness_without_clipping (test_properties_finish.py, 10 passed); production finish: loudness -14.7, no clipping (build-progress Nov 18)_
    - _Requirements: 6.1_
  - [ ] 5.2 WAV → MP3 320k via FFmpeg; store in private exports/ bucket — _PARTLY DONE: 320 kbps MP3 is tested (test_output_is_decodable_320kbps_stereo_mp3) and uploaded to the "exports" bucket (`upload_audio_with_path`). MISSING: nothing checks the bucket is private; the code falls back to a public URL when no path is stored (routers/export.py)_
    - _Requirements: 6.1, 6.2_

- [ ] 6. Backend: export routes — _open: 6.3_
  - [x] 6.1 All three endpoints (export, list, download) — _Evidence: routers/export.py `create_export`, `list_exports`, `get_download_url`; the export and download steps of scripts/ops/e2e.py passed on the deployed backend (build-progress Nov 18); not re-run by me_
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 6.2 Signed URL generation for download — _Evidence: routers/export.py `get_download_url` calls storage.files `create_signed_url` from the stored path; used by the production walkthrough's download step; no committed test_
    - _Requirements: 5.3_
  - [ ] 6.3 Export records with mix_version_id + mastered; dedup lookup — _PARTLY DONE: export_db `create_export_sync` stores `mix_version_id` and `mastered` and the list route returns them; the dedup lookup (`find_existing_export_sync`) exists but is untested (see 3.2)_
    - _Requirements: 4.1, 5.4_

- [ ] 7. Deferred follow-ups (tracked) — _open: 7.1_
  - [ ] 7.1 Waveform on the final-listen screen — _PARTLY DONE: components/audio/Waveform.tsx with `waveform()` in export_runner.py (test_the_waveform_is_a_short_shape_between_zero_and_one) is shown, but only after "Finish it" (`{finished && <Waveform .../>}`); the first listen at the top of the screen still has only the play button. Not seen in a browser by me_
    - _Requirements: 1.2_
  - [x] 7.2 Two-pass loudnorm; true-320k from un-encoded source — _Evidence: mastering.py `measure_loudness` then `encode_finished` (second pass with the measured values, one corrective retry) fed by `render_array`, the uncompressed mix, in export_runner; test_finishing_reaches_streaming_loudness_without_clipping passes; production loudness -14.7 (build-progress Nov 18)_
    - _Requirements: 6.1_
