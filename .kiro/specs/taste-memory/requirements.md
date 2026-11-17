# Taste Memory - Requirements (spec 09)

## Introduction
Founder decision 10: specialists remember the artist's taste ("you usually prefer stripped-back verses",
"you dislike cliches", "you like intimate vocals"). This is a relationship, not personalisation, and a
preference is only stated after repeated evidence.

## Requirements

### Requirement 1 - Learn from what the person does
#### Acceptance Criteria
1. THE SYSTEM SHALL record taste signals from: directions chosen and rejected (spec 08), experiments won,
   lyric options taken or refused, textures approved or skipped, measurement mismatches (spec 03 req 6), and
   things the person says about themselves ("I hate autotune").
2. EACH signal SHALL carry the specialist it concerns, the project, a plain statement, and its source.

### Requirement 2 - Only repeated evidence becomes a preference
#### Acceptance Criteria
1. A preference SHALL be stated only when supported by at least three signals across at least two songs, or
   by the person saying it directly.
2. A contradicting signal SHALL weaken a preference; two in a row SHALL retire it.

### Requirement 3 - Used gently
#### Acceptance Criteria
1. THE preferences SHALL be included in the song brief for the specialist they concern.
2. THE SYSTEM SHALL use a preference to choose the first direction to offer and may mention it ("you usually
   like the verses stripped back, so I started there"), never to refuse what the person asks.

### Requirement 4 - The person is in control
#### Acceptance Criteria
1. THE person SHALL be able to see what Frank has learned about their taste in plain words, edit any line,
   and forget any line or everything.
2. Forgotten signals SHALL be deleted, not hidden.
3. Taste belongs to the user account, not a project, and is private to them (row level security).
