# Song Engine - Requirements

## Introduction

The engine is the team's hands for music. The Nov 11 audit and the founder's listening notes showed what
it does today: it renders section blocks that are joined with hard cuts, with the same chord loop, a
melody that wanders, identical drums every bar, no fills, builds or instrument changes, no randomness,
several fingerprint fields that do nothing, and no stems. The founder's words: real songs have
different instruments in different places and a lot of work in different places; this sounds like
"basic music broken into bits".

This spec replaces the composition and arrangement logic. It does NOT choose the final sound source;
spec 05 does. The engine outputs a Score (notes, instruments, dynamics) that any renderer can play.
It traces to `frank-team.md` (Arranger, Beat-maker, Session player) and the baseline findings.

## Requirements

### Requirement 1 - A song, not a loop

**User Story:** As a user, I want music that develops like a real song.

#### Acceptance Criteria

1. THE SYSTEM SHALL build the arrangement from the song record: section names and sizes from the
   structure facet when it exists, otherwise from a style template; sections are not fixed to one shape.
2. THE SYSTEM SHALL vary the music across and within sections: different parts enter and leave, repeated
   sections differ in detail, and sections develop (a second chorus is fuller than the first).
3. THE SYSTEM SHALL create transitions between sections: fills, builds, risers, breaks, held notes, and
   tails that carry across the join, so no join is a hard cut.
4. THE SYSTEM SHALL include more than a backing loop: counter-melodies, rhythmic variation, passing chords,
   instrument changes between sections, and moments of space.

### Requirement 2 - The song's loudness shape is deliberate

#### Acceptance Criteria

1. THE SYSTEM SHALL decide section loudness from the arrangement (the chorus lifts, the bridge contrasts,
   the intro and outro sit back) and SHALL NOT normalise each section to the same peak.
2. WHEN the energy curve says one section should be bigger than another THEN THE rendered loudness
   difference SHALL follow it by at least a minimum margin.
3. THE SYSTEM SHALL normalise loudness once for the whole song.

### Requirement 3 - Harmony and melody that belong together

#### Acceptance Criteria

1. THE SYSTEM SHALL support richer harmony: seventh and added-note chords, inversions with smooth
   voice-leading, one or two chords per bar, and progression choices that depend on the mode and the feeling.
2. WHEN no melody exists THEN THE SYSTEM SHALL write one from a short repeated motif, with chord tones
   on strong beats, a clear shape, rests, and a contrast between verse and chorus.
3. WHEN a confirmed melody exists (spec 02) THEN THE SYSTEM SHALL use it as the lead and choose chords
   and a bass line that fit it.
4. THE SYSTEM SHALL keep every pitched part in the song's key unless a change is requested.

### Requirement 4 - Every field of the fingerprint matters

#### Acceptance Criteria

1. THE SYSTEM SHALL use brightness, warmth, genre proximity, instrumentation hints, tempo feel, mode and
   the groove from a tapped rhythm (spec 02), so that changing any of them changes the Score.
2. THE SYSTEM SHALL describe styles as data (instrument palettes, drum grooves, bass patterns, swing,
   chord vocabulary), not as code branches, so new styles are added without changing the engine.
3. THE SYSTEM SHALL tell the user in plain language which hints it could not honour.

### Requirement 5 - Real parts that can be changed one by one

#### Acceptance Criteria

1. THE SYSTEM SHALL keep every instrument part (drums, bass, chords, melody, atmosphere, extras) as its own
   stem for every section, and store them.
2. THE SYSTEM SHALL allow a change to one part in one section without changing other parts or sections.
3. THE SYSTEM SHALL support edits as typed operations (change how busy, swap the instrument, add a fill,
   remove a part, reseed a part, lengthen or shorten a section, reorder or repeat sections) validated before use.
4. THE SYSTEM SHALL tell the caller exactly what changed.

### Requirement 6 - Variation under control

#### Acceptance Criteria

1. THE SYSTEM SHALL make every random choice from an explicit seed saved in the plan, so the same plan
   renders the same music.
2. WHEN the user asks for "another" THEN THE SYSTEM SHALL use a new seed and produce music that is
   audibly different but still fits the fingerprint.
3. THE SYSTEM SHALL add small timing and strength variation so parts do not sound mechanical, from the same seed.

### Requirement 7 - Plan, score and render are separate

#### Acceptance Criteria

1. THE SYSTEM SHALL separate the plan (decisions and seeds), the Score (notes, instruments, dynamics) and the render (audio).
2. THE SYSTEM SHALL produce the Score as renderer-neutral data.
3. THE SYSTEM SHALL record the plan with each beat version so any version can be rebuilt or edited later.
4. THE SYSTEM SHALL provide a quick preview of a changed section without re-rendering the whole song.

### Requirement 8 - Performance and compatibility

#### Acceptance Criteria

1. THE SYSTEM SHALL render within memory limits on the deployed backend by processing one section and one part at a time.
2. THE SYSTEM SHALL keep existing beat versions playable and restorable.
3. THE SYSTEM SHALL keep working with the current renderer until spec 05 chooses a replacement.
