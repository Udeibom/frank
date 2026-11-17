# Team Conversation - Requirements (spec 07)

## Introduction
Frank is one trusted producer who consults specialists on the person's behalf (`frank-team.md`). Today each
room has one prompt, conversation history lives in the browser and is lost on reload, the Beat Room turns
replies into edits by keyword matching, and nothing checks the reply for jargon. Every room now receives the
shared song brief (song-record task 6, done Nov 17); this spec builds the team on top of it.
Traces to founder decisions 1, 2, 4, 6 and the conversation-layer steering file.

## Requirements

### Requirement 1 - One voice, the right specialists behind it
**User Story:** As a user, I want to talk to Frank and have the right expert answer.
#### Acceptance Criteria
1. THE SYSTEM SHALL route each message to one or more specialists (Songwriter, Producer, Creative Director,
   Arranger, Beat-maker, Session player, Vocal producer, Recording engineer, Mix engineer, Mastering
   engineer) based on what the message is about, not only on which room it was typed in.
2. EACH specialist SHALL have its own instructions taken from `frank-team.md` (what it owns, what it can
   hear, what it can change, when it disagrees) and SHALL only propose actions it is allowed to take.
3. THE reply SHALL always come from Frank, in one voice.
4. THE SYSTEM SHALL name a specialist only occasionally ("I asked the beat-maker"), at most once in any three
   replies, and never as a label on every message.

### Requirement 2 - Disagreement that carries information
#### Acceptance Criteria
1. WHEN two specialists propose conflicting changes (for example the Mix engineer lowers the vocal and the
   Vocal producer objects) THE SYSTEM SHALL hold one round where each states its position with the evidence
   it rests on (a Listener measurement or the person's words), and the Producer decides.
2. THE person SHALL see only Frank's summary ("I could make the music bigger, but it would cover your voice,
   so I lifted both a little").
3. THE round SHALL be bounded: one round, no loops.

### Requirement 3 - Protect the intention
#### Acceptance Criteria
1. WHEN a request fights the person's stated feeling THE Producer SHALL say so once, kindly, with a reason,
   and offer three directions; IF the person insists THE SYSTEM SHALL build what they asked.

### Requirement 4 - Creating and refining
#### Acceptance Criteria
1. WHILE the song is in "creating" THE SYSTEM SHALL not volunteer observations.
2. WHILE the song is in "refining" THE SYSTEM MAY start a reply with one observation ("I noticed something")
   when a Listener finding is "likely problem", and offer to show ways to fix it.
3. THE phase SHALL switch to "refining" by itself when the first complete draft exists (beat + vocal + mix),
   and the person can switch it at any time.

### Requirement 5 - Actions are typed and checked
#### Acceptance Criteria
1. EVERY change Frank makes SHALL come from a typed action validated against a schema; keyword matching SHALL
   be removed (song-engine task 7.3).
2. AN invalid action SHALL be repaired once (the model is told what was wrong) and otherwise dropped with a
   plain message, never executed.

### Requirement 6 - Plain language, enforced
#### Acceptance Criteria
1. EVERY reply SHALL be checked against the banned-word list (conversation-layer steering) before it is shown.
2. A reply that fails SHALL be rewritten once by the model with the offending words named; IF it still fails
   THE terms SHALL be replaced by their plain equivalents from the steering table.

### Requirement 7 - The conversation is remembered
#### Acceptance Criteria
1. THE SYSTEM SHALL store every exchange per project and room, so a reload or another device shows it.
2. AFTER 20 exchanges in a room THE SYSTEM SHALL summarise the older ones into a paragraph and keep the summary.
3. BETWEEN sessions THE SYSTEM SHALL store a summary of the song's state and key decisions in the song record
   and load it before the first reply.

### Requirement 8 - More than one model provider
#### Acceptance Criteria
1. THE SYSTEM SHALL call models through one interface with a primary provider (Groq) and a fallback.
2. WHEN the primary is rate-limited or down THE SYSTEM SHALL use the fallback without the person noticing,
   other than a slightly slower reply.
3. Every provider SHALL be free tier (tech.md principle 4).
