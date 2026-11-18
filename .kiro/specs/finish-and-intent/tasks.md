# Finish and Intent - Implementation Plan (spec 11)

Depends on song-engine 5.4 (stems), 03 (Listener), 08 (refine loop).

Decision (Nov 18): parts are a CACHE, not stored for every beat version. The free tier has 1 GB of storage and a
512 MB server; one beat's parts are ~28 MB. Parts are rendered one family at a time at their exact level inside
the beat (section and song gains saved with every beat since checkpoint 3) and kept only for the beat being mixed;
they are re-made exactly from the plan and seed when needed.

- [x] 1. Per-part mix model, renderer, legacy one-block path and "rebuild the parts"
  - _Requirements: 1.1, 1.4_
  - Evidence: `beat.render_parts`, `beat.families_in`, `beat_runner.ensure_parts/_parts_sync` (older beats learn
    their levels with one silent render), `mixing.render_mix(parts=...)` with level, tone, space, per-section level,
    mute; legacy beats still mix as one block until a part change asks for the parts.
    `test_the_parts_add_up_to_the_beat` (correlation > 0.99, loudness within 1 dB moment by moment).
    Found and fixed on the way: parts rendered after other parts came out different (FluidSynth applies notes on
    64-sample blocks, and its echo carried over); every render now starts on a block boundary and drains the echo.
- [x] 2. Mix conversation over parts (typed actions, max three), stem balance view with every part
  - _Requirements: 1.2, 1.3_
  - Evidence: `part_adjust` in `routers/mix.py` (MAX_CHANGES = 3), sections and parts in the mix prompt,
    `StemBalance.tsx` part rows (softer / louder / off, no sliders), `GET /finish/parts`.
- [x] 3. Finishing: full-quality source rule, two-pass loudness, true peak, Listener check, before/after
  - _Requirements: 2.1-2.3_
  - Evidence: `mastering.finish` (uncompressed render, chain, two-pass loudnorm with -1 dB peak ceiling, Listener
    loudness/clipping check, one corrective pass), export job renders the mix fresh from the mix's own sources;
    prod Nov 18: loudness -14.7, no clipping, before and after both made.
- [x] 4. Intent statement capture and the intent check before first export
  - _Requirements: 3.1-3.3_
  - Evidence: `services/finish/intent.py` (first description kept from the stored conversation), `GET/POST
    /finish/intent`; Export Room asks in their words; "Not yet" opens the Mix Room refine loop with their answer;
    export marks the song `exported`. Prod: "You said “standing alone in the rain after losing someone”…".
- [x] 5. Surprise version, once per song
  - _Requirements: 4.1, 4.2_
  - Evidence: `services/finish/surprise.py` (stripped back for a full song, a different take for a sparse one;
    never active), `POST /finish/surprise`, `/surprise/skip`; prod "Stripped right back".
- [x] 6. Download separate parts (zip) and final-listen waveform
  - _Requirements: 5.1, 5.2_
  - Evidence: `services/finish/parts_zip.py` (plain names, voice as MP3 to stay under the 50 MB upload limit),
    `components/audio/Waveform.tsx` drawn from points the export job measured; prod zip 28 MB, 300 points.
- [x] 7. Property tests and a real-audio before/after listening set
  - Evidence: `tests/test_properties_finish.py` (9 tests). The before/after listening set is made for the founder
    by the Export Room itself ("As you mixed it" / "Finished" at the same position); no separate files.
