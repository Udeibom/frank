# Frank: everything left to build

Written Nov 17. This is the whole remaining scope, in one place, to read before the build continues.
Part A lists every open task in the specs that are already partly built (copied from their tasks.md files).
Part B is the full text of the eight specs that existed only as one-line outlines in `_roadmap.md` until today:
requirements, design and tasks for each. The individual files live in `.kiro/specs/<name>/`.

Build order (dependencies): song-engine contracts, planner, stems and editing -> listener rest -> sing-it ->
team-conversation -> refine-loop -> taste-memory and creative-director -> finish-and-intent -> ship-it, with
kiro-craft alongside. Start-from-any-input's remaining paths slot in after team-conversation (they use the router).

Things only you can give or decide are marked FOUNDER.

## Part A: open tasks in specs already under way

### start-from-any-input

- [ ] 1. Models and plumbing
  - [ ] 1.2 Intake routes per input kind, with job wiring and the original input stored. BUILT: `POST /intake/hum` (job), `POST /intake/lyrics`, melody confirm and reject. STILL TO BUILD: rhythm, description, voice memo. (A single route with `kind` routing was dropped on purpose: each kind needs different inputs and different waits.)
- [ ] 4. Words
  - [ ] 4.3 (not started) Description and voice-memo path (Whisper then text path)
- [ ] 5. Merge
  - [ ] 5.2 (done for the words: the route returns ONE question and the Idea Room says it; NOT done for a tune that disagrees with the words, because hum hints are merged in the browser) Conflict questions surfaced to the conversation
- [ ] 6. Frontend
  - [ ] 6.1 `StartSurface.tsx` reachable from every room

### listener

- [ ] 1. Core measurements
  - [ ] 1.1 Loudness per section (gated, K-weighted) and per part — _NOT DONE: per section works (BS.1770 K-weighted, gated); per part needs stored stems (song-engine 5.4); reported as 'could not measure'_
  - [ ] 1.3 Repetition (chroma/MFCC self-similarity, melody similarity) — _NOT DONE: sound similarity of same-named sections and chorus vs verse works; melody-interval similarity is not built_
- [ ] 2. Voice measures
- [ ] 3. Findings
- [ ] 4. Service
  - [ ] 4.4 Mismatch recording hook for taste signals (stores; spec 09 reads) — _NOT DONE_
- [ ] 5. Calibration
  - [ ] 5.2 Founder check — _NOT DONE_: do the findings match what the founder hears?
- [ ] 6. Property-based tests (`backend/tests/test_properties_listener.py`)
  - [ ] 6.3 Prove each test can fail — _NOT DONE_

### song-engine

- [ ] 1. Contracts
  - [ ] 1.1 `Plan`, `PartPlan`, `Score`, `StyleProfile`, typed operation models (Pydantic)
  - [ ] 1.2 Plan storage in `beat_versions.params`; legacy loading path
- [ ] 3. Planner
  - [ ] 3.1 Sections from the structure facet (lines to bars) or style template
  - [ ] 3.2 Energy curve and per-section part choices with rotation across repeats
- [ ] 4. Composer
  - [ ] 4.1 Richer harmony: sevenths, inversions, voice-leading, harmonic rhythm — _NOT DONE: sevenths, inversions and voice-leading exist (theory.py voice_lead, chord_for_degree; test_voice_leading_*), but no harmonic-rhythm change and no test that sevenths appear_
  - [ ] 4.2 Motif-based melody with rests and phrase shapes — _NOT DONE: motif and phrase endings exist in compose_melody; only strong-beat harmony is tested, not rests or phrase shape_
  - [ ] 4.8 Founder verdict on /home/caleb/frank-listening/blind-hum-songs — _NOT DONE: no verdict yet_
  - [ ] 4.12 Tune plays in verses as well as choruses, and hums longer than 16 bars are not cut — _NOT DONE: LEAD_SECTIONS = ("chorus",), MAX_BARS = 16. Also xfail: a tune sitting on a diminished chord is heard as another chord_
  - [ ] 4.4 Bass patterns with approach notes; drum grooves, fills, crashes, breakdowns — _NOT DONE: drum fills and crashes tested; bass approach notes (_bass_pitch "approach") have no test and no breakdown code found_
  - [ ] 4.5 Extras (counter-melody, arpeggios, swells, risers) and transition events
- [ ] 5. Assembly
  - [ ] 5.4 Stem files stored; `beat_stems` extended
- [ ] 6. Renderer clean-up
  - [ ] 6.1 Per-part reverb/chorus control; fix equal-sample note-off ordering
- [ ] 7. Editing
  - [ ] 7.1 Typed operations with validation and a change summary
  - [ ] 7.2 Partial re-compose and re-render; quick section preview
  - [ ] 7.3 Beat Room LLM emits typed operations; remove keyword matching
  - [ ] 7.4 "Another" uses a new seed and sounds different — _NOT DONE: engine-level new seed tested (test_a_new_seed_gives_different_music) and beat_runner derives a seed from version count, but no test covers the "another" path through beat_runner_
- [ ] 9. Property-based tests (`backend/tests/test_properties_engine.py`)
  - [ ] 9.3 Structure validity, stem sum
  - [ ] 9.4 Prove each test can fail

### sound-quality

- [ ] 1. Sample-set spike
  - [ ] 1.4 Cost figures (+12 MB memory, +2 s render) and MIT licence confirmed — _NOT DONE: the fetch script says MIT, but the licence text was not checked here and the memory/time figures were not re-measured (scratch/mem.py exists to do it)_
- [ ] 2. Neural test
  - [ ] 2.4 Kaggle job reproduced from the repo — _NOT DONE: the job lives only in scratch/kjob outside the repo (embeds the excerpt as base64); it has not been re-run and is not committed_
- [ ] 3. Mixing chain
  - [ ] 3.3 Measured effect (+8 dB at equal peak, +20 s on 185 s) — _NOT DONE: figures reported, not re-measured here; the blind pairs were matched to -21.5 LUFS, so the loudness gain was removed for listening_
  - [ ] 3.4 Founder decides: keep, make optional, or drop — _NOT DONE: OPEN. Chain is on by default (mix_chain=True) meanwhile_
- [ ] 4. Arrangement
  - [ ] 4.1 Founder answers the v3 blind test — _NOT DONE: blind-engine-v3/LISTEN_FIRST.md has no answers yet; the moments layer is built (spec 04) but not heard_

### beat-room

- [ ] 9. Deferred follow-ups (tracked, not demo-critical)
  - [ ] 9.1 Preview with vocal (temporary overlay) — after Voice Room
  - [ ] 9.2 Per-section re-render optimization
  - [ ] 9.3 Reorder / duplicate / remove section UI + endpoints

### voice-room

- [ ] 10. Deferred follow-ups (tracked)
  - [ ] 10.1 Alternating A/B "play both" comparison
  - [ ] 10.2 Pitch display waveform overlay + show/hide toggle

### export-room

- [ ] 7. Deferred follow-ups (tracked)
  - [ ] 7.1 Waveform on the final-listen screen
  - [ ] 7.2 Two-pass loudnorm; true-320k from un-encoded source

### voice-to-export-flow

- [ ] 3. Previews never change saved state
  - [ ] 3.2 Automated check that a preview leaves the mix list unchanged (needs DB; covered by the browser test in 5.1)
- [ ] 4. Close the Mix Room resolution gaps
  - [ ] 4.2 Add an `is_harmony` flag instead of matching the label prefix (needs a schema migration; deferred to the auth migration)
- [ ] 5. Browser-driven integration test (Playwright MCP)
  - [ ] 5.1 Click through Voice → Beat → Mix and compare each room with `project_active_state`
  - [ ] 5.2 Export Room loads `active_mix_id` and records `mix_version_id`
- [ ] 6. Property-based tests
  - [ ] 6.2 Pointer moves never delete rows or files

FOUNDER items in Part A: song-engine 4.8 (verdict on blind-hum-songs), sound-quality 3.4 (keep the mixing chain?), sound-quality 4.1 (v3 blind test answers), listener 5.2 (do the findings match what you hear?).

## Part B: the eight new specs in full

### Sing It - Requirements (spec 06)

#### Introduction
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

#### Requirements

##### Requirement 1 - A guide to sing along with
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

##### Requirement 2 - Tuning to the song's own notes
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

##### Requirement 3 - Timing that sits with the beat
**User Story:** As a singer, I want my take to line up with the music even if my computer adds a delay.
#### Acceptance Criteria
1. THE SYSTEM SHALL measure the delay between what the person heard and what was recorded, once per device,
   with a short check ("tap along to four clicks" or a clap), and store it with the person.
2. THE SYSTEM SHALL shift every new take by that delay so it starts where it was sung.
3. THE SYSTEM SHALL offer "tighten the timing": phrases that start clearly early or late against the beat are
   moved toward the beat, never more than a quarter of a beat, and never in the gentlest setting.
4. THE SYSTEM SHALL use the Listener's timing measurement (spec 03) to say how the take sits before and after.
5. The original take SHALL be kept; alignment makes a new version.

##### Requirement 4 - Beat bleed removed
**User Story:** As someone recording without headphones, I want the beat taken out of my vocal.
#### Acceptance Criteria
1. WHEN a take was recorded while the beat played through speakers THE SYSTEM SHALL remove the beat from the
   take, using the exact beat audio that was playing (Frank made it, so it knows it).
2. THE SYSTEM SHALL tell the person when it did this and offer to compare with and without.
3. THE SYSTEM SHALL not run removal on a take recorded with headphones confirmed, unless the person asks.
4. Removal SHALL reduce the beat in the take by a measurable amount (checked by the Listener) without making
   the voice sound underwater; if it cannot, it keeps the take as recorded and says so.

##### Requirement 5 - The best take, phrase by phrase
**User Story:** As a singer with several takes, I want the best moments put together.
#### Acceptance Criteria
1. THE SYSTEM SHALL split takes into phrases (where the singer breathes), lined up with the song's sections.
2. THE SYSTEM SHALL score each phrase of each take on: notes against the song, timing against the beat,
   clarity (no clipping, little noise), and commitment (steady level), and pick the best per phrase.
3. THE SYSTEM SHALL present the comp as a suggestion, show which take each phrase came from, and let the
   person swap any phrase for the same phrase from another take with one click.
4. Joins SHALL be inaudible: phrases join in a gap where possible, with a short crossfade otherwise.

##### Requirement 6 - A harmony that follows the chords
**User Story:** As a singer, I want a harmony that sounds like it belongs, made from my own voice.
#### Acceptance Criteria
1. THE SYSTEM SHALL choose the harmony note for each sung note from the chord playing at that moment
   (the nearest chord note above or below, as chosen), not a fixed distance for the whole take.
2. THE SYSTEM SHALL let the person have the harmony in some sections only (for example only the choruses).
3. THE harmony SHALL be its own layer the Mix Room can turn on and off, and SHALL be marked as a harmony in the
   data (replacing the label-prefix check; voice-to-export-flow task 4.2).

##### Requirement 7 - The recording engineer speaks up
**User Story:** As a beginner, I want to know about a problem before I record ten more takes.
#### Acceptance Criteria
1. AFTER each take THE SYSTEM SHALL check for clipping, a very quiet level, background noise and beat bleed
   (Listener measures), and say at most one thing, kindly, with what to try ("move a hand's width back").
2. THE SYSTEM SHALL never comment on the quality of the singing itself.

##### Requirement 8 - A sung line can become the song's melody
#### Acceptance Criteria
1. WHEN the song has no melody yet THE SYSTEM SHALL offer to take the tune from a take (same path as the hum:
   play it back, the person confirms, it becomes the melody facet).

##### Requirement 9 - The Voice Room conversation knows the takes
#### Acceptance Criteria
1. THE Voice Room conversation SHALL see, through the song brief, each take's facts (length, which sections it
   covers, how it sits on the notes and the beat, whether bleed was removed) and act through typed actions:
   tune, align, remove bleed, comp, harmony, guide settings.

### Sing It - Design (spec 06)

#### Overview
All processing stays on the backend (audio-architecture rule 1). The browser plays the beat and the guide,
records the microphone, and uploads. New code:

| File | Job |
|---|---|
| `services/audio/guide.py` | Render the guide: the melody (Lead or engine melody) on GM 54 at -12 dB under the beat, per section, MP3 |
| `services/audio/song_notes.py` | `target_at(t) -> (scale_pcs, melody_note or None, chord_pcs)` from the active beat plan + lead |
| `services/audio/pitch.py` (changed) | `correct_pitch(wav, mode, targets)`: per-segment shift toward the song target; keeps intra-note movement |
| `services/audio/align.py` | Device delay from a click check; whole-take shift; per-phrase tighten via onset vs beat grid |
| `services/audio/bleed.py` | Beat removal: align beat to take (cross-correlation), estimate a per-band transfer (STFT least squares over voiced-free frames), soft mask subtraction |
| `services/audio/phrases.py` | Phrase split on voicing gaps > 250 ms, mapped to sections by time |
| `services/audio/comp.py` (changed) | Phrase-based scoring and selection; swap endpoint |
| `services/audio/harmony.py` (changed) | Per-note interval from the chord at that time |
| `services/audio/engineer.py` | After-take checks using Listener dsp functions; returns one plain message or none |

#### Song targets
`song_notes.target_at` uses `beat.plan_contexts` (already deterministic from a stored beat version) to know the
chord and the melody note at any second: `section_spans` gives section times, bars give chord indices, the
melody part gives the note. No new storage: it is recomputed from the active beat version's params.

#### Tuning algorithm
1. pyin contour (existing settings). 2. Segment voiced frames into notes (existing `_snap_to_grid` walk).
3. Per note: centre = median pitch of its middle 60%. Target = melody note if |centre - melody| <= 2 semitones,
else nearest scale note. 4. Error = target - centre; apply mode threshold and strength. 5. Rubber Band shift of
the segment by `strength * error` (constant per note, so vibrato inside the note survives); "Lock it in" also
flattens the contour by shifting in short sub-segments. 6. Crossfaded splice (existing).

#### Delay check
The browser plays four clicks at a known time and records; the backend finds the click onsets and the median
offset. Stored per user in `user_settings(user_id, input_delay_ms)` (new table). Applied on upload.

#### Bleed removal
Inputs: take (mono, 44.1 kHz) and the exact beat render the take was recorded against (`beat_version_id` and
start offset are sent with the upload). Steps: cross-correlate to align (sub-frame), STFT both (2048/512),
estimate per-bin gain H from frames where the voice is unvoiced (pyin), residual = take - H*beat, then a soft
mask (Wiener-style) floor 0.1 to avoid "underwater" sound. Accept only if the Listener measures beat-band
correlation drop >= 6 units and the voice loudness drop < 2 units; otherwise keep the original and say so.

#### Comp
Phrases are found on the first take and matched across takes by time (all takes are aligned to the beat, so
the same phrase sits at the same time). Score = 0.4 tuning share (Listener in-tune vs song notes) + 0.25 timing
+ 0.2 clarity + 0.15 steadiness. Stored in the existing `vocal_comps.segments` with `take_id` per phrase.
`POST /voice/comp/{id}/swap {phrase_index, take_id}` creates a NEW comp version.

#### Harmony
For each note segment: chord pcs at its time; harmony note = nearest chord tone strictly above (or below) the
target note; shift = harmony - centre. Sections filter: segments outside the chosen sections are silent.
Schema: `vocal_takes.is_harmony boolean default false` (additive migration), backfilled from label prefix.

#### API (all under `/projects/{id}/voice`)
`GET /guide?section=` (job, returns MP3 URL) · `POST /delay-check` (upload) · `POST /takes` gains
`beat_version_id`, `beat_offset_s`, `headphones` · `POST /takes/{id}/align` · `POST /takes/{id}/remove-bleed`
· `POST /takes/{id}/correct` (now song-aware) · `POST /comp` (phrase comp) · `POST /comp/{id}/swap`
· `POST /harmony {take_id, type, sections}` · `POST /takes/{id}/use-as-melody`.

#### Frontend
Voice Room gains: guide toggle + level, section picker for practice loop, count-in, delay check (one-time
card), per-take chips ("lined up", "beat taken out"), comp view with per-phrase take picker, harmony section
picker. Plain words only ("Sing along with the tune", "Line it up with the beat", "Take the music out of my
vocal").

#### Properties (PBT)
1. Tuning never moves a note already within the mode's threshold of its target. 2. Tuning moves every note
toward its target (distance after <= before). 3. Alignment of a take delayed by d returns within one frame of
d. 4. Bleed removal on take = voice + g*beat reduces the beat part and keeps the voice part within 2 units.
5. Comp segments tile the comp without gaps or overlaps (existing property, now per phrase). 6. Every harmony
note is a chord tone. 7. Originals never change (hash before/after).

### Sing It - Implementation Plan (spec 06)

Depends on spec 03 (Listener measures) and spec 04 (beat plan, lead).

- [ ] 1. Song targets
  - [ ] 1.1 `song_notes.target_at` from the active beat plan and lead, with tests against known plans
    - _Requirements: 2.1, 6.1_
- [ ] 2. Guide
  - [ ] 2.1 Guide render per section (melody on a voice sound, under the beat) as a job; cached by beat version
    - _Requirements: 1.1, 1.3_
  - [ ] 2.2 Voice Room: guide on/off and level, practice loop per section, count-in
    - _Requirements: 1.2, 1.3, 1.4, 1.6_
- [ ] 3. Tuning to the song
  - [ ] 3.1 `correct_pitch` uses song targets; vibrato kept in gentle modes; per-section report
    - _Requirements: 2.1-2.5_
- [ ] 4. Timing
  - [ ] 4.1 Delay check (browser clicks + backend onset offset), `user_settings` migration
    - _Requirements: 3.1_
  - [ ] 4.2 Upload applies the delay; take records `beat_version_id`, offset, headphones
    - _Requirements: 3.2_
  - [ ] 4.3 Tighten-the-timing per phrase, bounded to a quarter beat; Listener before/after
    - _Requirements: 3.3, 3.4, 3.5_
- [ ] 5. Bleed removal with the accept/keep rule and plain report
  - _Requirements: 4.1-4.4_
- [ ] 6. Phrase comp and per-phrase swap
  - _Requirements: 5.1-5.4_
- [ ] 7. Chord-following harmony, per-section, `is_harmony` migration and backfill
  - _Requirements: 6.1-6.3_
- [ ] 8. Recording engineer after-take message
  - _Requirements: 7.1, 7.2_
- [ ] 9. Use a take as the melody (shares the hum confirm path)
  - _Requirements: 8.1_
- [ ] 10. Voice Room typed actions and take facts in the brief
  - _Requirements: 9.1_
- [ ] 11. Property tests (`tests/test_properties_sing.py`), each proved able to fail
- [ ] 12. Real audio check: a real sung take through tune, align, bleed and comp; listening files prepared
  with the Listening Lab agent (before/after)

### Team Conversation - Requirements (spec 07)

#### Introduction
Frank is one trusted producer who consults specialists on the person's behalf (`frank-team.md`). Today each
room has one prompt, conversation history lives in the browser and is lost on reload, the Beat Room turns
replies into edits by keyword matching, and nothing checks the reply for jargon. Every room now receives the
shared song brief (song-record task 6, done Nov 17); this spec builds the team on top of it.
Traces to founder decisions 1, 2, 4, 6 and the conversation-layer steering file.

#### Requirements

##### Requirement 1 - One voice, the right specialists behind it
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

##### Requirement 2 - Disagreement that carries information
#### Acceptance Criteria
1. WHEN two specialists propose conflicting changes (for example the Mix engineer lowers the vocal and the
   Vocal producer objects) THE SYSTEM SHALL hold one round where each states its position with the evidence
   it rests on (a Listener measurement or the person's words), and the Producer decides.
2. THE person SHALL see only Frank's summary ("I could make the music bigger, but it would cover your voice,
   so I lifted both a little").
3. THE round SHALL be bounded: one round, no loops.

##### Requirement 3 - Protect the intention
#### Acceptance Criteria
1. WHEN a request fights the person's stated feeling THE Producer SHALL say so once, kindly, with a reason,
   and offer three directions; IF the person insists THE SYSTEM SHALL build what they asked.

##### Requirement 4 - Creating and refining
#### Acceptance Criteria
1. WHILE the song is in "creating" THE SYSTEM SHALL not volunteer observations.
2. WHILE the song is in "refining" THE SYSTEM MAY start a reply with one observation ("I noticed something")
   when a Listener finding is "likely problem", and offer to show ways to fix it.
3. THE phase SHALL switch to "refining" by itself when the first complete draft exists (beat + vocal + mix),
   and the person can switch it at any time.

##### Requirement 5 - Actions are typed and checked
#### Acceptance Criteria
1. EVERY change Frank makes SHALL come from a typed action validated against a schema; keyword matching SHALL
   be removed (song-engine task 7.3).
2. AN invalid action SHALL be repaired once (the model is told what was wrong) and otherwise dropped with a
   plain message, never executed.

##### Requirement 6 - Plain language, enforced
#### Acceptance Criteria
1. EVERY reply SHALL be checked against the banned-word list (conversation-layer steering) before it is shown.
2. A reply that fails SHALL be rewritten once by the model with the offending words named; IF it still fails
   THE terms SHALL be replaced by their plain equivalents from the steering table.

##### Requirement 7 - The conversation is remembered
#### Acceptance Criteria
1. THE SYSTEM SHALL store every exchange per project and room, so a reload or another device shows it.
2. AFTER 20 exchanges in a room THE SYSTEM SHALL summarise the older ones into a paragraph and keep the summary.
3. BETWEEN sessions THE SYSTEM SHALL store a summary of the song's state and key decisions in the song record
   and load it before the first reply.

##### Requirement 8 - More than one model provider
#### Acceptance Criteria
1. THE SYSTEM SHALL call models through one interface with a primary provider (Groq) and a fallback.
2. WHEN the primary is rate-limited or down THE SYSTEM SHALL use the fallback without the person noticing,
   other than a slightly slower reply.
3. Every provider SHALL be free tier (tech.md principle 4).

### Team Conversation - Design (spec 07)

#### Flow per message
```
POST /projects/{id}/talk {room, message}
  -> load record + brief (record.system_with_brief) + stored history/summary for the room
  -> router: one cheap JSON call -> {specialists: [..], concern: str|null, needs_listening: bool}
  -> if needs_listening: Listener find_issues(cached report, concern)        (spec 03)
  -> each chosen specialist (max 3): JSON {position, actions: [typed], evidence: [ids|"user words"]}
  -> conflict check (code): actions on the same target with opposite direction
       -> one round: each specialist sees the other's position, may revise
       -> Producer call settles: keeps a set of actions
  -> Frank call: writes the reply from the kept positions (one voice, mention rule)
  -> plain-language guard (code + one rewrite)
  -> store exchange; return {message, actions, findings_shown}
```
The room pages call `/talk` instead of their own `/conversation` routes. The old routes stay as thin wrappers
for one release, then are removed.

#### Specialists as data
`backend/app/services/team/roles.py` loads `.kiro/steering/frank-team.md`-derived role cards from
`services/team/roles.json` (owns, hears, changes, disagrees_when, never, allowed_actions). The steering file
stays the human source; a test checks every role in the steering file has a card (spec 12 "role steering that
doubles as runtime prompts").

#### Typed actions
`services/team/actions.py`: one Pydantic model per action, for example
`BeatSectionEdit{section_index, change: more_energy|less_energy|busier|sparser|add_part|remove_part, part?}`,
`ArrangeSections{op: reorder|duplicate|remove, ...}`, `RegenerateSection{section_index, new_seed}`,
`MixLevel{target: vocal|beat|harmony|part:<name>, section?, direction, amount: small|medium}`,
`MixTone{target, change: warmer|brighter|clearer|smoother}`, `MixSpace{target, change: more|less}`,
`VocalTune{take_id, mode}`, `VocalAlign`, `VocalRemoveBleed`, `VocalComp`, `VocalHarmony{sections, type}`,
`LyricOptions{lines, options}`, `FeelUpdate{fields}`, `GenerateTexture`, `Listen{scope, concern}`,
`ProposeDirections` (spec 08). The executor maps each to the existing job endpoints.

#### Mention rule
Stored per room: `turns_since_mention`. Frank's prompt is told whether a mention is allowed this turn.

#### Phase switch
`record.has_first_draft` exists. On mix render completion the runner sets phase to `refining` if it was
`creating` and a beat and a vocal exist (decision recorded in the decisions log).

#### Storage (additive migration 006)
`conversation_turns(id, project_id, room, role, content, actions jsonb, created_at)`;
`conversation_summaries(project_id, room, summary, upto_turn_id, updated_at)`.
`projects.session_summary text` for the between-sessions summary.

#### Providers
`services/llm/providers.py`: `chat_json(system, messages)` tries Groq (`openai/gpt-oss-120b`), on 429/5xx/timeout
tries the fallback. Fallback: Google Gemini API free tier (`gemini-2.5-flash`, JSON mode) with key
`GEMINI_API_KEY`. If no fallback key is set, the second try is Groq's smaller JSON-capable model. The model
names live in this one file.

#### Plain-language guard
`services/team/plain.py`: regex list from conversation-layer steering (BPM, tempo, key/mode as music terms,
reverb, compression, EQ, Hz/kHz/dB, quantization, stem, DAW, VST, MIDI, LUFS) plus replacements table.
Shared with the Plain Language Auditor agent.

#### Token budget
Groq free tier is 6,000 tokens/min. Router + up to 3 specialists + Frank is too much per message at full
brief size, so: router and Frank get the full brief; specialists get the role-trimmed brief
(`build_brief(record, role, budget_chars=2500)`); a message that only needs one specialist skips the
conflict round. Measured target: under 5,000 tokens for a typical message.

#### Properties
1. Every executed action validates against its schema. 2. A reply never contains a banned term after the guard.
3. Mentions never occur in two consecutive replies. 4. The conflict round runs at most once. 5. History reload
returns the same turns in the same order.

### Team Conversation - Implementation Plan (spec 07)

Depends on spec 01 (brief, done) and spec 03 (Listener).

- [ ] 1. Providers: one interface, Groq primary, free fallback, retries
  - _Requirements: 8.1-8.3_
- [ ] 2. Role cards from frank-team.md, with a test that they stay in step
  - _Requirements: 1.2_
- [ ] 3. Typed actions and executor (replaces Beat Room keyword matching)
  - _Requirements: 5.1, 5.2_
- [ ] 4. Router call and specialist calls
  - _Requirements: 1.1, 1.2_
- [ ] 5. Conflict detection, one bounded round, Producer settles
  - _Requirements: 2.1-2.3, 3.1_
- [ ] 6. Frank reply, mention rule, plain-language guard
  - _Requirements: 1.3, 1.4, 6.1, 6.2_
- [ ] 7. Phase: auto-switch to refining, observations only in refining
  - _Requirements: 4.1-4.3_
- [ ] 8. Conversation storage, 20-turn summaries, between-session summary (migration 006)
  - _Requirements: 7.1-7.3_
- [ ] 9. `/talk` endpoint; all six room pages use it; old routes become wrappers
  - _Requirements: 1.3_
- [ ] 10. Property tests, each proved able to fail
- [ ] 11. Live check with the real model: the three demo-story conversations, transcripts saved

### Refine Loop - Requirements (spec 08)

#### Introduction
North-star scenario 3 and demo story 3: "Something feels wrong." Frank measures, explains with evidence, offers
two or three directions the person can HEAR before choosing, and commits the one they pick. When nobody can
tell what is wrong, Frank says so and proposes an experiment. Every version is kept; the person can branch and
ask for an earlier version back in their own words.
Traces to founder decisions 1, 5, 7 and `frank-team.md` "How a request flows".

#### Requirements

##### Requirement 1 - Diagnose with evidence
#### Acceptance Criteria
1. WHEN the person describes a problem THE SYSTEM SHALL ask the Listener (spec 03) about the relevant sections
   and base the diagnosis only on findings it returned, stating the comparison in plain words.
2. WHEN the Listener returns no clear cause THE SYSTEM SHALL say it cannot tell yet and go to requirement 4.
3. WHEN the person disagrees with a measurement THE SYSTEM SHALL side with the person, ask what the word means
   to them ("bigger" as louder, fuller, or higher), and record the mismatch (Listener requirement 6, spec 09).

##### Requirement 2 - Directions, not one answer
#### Acceptance Criteria
1. THE SYSTEM SHALL offer two or three directions, each a short plain description tied to a set of typed
   actions (spec 07), each changing different things.
2. EACH direction SHALL be previewable: a short render of the affected section (or the whole song if the change
   is global), playable from the conversation, without changing any saved version or active pointer.
3. Previews SHALL be ready within 60 seconds for a section on the deployed backend, with a progress message.
4. THE person SHALL be able to compare a preview with the current version at the same position (A/B).

##### Requirement 3 - Commit what was chosen
#### Acceptance Criteria
1. WHEN the person picks a direction THE SYSTEM SHALL apply its actions as a new version (beat, vocal or mix),
   make it active, and record a decision with the options, the evidence, and the choice.
2. THE SYSTEM SHALL ask how it feels afterwards, and keep the other directions available to try.

##### Requirement 4 - Experiments when nobody knows
#### Acceptance Criteria
1. WHEN no cause is found THE SYSTEM SHALL build two or three versions that differ in exactly one thing each
   (for example: fewer parts in the verse; a higher chorus tune; a slower song), say what each changes, and
   let the person's ears decide.
2. THE outcome SHALL be recorded as evidence for taste memory (spec 09).

##### Requirement 5 - Branches and going back
#### Acceptance Criteria
1. THE person SHALL be able to go back to any earlier version of the beat, vocal or mix and continue from it;
   the later versions stay (a branch, not a delete).
2. THE SYSTEM SHALL understand plain references to versions: "give me the second version back", "the one before I
   changed the chorus", "the version from yesterday", resolved against version labels, order, dates and the
   decisions log; IF ambiguous it SHALL play the two candidates and ask.
3. THE studio SHALL show the versions as a simple history per layer, with labels the person can rename.

### Refine Loop - Design (spec 08)

#### Pieces
| Piece | Where |
|---|---|
| Direction model `Direction{id, title, plain, actions: [typed], scope: {sections}, preview_url?}` | `services/refine/models.py` |
| Proposer: Producer call with Listener findings + record -> 2-3 Directions, validated (distinct action sets) | `services/refine/propose.py` |
| Preview runner: applies actions to an IN-MEMORY copy of the active plan / mix params, renders only affected sections (song-engine 7.2 partial re-render), uploads to a `previews/` prefix, never writes versions | `services/jobs/preview_runner.py` |
| Commit: runs the same actions through the normal job path (new version + active pointer) | executor from spec 07 |
| Experiments: a fixed menu of single-variable changes, ranked by which sections the complaint names | `services/refine/experiments.py` |
| Version resolver: `resolve(text, versions, decisions) -> version | [candidates]` | `services/refine/resolve.py` |
| Proposals stored: `refine_proposals(id, project_id, concern, findings, directions jsonb, chosen, created_at)` | migration 007 |

#### Preview speed
Partial re-render renders only sections whose plan changed plus one bar of neighbours for the joins, then
splices into the cached full render (per-section MP3s already stored per beat version). Mix previews reuse the
existing 64 kbps preview render. Target: one 8-bar section in < 30 s on a 0.1-CPU Render instance; measured on
deploy, and the progress text says the honest wait.

#### Experiment menu
energy (chorus fuller / verse thinner), tune (chorus up an octave-step on the engine melody, not on a hummed
tune), speed (+-6%), space (more/less room on the vocal), density (busier/sparser drums), colour (warmer/brighter).
Each experiment changes one field; property-tested.

#### Version resolver
Ordinal ("second", "first", "last", "previous"), relative ("before I changed X" -> latest version created before
the decision whose summary mentions X), date ("yesterday"), label match (fuzzy). Returns a single version or the
top two candidates.

#### UI
Conversation shows direction cards (title, one sentence, play preview, "Use this"). A/B compare plays current and
preview from the same position. Version history panel per layer reuses BeatVersions / MixVersions / takes.

#### Properties
1. Previews never change any version row or active pointer. 2. Directions in one proposal have distinct action
sets. 3. Each experiment differs from the current version in exactly one field. 4. Resolver returns a version
that exists in the project or asks.

### Refine Loop - Implementation Plan (spec 08)

Depends on 03 (Listener), 04 (typed operations, partial re-render), 07 (team, actions).

- [ ] 1. Direction model, proposals table (migration 007)
  - _Requirements: 2.1, 3.1_
- [ ] 2. Proposer from Listener findings; disagreement with a measurement records a mismatch
  - _Requirements: 1.1-1.3, 2.1_
- [ ] 3. Preview runner (in-memory plan, partial re-render, previews prefix, no writes)
  - _Requirements: 2.2, 2.3_
- [ ] 4. Commit path and decision record; "how does that feel?"
  - _Requirements: 3.1, 3.2_
- [ ] 5. Experiments menu and runner
  - _Requirements: 4.1, 4.2_
- [ ] 6. Version resolver and "give it back" action
  - _Requirements: 5.1, 5.2_
- [ ] 7. UI: direction cards, A/B compare, version history per layer
  - _Requirements: 2.4, 5.3_
- [ ] 8. Property tests, each proved able to fail
- [ ] 9. Demo story 3 end to end on the deployed URL, recorded

### Taste Memory - Requirements (spec 09)

#### Introduction
Founder decision 10: specialists remember the artist's taste ("you usually prefer stripped-back verses",
"you dislike cliches", "you like intimate vocals"). This is a relationship, not personalisation, and a
preference is only stated after repeated evidence.

#### Requirements

##### Requirement 1 - Learn from what the person does
#### Acceptance Criteria
1. THE SYSTEM SHALL record taste signals from: directions chosen and rejected (spec 08), experiments won,
   lyric options taken or refused, textures approved or skipped, measurement mismatches (spec 03 req 6), and
   things the person says about themselves ("I hate autotune").
2. EACH signal SHALL carry the specialist it concerns, the project, a plain statement, and its source.

##### Requirement 2 - Only repeated evidence becomes a preference
#### Acceptance Criteria
1. A preference SHALL be stated only when supported by at least three signals across at least two songs, or
   by the person saying it directly.
2. A contradicting signal SHALL weaken a preference; two in a row SHALL retire it.

##### Requirement 3 - Used gently
#### Acceptance Criteria
1. THE preferences SHALL be included in the song brief for the specialist they concern.
2. THE SYSTEM SHALL use a preference to choose the first direction to offer and may mention it ("you usually
   like the verses stripped back, so I started there"), never to refuse what the person asks.

##### Requirement 4 - The person is in control
#### Acceptance Criteria
1. THE person SHALL be able to see what Frank has learned about their taste in plain words, edit any line,
   and forget any line or everything.
2. Forgotten signals SHALL be deleted, not hidden.
3. Taste belongs to the user account, not a project, and is private to them (row level security).

### Taste Memory - Design (spec 09)

#### Data (migration 008, RLS by user_id)
`taste_signals(id, user_id, project_id, specialist, topic, direction (+1|-1), statement, source, created_at)`
`taste_preferences(id, user_id, specialist, topic, statement, strength, status: active|retired|user_stated,
 edited_by_user bool, updated_at)`

`topic` is a short key from a fixed vocabulary (for example `verse_density`, `vocal_closeness`,
`autotune_amount`, `chorus_size`, `lyric_cliche`, `brightness`, `speed`), so signals about the same thing meet.
The fixed vocabulary lives in `services/taste/topics.py`; the model maps a free-text signal to a topic or
`other` (other is never promoted).

#### Promotion
After each new signal: for (user, topic) count signals by direction across distinct projects. Promote when
`same_direction >= 3 and projects >= 2`; strength = net / total. Retire after two consecutive opposite signals.
A direct statement ("I hate autotune") creates a `user_stated` preference immediately.

#### Use
`build_brief` gains a "What this artist tends to like" block for the role, max 5 lines. The proposer (spec 08)
orders directions by matching preferences.

#### UI
`/taste` page reachable from the studio menu: a list of plain sentences, edit in place, "Forget this",
"Forget everything" (with confirm). Plain words only.

#### Properties
1. One signal never creates a preference (except user_stated). 2. Signals from one project never create a
preference. 3. Forget deletes rows. 4. A user never sees another user's taste (RLS test with two users).

### Taste Memory - Implementation Plan (spec 09)

Depends on 07 (team) and 08 (refine signals).

- [ ] 1. Tables, RLS, topics vocabulary (migration 008)
  - _Requirements: 1.2, 4.3_
- [ ] 2. Signal recording from every source listed in requirement 1
  - _Requirements: 1.1_
- [ ] 3. Promotion and retirement rules
  - _Requirements: 2.1, 2.2_
- [ ] 4. Brief block and direction ordering
  - _Requirements: 3.1, 3.2_
- [ ] 5. Taste page: view, edit, forget, forget all
  - _Requirements: 4.1, 4.2_
- [ ] 6. Property tests incl. two-user RLS check, each proved able to fail

### Creative Director - Requirements (spec 10)

#### Introduction
The Creative Director protects what makes THIS song and THIS person themselves. Decided Nov 13
(`producer-craft.md`): it is NOT a "sounds like" role. Frank does not research, describe or imitate a named
artist's sound. If the person names an artist, Frank asks what they love about it and turns that into a feeling
in the person's own words, then builds from the feeling. This amends decision 3 in `frank-team.md`.

#### Requirements

##### Requirement 1 - The identity brief
#### Acceptance Criteria
1. THE SYSTEM SHALL keep an identity brief (the existing `identity_brief` facet): what is distinctively the
   person's own in their words (images, phrases, how they talk about the song), their voice (how they sing,
   what they kept), and their choices (what they chose and rejected, from the decisions log).
2. THE brief SHALL be written in plain words, updated after major choices, versioned like every facet, and
   shown to the person on request ("what makes this song yours").
3. EVERY specialist SHALL receive the identity brief in the song brief.

##### Requirement 2 - Named artists become feelings
#### Acceptance Criteria
1. WHEN the person names an artist or song THE SYSTEM SHALL ask one question about what they love in it, in
   feeling words (close, hushed, wide, raw, bouncy), and record the answer as the feeling, not the name.
2. THE SYSTEM SHALL NOT search the web for, describe, or imitate the named artist's sound, and SHALL NOT steer
   the person toward sounding like anyone.
3. THE SYSTEM SHALL NOT lecture the person for naming an artist.

##### Requirement 3 - Speak up about drift
#### Acceptance Criteria
1. WHEN a proposed direction (spec 08) or a requested change would remove something the identity brief marks as
   theirs (for example cutting their own lyric image, or tuning away the character of their voice in "Lock it
   in" when they said they want it raw), THE Creative Director SHALL say so once, with the reason, and offer a
   way to keep it.
2. THE person's call wins (founder decision 1).

### Creative Director - Design (spec 10)

#### Identity brief writer
`services/team/identity.py`: one model call (Creative Director role card) over: the intent facet, the feeling
facet, the lyrics, the person's own messages (last 40), decisions (chosen/rejected), vocal facts (raw or tuned
preference). Output JSON `{own_words: [..], own_images: [..], voice: str, keep: [..], avoid: [..]}` written as a
new `identity_brief` facet version. Runs after: lyrics saved, a direction chosen, a take kept, at most once per
10 minutes per project (job).

#### Named artists
Detection in the router (spec 07): the router JSON gets `named_reference: str|null`. When set, the Creative
Director card answers with ONE question about what they love, and on the reply the feeling words go into the
feeling facet (`loved_qualities`); the name is stored in the `references` facet with `use: "feeling_only"` and
is never passed to the composer or to any prompt as a target. No web tool is given to any role.

#### Drift check
Code check before executing directions or `VocalTune{mode: full}` and lyric replacements: compare the change
against `keep` items (lyric lines/images by text match; voice character flags). On hit, the Producer's reply
gets one line from the Creative Director. Recorded as a decision.

### Creative Director - Implementation Plan (spec 10)

Depends on 07 (team).

- [ ] 1. Identity brief writer (events, versioned facet) and "what makes this yours" view
  - _Requirements: 1.1-1.3_
- [ ] 2. Named-artist detection and the one question; feeling recorded; reference never stored as a target
  - _Requirements: 2.1-2.3_
- [ ] 3. Drift check on directions and changes, one mention, person wins
  - _Requirements: 3.1, 3.2_
- [ ] 4. Tests: no web call, artist name never reaches the composer, drift property; each proved able to fail

### Finish and Intent - Requirements (spec 11)

#### Introduction
"Finished" means the person's intent is met, and the person decides (founder decision 8). Today the Mix Room
treats the whole beat as one block (only the vocal, the beat and the harmony have levels), mastering can run on
anything, nothing asks whether the song matches what the person first described, and there is no surprise
version. This spec gives the mix real parts, a finishing step worthy of sharing, the intent check, one optional
surprise, and the export.
Depends on song-engine task 5.4 (stored stems). Traces to Mix engineer, Mastering engineer, decisions 8 and 9.

#### Requirements

##### Requirement 1 - Mix every part
#### Acceptance Criteria
1. THE Mix Room SHALL mix the beat's parts separately (drums, bass, keys, melody, pad and the extras), plus the
   lead vocal and the harmony, each with level, tone ("warmer", "brighter", "clearer") and space, per section
   when asked ("bring the piano down in the bridge").
2. THE mix conversation SHALL make at most three changes per reply and say what it did.
3. THE stem balance view SHALL show every part, in plain names ("Drums", "Bass", "Piano").
4. Older beats without stored parts SHALL still mix as one block, and the Mix Room SHALL offer to rebuild the
   parts from the saved plan.

##### Requirement 2 - Finishing worthy of sharing
#### Acceptance Criteria
1. THE finishing step SHALL bring the song to a streaming loudness (about -14 on the loudness scale used by
   streaming services) without audible pumping or clipping, measured by the Listener.
2. THE finishing step SHALL refuse to start from a low-quality preview and SHALL render the mix at full quality
   first (two-pass loudness, true 320 kbps from an uncompressed source; export-room task 7.2).
3. THE person SHALL hear before/after and choose.

##### Requirement 3 - Does it match what you described?
#### Acceptance Criteria
1. THE SYSTEM SHALL keep the person's own first description of the song as the intent statement.
2. BEFORE the first export THE SYSTEM SHALL play the song and ask, in their words, whether it matches ("You said
   'standing alone in the rain after losing someone'. Does this feel like that?").
3. IF the answer is no THE SYSTEM SHALL go to the refine loop (spec 08) with the answer as the concern; IF yes
   it SHALL mark the song finished (status `exported` after export) and record the decision.

##### Requirement 4 - One surprise, never a replacement
#### Acceptance Criteria
1. AFTER the person's version is complete THE SYSTEM MAY offer ONE unexpected alternative ("Before we finish, I
   tried one idea"), built as an extra version that differs in one bold way (a stripped-down version, a
   different feel), never replacing the active version.
2. THE offer SHALL happen at most once per song and SHALL be easy to skip.

##### Requirement 5 - Export
#### Acceptance Criteria
1. THE person SHALL download the finished song as a high-quality MP3, and also separate parts ("Download
   separate parts") as a zip of per-part files.
2. THE final-listen screen SHALL show the waveform (export-room task 7.1).

### Finish and Intent - Design (spec 11)

#### Parts in the mix
Song-engine 5.4 stores, per beat version, one MP3 per part for the whole song (`beat_stems` rows with
`type = part name`, `section = 'all'`), rendered in the same pass as the full beat (the renderer already makes
each part's audio; today it is summed and thrown away). Memory: parts are encoded and released one at a time.
Mix params become `{parts: {name: {level_db, tone, space, sections: {i: level_db}}}, vocal: {...}, harmony: {...}}`.
`render_mix` sums decoded parts with pedalboard chains per part. Legacy beats: `parts` absent -> current blob path;
"rebuild the parts" re-renders from the stored plan + seed (deterministic, so it sounds the same).

#### Finishing chain
Full-quality mix render (WAV in memory) -> gentle glue compression -> limiter at -1 dBTP -> FFmpeg `loudnorm`
two-pass to -14 LUFS integrated -> MP3 320k from the WAV. Listener checks clipping share and loudness after;
if loudness misses by > 1 unit or clipping is found, one corrective pass, else report honestly.

#### Intent
`intent` facet already exists. Captured from the person's first description in any room (router flags
`is_intent_statement`), editable. Export Room: before the first export, a card plays the mix and shows their
words with "Yes, that's it" / "Not yet". "Not yet" opens the conversation with the refine loop.

#### Surprise
After the first export or the intent "yes": a job builds one variant (choose from: stripped-down (keys + vocal),
half-time feel, brighter colour), labelled "Frank's idea", not active. A flag `surprise_offered` on the project.

#### Separate parts
`GET /export/{id}/parts.zip` streams a zip of the stored part MP3s plus vocal and harmony.

### Finish and Intent - Implementation Plan (spec 11)

Depends on song-engine 5.4 (stems), 03 (Listener), 08 (refine loop).

- [ ] 1. Per-part mix model, renderer, legacy one-block path and "rebuild the parts"
  - _Requirements: 1.1, 1.4_
- [ ] 2. Mix conversation over parts (typed actions, max three), stem balance view with every part
  - _Requirements: 1.2, 1.3_
- [ ] 3. Finishing: full-quality source rule, two-pass loudness, true peak, Listener check, before/after
  - _Requirements: 2.1-2.3_
- [ ] 4. Intent statement capture and the intent check before first export
  - _Requirements: 3.1-3.3_
- [ ] 5. Surprise version, once per song
  - _Requirements: 4.1, 4.2_
- [ ] 6. Download separate parts (zip) and final-listen waveform
  - _Requirements: 5.1, 5.2_
- [ ] 7. Property tests and a real-audio before/after listening set

### Kiro Craft - Requirements (spec 12)

#### Introduction
How Frank is built with Kiro, made real and honest. Started Nov 12: five hooks (architecture check, secret and
frontend-audio guard, spec checker, plain-language scan on save, song tests on save), seven agents (Database
Steward, Frank Code Reviewer, Integration Tester, Listening Lab, PBT Author, Plain Language Auditor, Spec Keeper),
an `mcp.json.example`, and `KIRO_USAGE.md`. This spec finishes the rest.

#### Requirements

##### Requirement 1 - Role steering is the runtime prompt
#### Acceptance Criteria
1. THE specialist role cards Frank uses at runtime (spec 07) SHALL be generated from, or checked against,
   `frank-team.md`, so the steering file and the product cannot drift; a test SHALL fail when they differ.

##### Requirement 2 - Hooks that do real work
#### Acceptance Criteria
1. EVERY hook SHALL run a real check and fail loudly; a hook that does nothing SHALL be removed.
2. THE Listener SHALL run from a hook after an engine change, rendering a fixed reference song and comparing its
   findings with the stored baseline (no new "likely problem" allowed without a note).

##### Requirement 3 - Kiro can hear its own renders
#### Acceptance Criteria
1. THE Listener SHALL be exposed as a local MCP server (`measure_file`, `find_issues_file`, `compare_files`) so
   Kiro can check audio it produced, using the same functions as the product (Listener requirement 4.2).

##### Requirement 4 - Property tests protect the invariants
#### Acceptance Criteria
1. EVERY spec's correctness properties SHALL have tests, and each test SHALL be proved able to fail (mutation
   recorded in the task evidence).

##### Requirement 5 - Continuous checks
#### Acceptance Criteria
1. A GitHub Actions workflow SHALL run on every push: backend tests, frontend type check and lint, the spec
   checker and the architecture checker, using the free tier.

##### Requirement 6 - Honest records
#### Acceptance Criteria
1. `README.md` SHALL describe how to run and deploy Frank as it is; `KIRO_USAGE.md` SHALL describe what was
   actually used, including what failed.
2. `mcp.json.example` SHALL list every MCP server with placeholder secrets only.

### Kiro Craft - Design (spec 12)

- Role cards: `backend/app/services/team/roles.json` is the runtime form; `scripts/check_roles.py` parses
  `frank-team.md` role headings and fields and fails on any missing or extra role. Run by the spec hook and CI.
- Listener hook: `scripts/listen_reference.py` renders `fixtures/reference_song.json` (fixed fingerprint + seed),
  runs `find_issues`, compares with `fixtures/reference_findings.json`. Triggered PostFileSave on
  `backend/app/services/generation/`. Takes ~40 s, so it runs in the background and writes a report file.
- Listener MCP: `tools/listener_mcp/server.py` (python `mcp` SDK, stdio), three tools wrapping
  `service.measure_audio` on decoded files. Added to `mcp.json.example`.
- CI: `.github/workflows/ci.yml`: ubuntu, apt ffmpeg fluidsynth librubberband, fetch soundfont (cached),
  pip install, `pytest -q`, `npm ci && npx tsc --noEmit && npm run lint`, both checkers.
- Mutation evidence: each PBT task records "reverted X, test Y failed".

### Kiro Craft - Implementation Plan (spec 12)

- [ ] 1. Role cards and the drift check
  - _Requirements: 1.1_
- [ ] 2. Hook review (remove any no-op); Listener reference hook
  - _Requirements: 2.1, 2.2_
- [ ] 3. Listener MCP server and mcp.json.example entry
  - _Requirements: 3.1, 6.2_
- [ ] 4. Mutation evidence for every property test in every spec
  - _Requirements: 4.1_
- [ ] 5. GitHub Actions CI
  - _Requirements: 5.1_
- [ ] 6. README and KIRO_USAGE brought up to date
  - _Requirements: 6.1_

### Ship It - Requirements (spec 13)

#### Introduction
Frank on the public internet, free tier, with the three demo stories working on the deployed URL. Follows
`deployment.md`.

#### Requirements

##### Requirement 1 - Deployed
#### Acceptance Criteria
1. THE backend SHALL run on Render as a Docker web service from `backend/Dockerfile` (FluidSynth, FFmpeg,
   Rubber Band, SoundFont fetched at build), with `GET /health`.
2. THE frontend SHALL run on Vercel with `NEXT_PUBLIC_API_URL` pointing at the backend.
3. CORS SHALL allow only the Vercel URL (and localhost in development).
4. Every migration SHALL be applied to the production database, and row level security SHALL be on for every
   table holding user data (auth checklist).
5. No secret SHALL be in the repository; the dev auth bypass SHALL be off in production.

##### Requirement 2 - Works within the free tier
#### Acceptance Criteria
1. THE backend SHALL stay within the free instance's memory (512 MB) during a full beat render, a mix and an
   export, measured on the deployed service.
2. A cold start SHALL show "Frank is waking up..." when the health check takes longer than 3 seconds, never an error.
3. Long jobs SHALL show honest progress and wait times measured on the deployed service.

##### Requirement 3 - The demo stories pass on the deployed URL
#### Acceptance Criteria
1. Demo 1 (a feeling and lyrics become a sung, finished song), demo 2 (a phone hum becomes a produced song),
   and demo 3 (the "something feels wrong" producer conversation) SHALL each be run end to end on the
   deployed URL with a fresh account, and the run recorded (steps, outputs, times, problems).
2. The voice-first and beat-first paths and an MP3 download SHALL be checked (deployment checklist).

##### Requirement 4 - Ready to show
#### Acceptance Criteria
1. THE repository SHALL have a licence file.
2. THE founder records the demo video and write-up (founder tasks; Frank's side is a demo script and a
   working deployment).

### Ship It - Design (spec 13)

- Render: Docker web service, root `backend/`, Dockerfile path `backend/Dockerfile`, health check `/health`,
  env vars per deployment.md (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, `ALLOWED_ORIGINS`,
  `ENVIRONMENT=production`, optional `GEMINI_API_KEY`). Created through the Render dashboard or the Render API
  with an API key from the founder; `render.yaml` blueprint committed so it is repeatable.
- Vercel: project root `frontend/`, env `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_URL`. Deployed with the Vercel CLI using a token from the founder, or by linking the GitHub
  repo in the Vercel dashboard (deploys from `main`).
- Memory: one heavy job at a time already (semaphores in beat, hum, intake runners); add a single process-wide
  heavy-job semaphore shared by beat, mix, export and listen; measure peak RSS during a full beat with
  `/proc/self/status` logged at job end.
- Supabase Auth: add the Vercel URL to allowed redirect URLs.
- Demo runs: scripted with the Integration Tester agent and Playwright against the production URL; results in
  `docs/demo-runs/`.
- Licence: MIT unless the founder chooses otherwise (the founder's call; flagged).

### Ship It - Implementation Plan (spec 13)

Needs from the founder: a Render account (API key, or create the service in the dashboard) and a Vercel token
(or link the GitHub repo in the Vercel dashboard). Everything else Frank's side can do.

- [ ] 1. `render.yaml`, production settings, shared heavy-job semaphore, memory logging
  - _Requirements: 1.1, 2.1_
- [ ] 2. Backend deployed on Render; health check green; memory measured on a full beat
  - _Requirements: 1.1, 2.1_
- [ ] 3. Frontend deployed on Vercel; CORS locked; Supabase redirect URLs
  - _Requirements: 1.2, 1.3_
- [ ] 4. All migrations on production; RLS audit by the Database Steward agent
  - _Requirements: 1.4_
- [ ] 5. Secrets and dev bypass audit
  - _Requirements: 1.5_
- [ ] 6. Cold start and progress wording checked on the deployed URL
  - _Requirements: 2.2, 2.3_
- [ ] 7. Demo stories 1, 2, 3 run on the deployed URL with a fresh account; records in docs/demo-runs/
  - _Requirements: 3.1, 3.2_
- [ ] 8. Licence file
  - _Requirements: 4.1_
