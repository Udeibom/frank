# Listener - Requirements

## Introduction

A producer can say "the chorus isn't lifting" because they can hear it. Frank's specialists can't hear
anything today: the only analysis is a rough whole-mix check on the first 10 seconds. The Listener is
the team's ears. It measures the real audio, reports plain facts with evidence, and never changes
anything. Every diagnosis a specialist gives must cite a Listener measurement or say it has none.
It traces to `frank-team.md` (Listener role, decisions 5 and 7) and demo story 3.

The Listener reports. It does not judge taste. The user's feeling always outranks a measurement (decision 5).

## Requirements

### Requirement 1 - Measure the song, not just the mix

**User Story:** As a user who says "something feels off", I want Frank to actually check the sound.

#### Acceptance Criteria

1. THE SYSTEM SHALL measure, for the active beat, per section and per part (when parts are available):
   loudness, how many parts play, how busy the notes are, brightness of the sound, and how much it
   changes from the previous section.
2. THE SYSTEM SHALL measure, for the active vocal, loudness, how steadily it is sung in tune against the
   song's notes, timing against the beat, and background noise.
3. THE SYSTEM SHALL measure, for the whole mix, loudness against the vocal, how much the vocal and
   the beat compete in the same range, peaks, and overall loudness.
4. THE SYSTEM SHALL measure repetition: how similar sections of the same name are in sound and in melody,
   and how similar the chorus is to the verse.
5. THE SYSTEM SHALL measure the melody: range, how much it moves, and how many of its strong notes fit the chords.

### Requirement 2 - Findings are evidence-backed and plain

**User Story:** As a user, I want to know what was found without being shown numbers.

#### Acceptance Criteria

1. THE SYSTEM SHALL produce a report of findings, each with: a plain-language statement, a severity
   (note, worth a look, likely problem), the measurement ids it rests on, and which sections or parts it concerns.
2. THE SYSTEM SHALL NOT include music jargon or raw units in the plain-language statement.
3. THE SYSTEM SHALL make raw measurements available to specialists separately from the statements.
4. WHEN a finding compares two things THE SYSTEM SHALL state the comparison ("the chorus plays at almost the
   same strength as the verse").

### Requirement 3 - Honest about what it cannot tell

**User Story:** As a user, I want Frank to say when it does not know.

#### Acceptance Criteria

1. WHEN the audio is missing, silent, or too short to measure THEN THE SYSTEM SHALL say what could not be
   measured instead of returning zero or guessing.
2. WHEN no finding explains a complaint THEN THE SYSTEM SHALL return "no clear cause found" so the
   specialists can propose an experiment (spec 08), and SHALL NOT invent a cause.
3. THE SYSTEM SHALL attach a confidence to each finding.

### Requirement 4 - Reports only; never changes

#### Acceptance Criteria

1. THE SYSTEM SHALL NOT modify any version, file, or active pointer.
2. THE SYSTEM SHALL be callable by any specialist and by Kiro tooling through the same functions.

### Requirement 5 - Fast enough to use in a conversation

#### Acceptance Criteria

1. THE SYSTEM SHALL cache measurements by the id of the audio version, so the same version is never measured twice.
2. THE SYSTEM SHALL measure a full song in a background job and show progress ("Listening closely...").
3. THE SYSTEM SHALL measure only the parts relevant to a question when asked (for example only the chorus).
4. THE SYSTEM SHALL keep memory use low enough to run on the deployed backend (process in chunks, release buffers).

### Requirement 6 - The user's feeling is recorded alongside

#### Acceptance Criteria

1. WHEN the user says a measured thing still does not feel right THEN THE SYSTEM SHALL record the
   mismatch (what was measured, what the user said) as a taste signal for spec 09, and SHALL NOT argue.
