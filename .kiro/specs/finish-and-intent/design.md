# Finish and Intent - Design (spec 11)

## Parts in the mix
Song-engine 5.4 stores, per beat version, one MP3 per part for the whole song (`beat_stems` rows with
`type = part name`, `section = 'all'`), rendered in the same pass as the full beat (the renderer already makes
each part's audio; today it is summed and thrown away). Memory: parts are encoded and released one at a time.
Mix params become `{parts: {name: {level_db, tone, space, sections: {i: level_db}}}, vocal: {...}, harmony: {...}}`.
`render_mix` sums decoded parts with pedalboard chains per part. Legacy beats: `parts` absent -> current blob path;
"rebuild the parts" re-renders from the stored plan + seed (deterministic, so it sounds the same).

## Finishing chain
Full-quality mix render (WAV in memory) -> gentle glue compression -> limiter at -1 dBTP -> FFmpeg `loudnorm`
two-pass to -14 LUFS integrated -> MP3 320k from the WAV. Listener checks clipping share and loudness after;
if loudness misses by > 1 unit or clipping is found, one corrective pass, else report honestly.

## Intent
`intent` facet already exists. Captured from the person's first description in any room (router flags
`is_intent_statement`), editable. Export Room: before the first export, a card plays the mix and shows their
words with "Yes, that's it" / "Not yet". "Not yet" opens the conversation with the refine loop.

## Surprise
After the first export or the intent "yes": a job builds one variant (choose from: stripped-down (keys + vocal),
half-time feel, brighter colour), labelled "Frank's idea", not active. A flag `surprise_offered` on the project.

## Separate parts
`GET /export/{id}/parts.zip` streams a zip of the stored part MP3s plus vocal and harmony.
