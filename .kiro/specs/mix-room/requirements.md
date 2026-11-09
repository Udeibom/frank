# Mix Room — Requirements

## Introduction

The Mix Room is where everything comes together — the vocal, the beat, and any harmony are combined into one song. The user controls the mix entirely through listening and conversation; no faders or sliders are ever shown. The system adjusts, renders a preview, and the user reacts until it sounds right. This spec traces to `audio-architecture.md` (mixing, effects, preview vs full render, versioning), `conversation-layer.md` (mix-engineer tone, 2–3 changes per turn), and `design-and-ui.md`.

## Requirements

### Requirement 1 — Mix Assembly on Entry

**User Story:** As a user, I want to hear my song assembled the moment I arrive, so that I have something real to react to.

#### Acceptance Criteria

1. WHEN the user enters the Mix Room THEN the system SHALL take stock of the active vocal (take or comp), any harmony, and the active beat version.
2. IF both vocal and beat exist THEN the system SHALL auto-assemble an initial mix and play it with a greeting.
3. IF only one of vocal or beat exists THEN the system SHALL show what is available and explain what is missing.
4. THE SYSTEM SHALL use sensible default gains that give the vocal prominence (vocal at 0 dB, beat lower).

### Requirement 2 — Mix Conversation

**User Story:** As a user, I want to fix the mix by describing what I hear, so that I never operate a technical control.

#### Acceptance Criteria

1. WHEN the user says the vocals feel buried THEN the system SHALL raise the vocal and slightly lower the beat.
2. WHEN the user says it sounds muddy THEN the system SHALL clean the low end and add clarity.
3. WHEN the user asks for more warmth THEN the system SHALL apply gentle warmth to vocal and/or beat.
4. WHEN the user says "something feels off but I don't know what" THEN the system SHALL analyze the mix and suggest a specific change rather than asking the user to be more precise.
5. WHEN the user asks for space THEN the system SHALL add reverb to the vocal.
6. THE SYSTEM SHALL make no more than 2–3 changes per response and SHALL render a new preview after adjustment.

### Requirement 3 — Mix Versions

**User Story:** As a user, I want every mix kept, replayable, and described in plain words, so that I can compare and return to any of them.

#### Acceptance Criteria

1. WHEN a mix adjustment is made THEN the system SHALL create a new mix version.
2. THE SYSTEM SHALL list versions in a collapsible panel, each with play, timestamp, and a plain-text summary baked into the label (e.g. "Mix v2 — vocals forward, warmer").
3. WHEN the user chooses a version THEN the system SHALL set it active.
4. WHEN the user labels a version THEN the system SHALL persist the label.

### Requirement 4 — Preview vs Full Render

**User Story:** As a user, I want quick listens while tweaking and a high-quality render for export, so that iteration stays fast and the final is clean.

#### Acceptance Criteria

1. WHEN a mix is rendered for listening THEN the system SHALL produce a fast preview at 64 kbps MP3.
2. WHEN the user asks for the full-quality version THEN the system SHALL render WAV then MP3 at 320 kbps.
3. THE SYSTEM SHALL use preview renders for all listening during the mix conversation.

### Requirement 5 — Section-Level Control

**User Story:** As a user, I want to make one part louder than another, so that the song's dynamics match my intent.

#### Acceptance Criteria

1. WHEN the user asks to make a section louder (e.g. "make the chorus louder than the verses") THEN the system SHALL apply a per-section gain stored in `mix_params`.
2. WHEN a mix is rendered THEN the system SHALL actually apply per-section gains by time-windowing the beat using the section bars and tempo known from the beat version's params.
3. THE SYSTEM SHALL NOT report a section change it did not make (no fake handoff).

### Requirement 6 — Stem Balance View

**User Story:** As a user, I want to see the layers in the mix and toggle the harmony, so that I understand the song without touching numbers.

#### Acceptance Criteria

1. THE SYSTEM SHALL show a read-only list of what is in the mix: vocal (main), harmony (if present), and beat.
2. WHEN the harmony toggle is used THEN the system SHALL turn the harmony on or off in the mix.
3. THE SYSTEM SHALL NOT show gain sliders or numeric levels; the harmony toggle is the only direct control.

### Requirement 7 — Mix Room API and Actions

**User Story:** As a developer, I want mix endpoints and a precise action set, so that plain-language requests map to real render operations.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/mix/render` is called with `mix_params` and a quality THEN the system SHALL return a `job_id`.
2. WHEN `GET /projects/{project_id}/mix/versions` is called THEN the system SHALL list mix versions.
3. WHEN `POST /projects/{project_id}/mix/versions/active` is called THEN the system SHALL set the active mix version.
4. WHEN `POST /projects/{project_id}/mix/conversation` is called THEN the system SHALL return `{ message, actions }`.
5. THE SYSTEM SHALL support the action types: `adjust_levels`, `apply_effect`, `section_adjust`, `render_preview`, and `analyze_mix`.

### Requirement 8 — Mix Rendering and Analysis

**User Story:** As the product, I want rendering that fits free-tier memory and analysis that speaks plainly, so that mixes render reliably and advice never leaks jargon.

#### Acceptance Criteria

1. THE SYSTEM SHALL render via FFmpeg overlay of vocal, harmony, and beat with gains and pedalboard effects from `mix_params`.
2. THE SYSTEM SHALL accumulate each layer into the mix and release the source buffer before loading the next, to stay within the free-tier memory budget.
3. WHEN analyzing a mix THEN the system SHALL translate findings (frequency balance, dynamics, vocal prominence) into plain language and SHALL NOT surface raw numbers to the user.

### Requirement 9 — Preview-With-Vocal Isolation

**User Story:** As a user, I want a quick "hear it with my vocal" without polluting my saved mixes, so that previews stay throwaway.

#### Acceptance Criteria

1. WHEN a vocal preview is rendered THEN the system SHALL return only the audio URL.
2. THE SYSTEM SHALL NOT create a mix version or change `active_mix_id` for a vocal preview.

### Requirement 10 — Active State and Status

**User Story:** As a user, I want the active mix reflected across the studio, so that the Export Room uses the right version.

#### Acceptance Criteria

1. WHEN a mix version is created or chosen THEN the system SHALL update `project_active_state.active_mix_id`.
2. WHEN mix content exists THEN the system SHALL set the Mix Room sidebar status indicator to "has content".
