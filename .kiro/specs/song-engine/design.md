# Song Engine - Design

## Overview

Three layers with narrow contracts, so the sound source can change (spec 05) without touching the music logic:

```
Song record (spec 01) + fingerprint + melody/groove/structure
        |
   Planner  ->  Plan   (sections, energy curve, which parts, style, seeds)
        |
   Composer ->  Score  (notes per part per section, instruments, dynamics)   <- renderer-neutral
        |
   Renderer ->  audio  (per part, per section; FluidSynth now, spec 05 decides what next)
        |
   Assembler -> stems + full mix with one song-level loudness pass
```

Everything in Plan and Score is data. Rendering is a pure function of the Score and the renderer settings.

## Plan

```
Plan { seed, style: StyleProfile, key, mode, tempo_bpm, energy_curve: [per-section 0..1],
       sections: [{name, bars, parts: [PartPlan]}] }
PartPlan { part: drums|bass|chords|melody|pad|extra, pattern_id, busy: 0..1, instrument_id, seed, fx }
```

The Planner:
1. Takes sections and sizes from the structure facet (lines to bars: roughly 2 bars per lyric line, rounded
   to 4 or 8); otherwise from the style template.
2. Builds an energy curve over the whole song from the feeling and the arrangement role of each section
   (intro low, verse mid, pre-chorus rising, chorus high, bridge contrast, final chorus highest, outro down).
3. Chooses parts per section from the style's palette, adding a part on each repeat of a chorus and
   rotating colour parts (strings, a plucked line, a pad) so repeats are not copies.
4. Assigns a seed per part per section, derived from the plan seed and stable ids, so editing one part
   does not move the seeds of the others.

## StyleProfile (data, not code)

Stored as JSON in `backend/app/services/generation/styles/*.json`. Fields: instrument palettes by warmth and
brightness, drum groove templates, bass pattern families, swing and humanise amounts, chord vocabulary
(triads, sevenths, suspended), progression families per mode, typical arrangement shapes, fill types.
The Planner picks and blends profiles from `genre_proximity` (several allowed), `warmth`, `brightness`,
`tempo_feel`. Unknown hints are reported back (Requirement 4.3), not ignored.
Initial set: soul/r&b, pop, lo-fi, rock, ambient, acoustic/folk, hip-hop/trap, gospel/worship, electronic.

## Composer

Each part is a function `(plan_part, harmony, seed) -> NoteEvents`.
- Harmony: progressions come from the style and mode; chords can be 7ths/added notes; voice-leading picks the
  inversion with the smallest movement; harmonic rhythm of 1 or 2 chords per bar from the busy value.
- When a confirmed melody exists: `harmonize(melody, key)` scores candidate chords per bar by how many
  melody notes they contain and by how well they follow each other, and picks the best path (Viterbi over bars).
- Melody (when absent): a motif of 3-5 notes built on chord tones, repeated and varied (sequence, inversion,
  rhythm change), phrased in 2 or 4 bar shapes with rests, ending phrases on chord tones. Chorus melody sits
  higher than verse melody.
- Bass: patterns from the style (root-fifth, walking, syncopated, sustained), approach notes into chord changes.
- Drums: groove templates with seeded variation; a fill on the last bar before sections with higher energy;
  crash on a chorus start; breakdown (drums out) before a drop; hat patterns by busy value.
- Extras: counter-melody in verses, arpeggios, string swells, risers (noise sweep in renderer), reverse-tail
  effects as Score events with instrument ids.
- Humanise: seeded timing offsets (a few ms) and velocity variation; larger for acoustic styles.
- Transitions: a Score event type `transition` (fill, riser, break, tail) placed on the bars before and
  across a join.

### Key and tempo when a tune exists
- The song's key follows a settled fingerprint key unless the tune clearly does not fit it: when the scale fit
  of the tune in the settled key is worse than in the hum's key by more than 5 points (0.05), the hum's key is
  used and the fingerprint gets `key_from_tune` (`lead.choose_key`, `beat_runner._fingerprint_and_lead`).
  With no settled key, the hum's key is used.
- Tempo is filled from the hum only when the fingerprint has none (and the hum's tempo confidence is high enough).
  A settled tempo is never replaced (spec 02 requirement 6.4).
- The tune plays in choruses only (`LEAD_SECTIONS`), is rounded up to 1, 2, 4, 8 or 16 bars and cut beyond 16.
  A chorus is extended to the tune's length. Known limits: see tasks 4.8-4.12.

## Dynamics and loudness

- The Score carries per-section and per-part gain. The Assembler applies them, then runs ONE loudness
  normalisation over the whole song. No per-section peak normalisation.
- A check at assembly: if the rendered chorus-vs-verse loudness gap is below the plan's margin, raise the
  chorus gain (bounded) and record that it did.

## Stems and storage

- Render per part per section to a buffer, write each part's full-length stem as MP3 (and keep the section mix
  for fast playback), store in Supabase, and list them in `beat_stems`.
- `beat_versions.params` holds the Plan (with seeds). The Score is rebuilt from the Plan; it is also
  cached because composing is cheap but not free.
- Editing: `apply_operation(plan, op) -> plan'` where op is a typed, validated model:
  `set_busy`, `swap_instrument`, `add_fill`, `remove_part`, `add_part`, `reseed`, `resize_section`,
  `reorder_sections`, `repeat_section`, `change_style_blend`. The caller then re-composes and re-renders only
  the parts and sections that changed.
- The current keyword-substring editor (`apply_section_instruction`) is replaced; the Beat Room LLM emits
  the typed operations. Old versions stay playable.
- Quick preview: render only the changed section plus one bar of lead-in and lead-out to a temporary file.

## Renderer contract

`render_part(score_part, renderer_settings) -> audio`. The FluidSynth renderer stays and is cleaned up
(per-part reverb/chorus controls, correct note-off ordering at equal sample times). Spec 05 adds other renderers
behind the same contract.

## Migration

Existing beat versions have no Plan. They load as "legacy" (playable, restorable, editable only by regenerating).
New versions always have a Plan. `beat_stems` is extended, not replaced.

## Correctness properties (PBT)

1. Determinism: same Plan and settings give identical Scores (and identical audio on the same renderer).
2. Variation: different plan seeds give different Scores, with a minimum share of differing notes, for the same fingerprint.
3. Key safety: every pitched note is in the key's scale (or an allowed passing tone), for random keys, modes and styles.
4. Strong-beat harmony: the share of melody notes on strong beats that are chord tones is above a threshold.
5. Dynamics: for any fingerprint, the rendered/planned chorus gain exceeds the verse gain by at least the margin.
6. No dead fields: changing warmth, brightness, a genre hint, or instrumentation hints changes the Score (or is reported as unsupported).
7. Locality: an operation on one part of one section leaves all other parts and sections' Score unchanged.
8. Density monotonicity: raising `busy` never lowers the note count of that part.
9. Structure: section bars sum to the song length; no overlapping or negative note timing; no note past its section end except declared tails.
10. Stem sum: the sum of stems equals the full mix within tolerance.
