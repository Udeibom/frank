# Start From Any Input - Design

## Overview

An intake pipeline with one module per input type. Each module turns raw input into facet content
plus confidence, and a merge step writes facet versions (spec 01). The existing `services/generation/hum.py`
and `/feel/hum` route are superseded; the route stays for compatibility and calls the new pipeline.

```
Status (Nov 13): built = hum and lyrics. Not built = rhythm, voice memo, description (the lines
marked "planned" below). Routes are separate per kind, not one `kind` route:

```
POST /projects/{id}/intake/hum                    -> async job (jobs/intake_runner.py)  [built]
POST /projects/{id}/intake/melody/{vid}/confirm   -> makes the tune live, returns fingerprint hints [built]
POST /projects/{id}/intake/melody/{vid}/reject    -> records "not their tune", changes nothing else [built]
POST /projects/{id}/intake/lyrics                 -> synchronous LLM read (routers/intake.py)  [built]
rhythm / voice_memo / text                        -> planned (intake/rhythm.py, Whisper, intake/describe.py)

   lyrics     -> intake/lyrics.py   LLM (structured, validated) -> feeling, structure, fingerprint hints
   hum        -> intake/melody.py   ffmpeg->WAV -> pitch -> notes -> key, tempo -> MelodySketch
   all built  -> intake/merge.py    fill gaps, name conflicts (a settled value is never replaced by a later input)
   hum        -> intake/preview.py  playback render -> "is this your tune?"
```

The hum runs as an async job (one at a time). Lyrics are read inside the request.

## MelodySketch

```
{ notes: [{pitch_midi: int, start_beat: float, dur_beats: float}],
  tempo_bpm: float, tempo_confidence: 0..1,
  key: "C minor", mode, key_confidence: 0..1,
  grid: 0.25,           // quantisation in beats (16ths)
  source_audio: url,    // the untouched hum
  confirmed: bool,      // false until the user says "that's my tune"
  performed_notes: [...], // same notes at the singer's own timing; playback follows these
  fit: 0..1 }           // share of sung frames the notes explain
```

## Melody extraction (replaces beat_track on a hum)

1. Decode with ffmpeg to mono 22.05 kHz.
2. Pitch: pYIN with a voiced probability via `pyin_fast` (see Speed below); keep frames above a confidence floor.
3. Smoothing: median filter on MIDI pitch; drop isolated frames.
4. Note segmentation: a new note starts when pitch moves by at least 0.7 semitones and stays there for
   at least 80 ms, or when voicing restarts after a gap. Merge neighbours of the same rounded pitch.
5. Tempo: estimate from inter-onset intervals of the notes (histogram of IOIs folded to a likely beat
   range 60-140, pick the peak, confidence from peak sharpness). If the peak is weak, report low
   confidence and let the caller ask; do not substitute 90.
6. Quantise onsets and lengths to the 16th grid at that tempo.
7. Key: Krumhansl-Schmuckler style correlation of the duration-weighted pitch-class histogram against
   the 24 major/minor profiles; confidence from the margin between the best and the second-best key.
8. Quality gate (Requirement 3.6): reject when voiced time is below a floor, when pitch jumps
   suggest several voices, or when noise dominates; return a reason in plain language.

Speed (Nov 12): pitch tracking is librosa's pYIN with a faster decoding step (`services/intake/pitch_track.py`). It returns exactly the same pitches as `librosa.pyin` (property tests compare them, including on real hums) but runs about 10x faster, so a hum is analysed in 3 to 5 seconds instead of 30 to 55. An earlier attempt narrowed the pitch range instead; it lost notes on the fast hum and was dropped.

Playback: the melody is saved as a new facet version that is NOT active. Only `/confirm` writes a
second, confirmed version and makes it active; `/reject` writes a decision and nothing else.
Fingerprint hints (tempo, key) are returned by `/confirm` only when confidence is at least 0.6.
The Feel Lab page applies them in the browser; `merge.py` is not used on that path yet.

Basic Pitch (neural audio-to-notes) was the fallback if this approach is not accurate enough on real
hums. Decision rule: build the pyin approach first, measure on synthetic and real hums (task 2.5); only
if note recall is below the threshold, spike Basic Pitch. Record the decision in tech.md.

## Rhythm extraction

librosa onset detection on the tapped audio, tempo from onset spacing, quantise to 16 steps over one
or two bars, return the most consistent bar as the pattern. Confidence from consistency across bars.

## Lyrics understanding

One LLM call with a strict JSON shape (Pydantic validation, one repair retry that names the problem):
`{feeling: {summary, themes, imagery, emotional_arc}, sections: [{name, first_line, last_line,
feeling: sorrowful|angry|warm|mixed}], hints: {energy_level, density, tempo_feel, mode, confidence},
question: str|null}`. Lines are numbered over non-empty lines only.

Code, not the model, has the last word:
- `repair_sections` makes the sections partition the lines exactly once, in order.
- The overall mood (`mode`) is decided in code (`derive_mood`) from the per-section feelings, weighed
  by line count, because one overall guess from the model flipped between runs on the same words.
  Sorrow and anger are both "dark", so a song that moves between them is clearly dark; a dead heat
  between dark and warm gives no mood. The mood has its OWN confidence (`mode_confidence`), computed from
  the sections alone (the margin and the share of "mixed" lines), never from the model's number, which is
  about energy and pace and varied from 0.45 to 0.65 on identical words.
- Two bars (`lyrics_hints`): the mood is offered only at 0.6 or more, because it shapes the whole sound.
  Energy, busyness and pace are offered from 0.4, because they are only a soft starting point that fills
  a gap and is refined in the Feel Lab. Doubt about the mood never throws the soft hints away.
- Frank asks a question only when it cannot tell dark from warm (mood below 0.6), and then exactly one.
  Anger against sorrow is not that doubt. The question is about which feeling the music should lean into,
  uses the song's own feelings, and always offers "or should it hold both" (`allow_both`, in code): a song
  may hold all of its feelings. See `.kiro/steering/producer-craft.md` for the evidence behind this.
- If two attempts fail, structure comes from blank lines and repeated stanzas (`guess_sections`) and
  the feeling is left empty. A dropped connection is passed on as an error, not hidden by this fallback.
Written as `feeling` and `structure` facet versions, keyed by a fingerprint of the lyrics text.

## Merge rules (intake/merge.py)

- Facets are written as new versions; originals are kept.
- Built: a hint is written only into a field that is empty. A settled value is never changed.
- Built: conflicts (mode that differs, or energy at least 0.4 apart) are NOT written; they are returned
  and `conflict_question` turns the most important into ONE plain question.
- By design (Requirement 6.4, decided Nov 13): a settled value is never replaced by a later input, however
  confident. A disagreement between inputs becomes one question to the person. Because of this, values do
  not need a stored confidence; a hint is either sure enough to be offered (0.6 or more) or it is not offered.
- The user's explicit values are protected only because nothing settled is ever overwritten.

## Frontend

- Built: `components/studio/HumIntake.tsx` (record or upload, "Is this your tune?" with hear again /
  yes / not quite) used on the Feel Lab page; `ReadWordsButton.tsx` on the Idea Room page;
  client in `lib/api/intake.ts`.
- Planned, not built: `StartSurface.tsx` (one box for text, "Hum it", "Tap it", "Upload a recording",
  reachable from every room).

## Correctness properties (PBT)

1. Transposing a melody by k semitones transposes the estimated key by k (same mode) - key estimator equivariance.
2. For melodies rendered from known notes and tempo, recovered notes match within a tolerance
   (pitch within 1 semitone, onset within one grid step) at a minimum recall, across random scales and tempi.
3. Tempo estimation is stable to small amplitude changes and to leading silence.
4. Section repair always yields sections that partition the non-empty lines exactly once, in order.
5. Merge: a settled value is never replaced by any later input;
   the user's explicit values are never replaced by extracted ones; merging the same input twice is idempotent.
6. Low-quality input (silence, white noise) is rejected rather than producing notes.
