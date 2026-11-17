# Sing It - Design (spec 06)

## Overview
All processing stays on the backend (audio-architecture rule 1). The browser plays the beat and the guide,
records the microphone, and uploads. New code:

| File | Job |
|---|---|
| `services/audio/guide.py` | Render the guide: the melody (Lead or engine melody) on GM 54 at -12 dB under the beat, per section, MP3 |
| `services/audio/song_notes.py` | `target_at(t) -> (scale_pcs, melody_note or None, chord_pcs)` from the active beat plan + lead |
| `services/audio/pitch.py` (changed) | `correct_pitch(wav, mode, targets)`: per-segment shift toward the song target; keeps intra-note movement |
| `services/audio/align.py` | Device delay from a click check; whole-take shift; per-phrase tighten via onset vs beat grid |
| `services/audio/bleed.py` | Beat removal: align beat to take (cross-correlation), estimate a per-band transfer (STFT least squares over voiced-free frames), soft mask subtraction |
| `services/audio/phrases.py` | Phrase split on voicing gaps > 250 ms, mapped to sections by time |
| `services/audio/comp.py` (changed) | Phrase-based scoring and selection; swap endpoint |
| `services/audio/harmony.py` (changed) | Per-note interval from the chord at that time |
| `services/audio/engineer.py` | After-take checks using Listener dsp functions; returns one plain message or none |

## Song targets
`song_notes.target_at` uses `beat.plan_contexts` (already deterministic from a stored beat version) to know the
chord and the melody note at any second: `section_spans` gives section times, bars give chord indices, the
melody part gives the note. No new storage: it is recomputed from the active beat version's params.

## Tuning algorithm
1. pyin contour (existing settings). 2. Segment voiced frames into notes (existing `_snap_to_grid` walk).
3. Per note: centre = median pitch of its middle 60%. Target = melody note if |centre - melody| <= 2 semitones,
else nearest scale note. 4. Error = target - centre; apply mode threshold and strength. 5. Rubber Band shift of
the segment by `strength * error` (constant per note, so vibrato inside the note survives); "Lock it in" also
flattens the contour by shifting in short sub-segments. 6. Crossfaded splice (existing).

## Delay check
The browser plays four clicks at a known time and records; the backend finds the click onsets and the median
offset. Stored per user in `user_settings(user_id, input_delay_ms)` (new table). Applied on upload.

## Bleed removal
Inputs: take (mono, 44.1 kHz) and the exact beat render the take was recorded against (`beat_version_id` and
start offset are sent with the upload). Steps: cross-correlate to align (sub-frame), STFT both (2048/512),
estimate per-bin gain H from frames where the voice is unvoiced (pyin), residual = take - H*beat, then a soft
mask (Wiener-style) floor 0.1 to avoid "underwater" sound. Accept only if the Listener measures beat-band
correlation drop >= 6 units and the voice loudness drop < 2 units; otherwise keep the original and say so.

## Comp
Phrases are found on the first take and matched across takes by time (all takes are aligned to the beat, so
the same phrase sits at the same time). Score = 0.4 tuning share (Listener in-tune vs song notes) + 0.25 timing
+ 0.2 clarity + 0.15 steadiness. Stored in the existing `vocal_comps.segments` with `take_id` per phrase.
`POST /voice/comp/{id}/swap {phrase_index, take_id}` creates a NEW comp version.

## Harmony
For each note segment: chord pcs at its time; harmony note = nearest chord tone strictly above (or below) the
target note; shift = harmony - centre. Sections filter: segments outside the chosen sections are silent.
Schema: `vocal_takes.is_harmony boolean default false` (additive migration), backfilled from label prefix.

## API (all under `/projects/{id}/voice`)
`GET /guide?section=` (job, returns MP3 URL) · `POST /delay-check` (upload) · `POST /takes` gains
`beat_version_id`, `beat_offset_s`, `headphones` · `POST /takes/{id}/align` · `POST /takes/{id}/remove-bleed`
· `POST /takes/{id}/correct` (now song-aware) · `POST /comp` (phrase comp) · `POST /comp/{id}/swap`
· `POST /harmony {take_id, type, sections}` · `POST /takes/{id}/use-as-melody`.

## Frontend
Voice Room gains: guide toggle + level, section picker for practice loop, count-in, delay check (one-time
card), per-take chips ("lined up", "beat taken out"), comp view with per-phrase take picker, harmony section
picker. Plain words only ("Sing along with the tune", "Line it up with the beat", "Take the music out of my
vocal").

## Properties (PBT)
1. Tuning never moves a note already within the mode's threshold of its target. 2. Tuning moves every note
toward its target (distance after <= before). 3. Alignment of a take delayed by d returns within one frame of
d. 4. Bleed removal on take = voice + g*beat reduces the beat part and keeps the voice part within 2 units.
5. Comp segments tile the comp without gaps or overlaps (existing property, now per phrase). 6. Every harmony
note is a chord tone. 7. Originals never change (hash before/after).
