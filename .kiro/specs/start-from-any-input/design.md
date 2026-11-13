# Start From Any Input - Design

## Overview

An intake pipeline with one module per input type. Each module turns raw input into facet content
plus confidence, and a merge step writes facet versions (spec 01). The existing `services/generation/hum.py`
and `/feel/hum` route are superseded; the route stays for compatibility and calls the new pipeline.

```
Start surface -> POST /projects/{id}/intake  (kind: lyrics | hum | rhythm | voice_memo | text)
   lyrics     -> intake/lyrics.py   LLM (structured, validated) -> feeling, structure, fingerprint hints
   hum        -> intake/melody.py   ffmpeg->WAV -> pitch -> notes -> key, tempo -> MelodySketch
   rhythm     -> intake/rhythm.py   onset detection -> tempo -> 16-step pattern
   voice_memo -> Whisper (existing) -> text path
   text       -> intake/describe.py LLM -> intent (if none), feeling, fingerprint hints
        all   -> intake/merge.py    merge into facets with confidence rules -> facet versions
        all   -> playback preview job (melody / rhythm) -> "is this your tune?"
```

Long steps are async jobs using the existing jobs system.

## MelodySketch

```
{ notes: [{pitch_midi: int, start_beat: float, dur_beats: float}],
  tempo_bpm: float, tempo_confidence: 0..1,
  key: "C minor", mode, key_confidence: 0..1,
  grid: 0.25,           // quantisation in beats (16ths)
  source_audio: url,    // the untouched hum
  confirmed: bool }     // false until the user says "that's my tune"
```

## Melody extraction (replaces beat_track on a hum)

1. Decode with ffmpeg to mono 22.05 kHz.
2. Pitch: librosa pyin with a voiced probability; keep frames above a confidence floor.
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

Basic Pitch (neural audio-to-notes) was the fallback if this approach is not accurate enough on real
hums. Decision rule: build the pyin approach first, measure on synthetic and real hums (task 2.5); only
if note recall is below the threshold, spike Basic Pitch. Record the decision in tech.md.

## Rhythm extraction

librosa onset detection on the tapped audio, tempo from onset spacing, quantise to 16 steps over one
or two bars, return the most consistent bar as the pattern. Confidence from consistency across bars.

## Lyrics understanding

One LLM call with a strict JSON schema (Pydantic validation, one repair retry):
`{feeling: {...}, sections: [{name, line_start, line_end}], hints: {energy, density, tempo_feel, mode,
confidence}, question: str|null}`. A deterministic post-check repairs sections so they partition the
non-empty lines exactly once, in order, before anything is stored. Used by the Songwriter and Producer.

## Merge rules (intake/merge.py)

- Facets are written as new versions; originals are kept.
- Fingerprint hints are written only for fields that are unset or have lower confidence than the new value.
- Conflicts (energy or mode that disagree by more than a threshold between inputs) are NOT written;
  they are returned as `conflicts` so Frank asks the user.
- The user's explicit statements always outrank extracted values.

## Frontend

- `components/studio/StartSurface.tsx` - single text/lyrics box, "Hum it", "Tap it", "Upload a recording".
- Playback card: "Is this your tune?" with Yes / Not quite / Record again.
- Replaces the Feel Lab hum button wiring; Feel Lab still works for conversation and textures.

## Correctness properties (PBT)

1. Transposing a melody by k semitones transposes the estimated key by k (same mode) - key estimator equivariance.
2. For melodies rendered from known notes and tempo, recovered notes match within a tolerance
   (pitch within 1 semitone, onset within one grid step) at a minimum recall, across random scales and tempi.
3. Tempo estimation is stable to small amplitude changes and to leading silence.
4. Section repair always yields sections that partition the non-empty lines exactly once, in order.
5. Merge: previously set higher-confidence values are never replaced by lower-confidence ones;
   the user's explicit values are never replaced by extracted ones; merging the same input twice is idempotent.
6. Low-quality input (silence, white noise) is rejected rather than producing notes.
