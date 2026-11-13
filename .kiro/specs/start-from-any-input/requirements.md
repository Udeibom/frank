# Start From Any Input - Requirements

## Introduction

Frank must not care how a song starts. Lyrics, a hummed tune, a tapped rhythm, a voice memo or a
plain description should all lead somewhere useful, and all feed the same Song Record (spec 01).
Today the hum seeds only tempo and a loudness number, its pitch is used to write one sentence, and
lyrics never reach the music. This spec replaces that.
It traces to `frank-team.md`, the founder's feelings 1 and 2, and demo stories 1 and 2.

Scope note: the hum must be monophonic and reasonably clean (founder decision). Messy phone
recordings with several sounds or long silences are out of scope for this version.

## Requirements

### Requirement 1 - One way in

**User Story:** As a user, I want to just start with what I have.

#### Acceptance Criteria

1. THE SYSTEM SHALL offer one starting surface for a new or empty project that accepts typed text,
   pasted lyrics, a recorded or uploaded hum or voice memo, and a tapped rhythm.
2. THE SYSTEM SHALL NOT ask the user to choose a path before starting.
3. THE SYSTEM SHALL keep this surface reachable from every room, because songs can be started again from a new angle at any time.

### Requirement 2 - Lyrics shape the music

**User Story:** As a user whose song lives in its words, I want the music to start from my lyrics.

#### Acceptance Criteria

1. WHEN lyrics are provided THEN THE SYSTEM SHALL read their emotional meaning (themes, imagery,
   emotional arc, how heavy or light they are) and store it as the feeling facet.
2. THE SYSTEM SHALL detect the song's sections (verse, chorus, bridge, repeated lines) and store
   them as the structure facet, with each section tied to line numbers.
3. THE SYSTEM SHALL add confidence-marked hints to the fingerprint (energy, density, tempo feel, mode)
   derived from the feeling, and SHALL NOT overwrite fingerprint values the user already set.
4. THE SYSTEM SHALL tell the user in plain language what it understood and ask one question if
   something important is unclear.

### Requirement 3 - A hum becomes a melody

**User Story:** As a user who can hum but not write music, I want Frank to keep my tune.

#### Acceptance Criteria

1. WHEN a hum is provided THEN THE SYSTEM SHALL extract the melody as notes with pitch, timing and
   length, and store it as the melody facet.
2. THE SYSTEM SHALL estimate the key from the hum's notes and record how confident it is.
3. THE SYSTEM SHALL estimate the tempo from the timing of the notes and record how confident it is.
4. THE SYSTEM SHALL play the extracted melody back as a plain instrument and ask "is this your tune?"
5. WHEN the user says it is wrong THEN THE SYSTEM SHALL let them re-record or accept corrections, and SHALL NOT use the melody until confirmed.
6. IF the recording is too noisy, has several voices, or has too little pitched sound THEN THE SYSTEM SHALL say so kindly and suggest recording again, and SHALL NOT guess.
7. THE SYSTEM SHALL keep the original recording untouched.

### Requirement 4 - A tapped rhythm becomes a groove

**User Story:** As a user who feels a beat but can't name it, I want to tap it.

#### Acceptance Criteria

1. WHEN a tapped or spoken rhythm is provided THEN THE SYSTEM SHALL detect the hits, work out the
   tempo, and capture the pattern on a 16-step grid.
2. THE SYSTEM SHALL play the pattern back with a drum sound for confirmation before using it.
3. THE SYSTEM SHALL store the pattern as part of the fingerprint's groove, usable by the Beat Room.

### Requirement 5 - Describing a feeling in speech or text

**User Story:** As a user, I want to just say how it should feel.

#### Acceptance Criteria

1. WHEN a voice memo is provided THEN THE SYSTEM SHALL transcribe it and treat the text as a description.
2. WHEN a description is provided THEN THE SYSTEM SHALL store the user's words as the intent statement
   if none exists yet, and fill the feeling facet and fingerprint hints from it.

### Requirement 6 - Honesty and combining inputs

**User Story:** As a user, I want Frank to tell me when it isn't sure.

#### Acceptance Criteria

1. THE SYSTEM SHALL attach a confidence to every extracted value.
2. WHEN confidence is low THEN THE SYSTEM SHALL ask or play something back instead of assuming.
3. THE SYSTEM SHALL NOT fall back to a silent default (such as a fixed 90 tempo) without telling the user.
4. WHEN several inputs are given THEN THE SYSTEM SHALL merge them, keeping earlier values unless the new one is more confident or the user asked for a change.
5. WHEN two inputs conflict (for example a sad lyric and a bright hum) THEN THE SYSTEM SHALL name the tension and ask which should lead, and SHALL NOT silently pick one.
6. THE SYSTEM SHALL store every extraction as a facet version (spec 01) with the original input kept.

### Requirement 7 - Plain language

#### Acceptance Criteria

1. THE SYSTEM SHALL describe results without music terms ("a slow, rising tune that settles low"),
   and SHALL NOT show tempo numbers, key names, or note names unless the user asks.
