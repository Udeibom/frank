# Sing It - Requirements (spec 06)

## Introduction
The person sings their own song. Today the Voice Room records takes, shows a pitch line, tunes to the
nearest of all twelve notes (not the song's notes), builds a comp from two-second windows, and adds a
harmony at one fixed distance for the whole take. Nothing helps the person know what to sing, nothing lines
the take up with the beat, and recording without headphones leaves the beat inside the vocal.
This spec makes the Voice Room a real vocal session: a guide to sing along with, tuning to the song's own
notes, timing lined up with the beat, beat bleed removed, a comp built phrase by phrase, a harmony that
follows the chords, and a recording engineer who catches problems before the next take.
Traces to `frank-team.md` (Vocal producer, Recording engineer), demo story 1 (the grandmother song), and the
baseline finding "vocal never aligned to the beat; tuning ignores the song's key; harmony is a fixed interval".
Replaces voice-room requirement 5.3 (chromatic snapping) and 7 (fixed-interval harmony) where they overlap.

## Requirements

### Requirement 1 - A guide to sing along with
**User Story:** As someone who has never sung over a track, I want to hear how my song goes while I sing.
#### Acceptance Criteria
1. WHEN the song has a melody (a confirmed hum, or the engine's tune) THE SYSTEM SHALL offer a guide: the
   tune played softly on a voice-like sound over the beat while the person records.
2. THE SYSTEM SHALL let the person turn the guide on or off, and make it quieter or louder, before each take.
3. THE SYSTEM SHALL let the person practise one section on repeat ("just the chorus") without recording.
4. THE SYSTEM SHALL count the person in (one bar of clicks or the beat's own intro) before the part they chose.
5. THE guide SHALL never be recorded into the take (it plays only in the headphones; the warning about
   headphones from voice-room requirement 1 applies to it as well).
6. WHEN there is no melody yet THE SYSTEM SHALL say so plainly and let the person sing freely; their take
   can then become the song's melody (requirement 8).

### Requirement 2 - Tuning to the song's own notes
**User Story:** As a singer, I want my wobbly notes nudged to the notes that belong in my song, not any note.
#### Acceptance Criteria
1. THE SYSTEM SHALL tune each sung note toward the nearest note of the song's scale, and, where the song has a
   melody at that moment, toward the melody's note when the sung note is within two steps of it.
2. THE SYSTEM SHALL keep the three modes ("Just the obvious mistakes", "Tighten it up", "Lock it in") with
   their current strengths, now measured against the song's notes.
3. THE SYSTEM SHALL keep slides and vibrato: only the steady centre of a note is moved; the movement inside
   a note is kept in the two gentler modes.
4. THE SYSTEM SHALL report what it did in plain words, by section ("I nudged four notes in the second verse").
5. THE original take SHALL never change; tuning makes a new version linked to it.

### Requirement 3 - Timing that sits with the beat
**User Story:** As a singer, I want my take to line up with the music even if my computer adds a delay.
#### Acceptance Criteria
1. THE SYSTEM SHALL measure the delay between what the person heard and what was recorded, once per device,
   with a short check ("tap along to four clicks" or a clap), and store it with the person.
2. THE SYSTEM SHALL shift every new take by that delay so it starts where it was sung.
3. THE SYSTEM SHALL offer "tighten the timing": phrases that start clearly early or late against the beat are
   moved toward the beat, never more than a quarter of a beat, and never in the gentlest setting.
4. THE SYSTEM SHALL use the Listener's timing measurement (spec 03) to say how the take sits before and after.
5. The original take SHALL be kept; alignment makes a new version.

### Requirement 4 - Beat bleed removed
**User Story:** As someone recording without headphones, I want the beat taken out of my vocal.
#### Acceptance Criteria
1. WHEN a take was recorded while the beat played through speakers THE SYSTEM SHALL remove the beat from the
   take, using the exact beat audio that was playing (Frank made it, so it knows it).
2. THE SYSTEM SHALL tell the person when it did this and offer to compare with and without.
3. THE SYSTEM SHALL not run removal on a take recorded with headphones confirmed, unless the person asks.
4. Removal SHALL reduce the beat in the take by a measurable amount (checked by the Listener) without making
   the voice sound underwater; if it cannot, it keeps the take as recorded and says so.

### Requirement 5 - The best take, phrase by phrase
**User Story:** As a singer with several takes, I want the best moments put together.
#### Acceptance Criteria
1. THE SYSTEM SHALL split takes into phrases (where the singer breathes), lined up with the song's sections.
2. THE SYSTEM SHALL score each phrase of each take on: notes against the song, timing against the beat,
   clarity (no clipping, little noise), and commitment (steady level), and pick the best per phrase.
3. THE SYSTEM SHALL present the comp as a suggestion, show which take each phrase came from, and let the
   person swap any phrase for the same phrase from another take with one click.
4. Joins SHALL be inaudible: phrases join in a gap where possible, with a short crossfade otherwise.

### Requirement 6 - A harmony that follows the chords
**User Story:** As a singer, I want a harmony that sounds like it belongs, made from my own voice.
#### Acceptance Criteria
1. THE SYSTEM SHALL choose the harmony note for each sung note from the chord playing at that moment
   (the nearest chord note above or below, as chosen), not a fixed distance for the whole take.
2. THE SYSTEM SHALL let the person have the harmony in some sections only (for example only the choruses).
3. THE harmony SHALL be its own layer the Mix Room can turn on and off, and SHALL be marked as a harmony in the
   data (replacing the label-prefix check; voice-to-export-flow task 4.2).

### Requirement 7 - The recording engineer speaks up
**User Story:** As a beginner, I want to know about a problem before I record ten more takes.
#### Acceptance Criteria
1. AFTER each take THE SYSTEM SHALL check for clipping, a very quiet level, background noise and beat bleed
   (Listener measures), and say at most one thing, kindly, with what to try ("move a hand's width back").
2. THE SYSTEM SHALL never comment on the quality of the singing itself.

### Requirement 8 - A sung line can become the song's melody
#### Acceptance Criteria
1. WHEN the song has no melody yet THE SYSTEM SHALL offer to take the tune from a take (same path as the hum:
   play it back, the person confirms, it becomes the melody facet).

### Requirement 9 - The Voice Room conversation knows the takes
#### Acceptance Criteria
1. THE Voice Room conversation SHALL see, through the song brief, each take's facts (length, which sections it
   covers, how it sits on the notes and the beat, whether bleed was removed) and act through typed actions:
   tune, align, remove bleed, comp, harmony, guide settings.
