# Song Record — Requirements

## Introduction

Every room today keeps its own state, so no part of Frank sees the whole song (the Voice Room's
LLM knows only how many takes exist; chat history lives in the browser and disappears on reload).
The Song Record is one living record of a song that any starting point can fill and every room and
specialist reads. It is what turns separate rooms into one team that knows the song.
It traces to `frank-team.md` ("The song"), `project-layer.md`, and founder decisions 2, 5, 8.

The record does not replace existing tables (lyrics, fingerprints, beats, takes, mixes). It adds the
missing facets, ties everything together, and provides one brief builder that all LLM calls use.

## Requirements

### Requirement 1 - One record, any starting point

**User Story:** As a user, I want to begin with whatever I have, so that I never have to choose a path.

#### Acceptance Criteria

1. THE SYSTEM SHALL hold, for each project, a song record with these facets: intent, feeling,
   melody, structure, references, identity brief, plus links to the active lyrics, fingerprint,
   beat, vocal, and mix that already exist.
2. THE SYSTEM SHALL allow any facet to be filled first, in any order, and SHALL NOT require any
   facet before another.
3. WHEN a facet is empty THE SYSTEM SHALL report it as empty rather than inventing a default.

### Requirement 2 - Intent is kept in the user's words

**User Story:** As a user, I want Frank to remember exactly what I said I wanted, so that "finished" means
my intent is met.

#### Acceptance Criteria

1. THE SYSTEM SHALL store the intent statement verbatim as the user wrote or said it.
2. THE SYSTEM SHALL only change the intent statement when the user changes it.
3. THE SYSTEM SHALL make the intent available to every specialist call.

### Requirement 3 - Versions with lineage; nothing overwritten

**User Story:** As a user, I want to go back, compare, and branch, so that I never lose a version I liked.

#### Acceptance Criteria

1. WHEN any facet changes THEN THE SYSTEM SHALL create a new version holding the new content, its
   parent version, the operation that made it, its parameters, who made it (user or a named
   specialist), and when.
2. THE SYSTEM SHALL never modify or delete a stored version.
3. THE SYSTEM SHALL let the user restore any earlier version of a facet, which creates a new
   version whose parent is the restored one.
4. THE SYSTEM SHALL let the user branch from any version; each branch keeps its own lineage.
5. THE SYSTEM SHALL keep a facet's active pointer separate from its versions, so switching the active
   version needs no re-processing.

### Requirement 4 - Decisions are remembered with reasons

**User Story:** As a user, I want Frank to remember what we decided and why, so that it stops suggesting what I rejected.

#### Acceptance Criteria

1. WHEN the user chooses between options, or rejects one, THEN THE SYSTEM SHALL record the decision:
   what was proposed, by whom, the options offered, the evidence cited, the choice, and the user's reaction.
2. THE SYSTEM SHALL keep rejected options so they are not offered again unchanged.
3. THE SYSTEM SHALL make recent decisions available to every specialist call.

### Requirement 5 - Creating and refining phases

**User Story:** As a user, I want Frank to leave me alone while I create and help when I review.

#### Acceptance Criteria

1. THE SYSTEM SHALL start every project in the creating phase.
2. WHEN a first complete draft exists (a beat and a vocal or melody, both playable) THEN THE SYSTEM
   SHALL offer to move the project to the refining phase, and SHALL NOT switch without the user.
3. THE SYSTEM SHALL let the user move between phases at any time.
4. THE SYSTEM SHALL expose the phase to every specialist call.

### Requirement 6 - One brief for every conversation

**User Story:** As a user, I want every part of Frank to know my whole song, so that I never repeat myself.

#### Acceptance Criteria

1. THE SYSTEM SHALL build one song brief from the record and provide it to every LLM call, in every room.
2. THE SYSTEM SHALL keep the brief within a fixed size, always keeping the intent, the active
   facets, and the most recent decisions, and trimming older material first.
3. THE SYSTEM SHALL produce the same brief for the same record.
4. THE SYSTEM SHALL allow a specialist-specific view (for example the Mix Engineer sees levels in
   more detail) without changing the underlying record.

### Requirement 7 - Persistence and plain language

**User Story:** As a user, I want to come back tomorrow and find my song as I left it.

#### Acceptance Criteria

1. THE SYSTEM SHALL persist the record on the server so a reload or a new device shows the same state.
2. THE SYSTEM SHALL NOT show raw record fields to the user; the interface describes them in plain language.
3. THE SYSTEM SHALL keep existing projects working; projects made before this spec load with empty new facets.
