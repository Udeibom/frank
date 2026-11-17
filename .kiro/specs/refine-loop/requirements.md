# Refine Loop - Requirements (spec 08)

## Introduction
North-star scenario 3 and demo story 3: "Something feels wrong." Frank measures, explains with evidence, offers
two or three directions the person can HEAR before choosing, and commits the one they pick. When nobody can
tell what is wrong, Frank says so and proposes an experiment. Every version is kept; the person can branch and
ask for an earlier version back in their own words.
Traces to founder decisions 1, 5, 7 and `frank-team.md` "How a request flows".

## Requirements

### Requirement 1 - Diagnose with evidence
#### Acceptance Criteria
1. WHEN the person describes a problem THE SYSTEM SHALL ask the Listener (spec 03) about the relevant sections
   and base the diagnosis only on findings it returned, stating the comparison in plain words.
2. WHEN the Listener returns no clear cause THE SYSTEM SHALL say it cannot tell yet and go to requirement 4.
3. WHEN the person disagrees with a measurement THE SYSTEM SHALL side with the person, ask what the word means
   to them ("bigger" as louder, fuller, or higher), and record the mismatch (Listener requirement 6, spec 09).

### Requirement 2 - Directions, not one answer
#### Acceptance Criteria
1. THE SYSTEM SHALL offer two or three directions, each a short plain description tied to a set of typed
   actions (spec 07), each changing different things.
2. EACH direction SHALL be previewable: a short render of the affected section (or the whole song if the change
   is global), playable from the conversation, without changing any saved version or active pointer.
3. Previews SHALL be ready within 60 seconds for a section on the deployed backend, with a progress message.
4. THE person SHALL be able to compare a preview with the current version at the same position (A/B).

### Requirement 3 - Commit what was chosen
#### Acceptance Criteria
1. WHEN the person picks a direction THE SYSTEM SHALL apply its actions as a new version (beat, vocal or mix),
   make it active, and record a decision with the options, the evidence, and the choice.
2. THE SYSTEM SHALL ask how it feels afterwards, and keep the other directions available to try.

### Requirement 4 - Experiments when nobody knows
#### Acceptance Criteria
1. WHEN no cause is found THE SYSTEM SHALL build two or three versions that differ in exactly one thing each
   (for example: fewer parts in the verse; a higher chorus tune; a slower song), say what each changes, and
   let the person's ears decide.
2. THE outcome SHALL be recorded as evidence for taste memory (spec 09).

### Requirement 5 - Branches and going back
#### Acceptance Criteria
1. THE person SHALL be able to go back to any earlier version of the beat, vocal or mix and continue from it;
   the later versions stay (a branch, not a delete).
2. THE SYSTEM SHALL understand plain references to versions: "give me the second version back", "the one before I
   changed the chorus", "the version from yesterday", resolved against version labels, order, dates and the
   decisions log; IF ambiguous it SHALL play the two candidates and ask.
3. THE studio SHALL show the versions as a simple history per layer, with labels the person can rename.
