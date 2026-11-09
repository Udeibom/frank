# Beat Room — Requirements

## Introduction

The Beat Room is where the instrumental comes to life. It starts from the musical fingerprint built in the Feel Lab, builds an initial beat, then lets the user shape it — section by section, layer by layer — entirely through listening and conversation. No faders, no technical controls: "the verse feels too empty" and the system responds. It also supports building a beat from scratch without a Feel Lab fingerprint (the Beat-First path). This spec traces to `audio-architecture.md` (procedural engine, stems, versioning), `conversation-layer.md` (Beat Room behavior), and `project-layer.md`.

Generation note: beats are built by Frank's own procedural engine — music theory → MIDI → FluidSynth + SoundFont render per stem — not MusicGen. Because every element is an explicit musical decision, adjusting one stem or section is a precise, controllable operation rather than a black-box re-roll. See `tech.md` and `audio-architecture.md`.

## Requirements

### Requirement 1 — Two Entry States

**User Story:** As a user arriving from either path, I want the Beat Room to meet me where I am, so that I can start building whether or not I did the Feel Lab first.

#### Acceptance Criteria

1. IF a fingerprint exists THEN the system SHALL load it, greet the user, and offer a "Build the beat" action.
2. WHERE a fingerprint exists THE SYSTEM SHALL allow the user to describe specifics before generating.
3. IF no fingerprint exists (Beat-First) THEN the system SHALL run an abbreviated feel discovery here and establish a direction before generating.
4. WHEN a Beat-First direction is established THEN the system SHALL create and save a simplified fingerprint so downstream layers have one.

### Requirement 2 — Initial Beat Generation

**User Story:** As a user, I want a full instrumental built from my feel, so that I have a real starting point to react to.

#### Acceptance Criteria

1. WHEN generation is triggered THEN the system SHALL build a full-length instrumental arranged into sections (Intro, Verse, Chorus, Bridge/Hook, Outro).
2. THE SYSTEM SHALL know section boundaries by construction (the engine builds them), requiring no onset-detection guesswork.
3. THE SYSTEM SHALL render each instrument part (drums, bass, keys/melody, pads/atmosphere) as its own stem.
4. THE SYSTEM SHALL assemble a full beat render from the stems and store it as a `beat_versions` record with stems in `beat_stems`.
5. THE SYSTEM SHALL play the beat in the room with a waveform, a play button, and sections labeled along a timeline.

### Requirement 3 — Section Timeline

**User Story:** As a user, I want to see and navigate the song's sections, so that I can direct changes to a specific part.

#### Acceptance Criteria

1. THE SYSTEM SHALL show a horizontal timeline of sections as warm, duration-proportional blocks.
2. WHEN a section is clicked THEN the system SHALL jump playback to that point and highlight the playing section.
3. WHEN the user edits a section label THEN the system SHALL persist the new label.
4. WHERE reordering, duplicating, or removing a section changes the audio THE SYSTEM SHALL treat it as a re-render producing a new version, not an in-place metadata edit.

### Requirement 4 — Stem Layer View

**User Story:** As a user, I want to understand the layers in plain language, so that I can talk about them without knowing production terms.

#### Acceptance Criteria

1. THE SYSTEM SHALL name layers by what they sound like, never "stem 1".
2. WHEN the user mutes or unmutes a layer for a section THEN the system SHALL re-render so the user hears the result.
3. THE SYSTEM SHALL NOT expose raw per-stem audio files or per-stem waveforms; the assembled section is what plays.

### Requirement 5 — Conversation-Driven Editing

**User Story:** As a user, I want to shape the beat by describing feelings, so that I never touch a technical control.

#### Acceptance Criteria

1. WHEN the user says a section feels too empty or should hit harder THEN the system SHALL add a layer or raise energy/density on that section and re-render.
2. WHEN the user asks to remove an instrument from a section THEN the system SHALL mute that layer there and re-render as a new version.
3. WHEN the user says a part is too busy THEN the system SHALL reduce that stem's note density and re-render that stem.
4. WHEN the user asks to start fresh on a section THEN the system SHALL regenerate only that section's stems.
5. WHEN the user asks for a completely different beat THEN the system SHALL generate a new beat version and preserve the old one.
6. WHEN the user asks to go back to an earlier version THEN the system SHALL restore that previous beat version.
7. THE SYSTEM SHALL make every editing action produce a new version or stem change so the user can always go back.

### Requirement 6 — Element-by-Element Building

**User Story:** As a user who prefers to build up, I want to add one layer at a time, so that I can grow the beat conversationally.

#### Acceptance Criteria

1. WHEN the user asks to start with just drums THEN the system SHALL generate a percussion-only beat.
2. WHEN the user asks to add bass, melody, or atmosphere THEN the system SHALL generate and layer that stem onto the existing beat.
3. THE SYSTEM SHALL perform each add as a stem-only generation and play the result once the job completes.

### Requirement 7 — Beat Versions

**User Story:** As a user, I want every beat version kept and replayable, so that I can compare directions and never lose one.

#### Acceptance Criteria

1. WHEN a significant change occurs THEN the system SHALL create a new beat version record.
2. THE SYSTEM SHALL list versions ("Beat v1", "Beat v2", ...) in a collapsible panel, each playable.
3. WHEN the user chooses a version THEN the system SHALL set it active.
4. WHEN the user labels a version THEN the system SHALL persist the label.

### Requirement 8 — Preview With Vocal (Voice-First)

**User Story:** As a voice-first user, I want to hear the beat under my vocal, so that I can judge whether the beat fits.

#### Acceptance Criteria

1. IF vocal takes exist THEN the system SHALL offer "Hear it with my vocal".
2. WHEN that is activated THEN the system SHALL temporarily overlay the active vocal over the active beat for preview only.
3. THE SYSTEM SHALL NOT persist this preview as the final mix.

### Requirement 9 — Beat Room API

**User Story:** As a developer, I want beat endpoints for generation, editing, and versioning, so that the room is fully server-backed.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/beat/generate` is called with a fingerprint THEN the system SHALL return a `job_id`.
2. WHEN `POST /projects/{project_id}/beat/generate-section` is called THEN the system SHALL regenerate a single section and return a `job_id`.
3. WHEN `POST /projects/{project_id}/beat/add-stem` is called THEN the system SHALL add a stem layer and return a `job_id`.
4. WHEN `POST /projects/{project_id}/beat/conversation` is called THEN the system SHALL return `{ message, actions }`.
5. WHEN `GET /projects/{project_id}/beat/versions` is called THEN the system SHALL list all versions.
6. WHEN `POST /projects/{project_id}/beat/versions/active` is called THEN the system SHALL set the active version.
7. WHEN `PATCH /projects/{project_id}/beat/sections/{section_id}` is called THEN the system SHALL update a section's label.

### Requirement 10 — Beat Conversation Actions

**User Story:** As a developer, I want the LLM to emit precise, resolvable actions, so that plain-language requests map to real operations.

#### Acceptance Criteria

1. THE SYSTEM SHALL support the action types: `regenerate_section`, `add_stem`, `mute_stem`, `reorder_sections`, `generate_full_beat`, `restore_version`, and `set_section_label`.
2. THE SYSTEM SHALL include current version ids and labels in the conversation context so "go back to the first version" resolves to a real id.
3. THE SYSTEM SHALL keep the section PATCH label-only, routing audio-changing reorders through a re-render.

### Requirement 11 — Persistence and Status

**User Story:** As a user, I want the beat to be saved and reflected in the studio map, so that my progress is durable and visible.

#### Acceptance Criteria

1. THE SYSTEM SHALL store every stem and assembled render in Supabase Storage as MP3 for playback.
2. WHEN a beat version is created THEN the system SHALL update `project_active_state.active_beat_version_id`.
3. WHEN beat content exists THEN the system SHALL set the Beat Room sidebar status indicator to "has content".
