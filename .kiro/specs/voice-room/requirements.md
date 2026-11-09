# Voice Room — Requirements

## Introduction

The Voice Room is the most personal layer. The user records their vocal — as many takes as they need — and the system handles the technical work: pitch analysis, pitch correction under the user's control, vocal comping from multiple takes, and harmony layering. The user never needs to know what pitch correction is; they just need to hear their voice in the song. This spec traces to `audio-architecture.md` (pitch processing, harmony, versioning), `conversation-layer.md` (patient vocal-producer tone), and `design-and-ui.md` (recording flow, accessibility).

Processing notes: pitch detection uses librosa `pyin` (not Basic Pitch — TensorFlow is too heavy for the free tier), and pitch shifting uses Rubber Band via `pylibrb` (binds `librubberband` directly, ~100x faster than librosa). See `tech.md` and `audio-architecture.md`.

## Requirements

### Requirement 1 — Recording Setup

**User Story:** As a singer, I want a clear, friendly setup that respects my mic and headphones, so that I can record a clean take with confidence.

#### Acceptance Criteria

1. WHEN the user enters the Voice Room THEN the system SHALL check microphone permission.
2. IF permission is not granted THEN the system SHALL show a warm explanation and a button to grant access.
3. THE SYSTEM SHALL attempt best-effort headphone detection and, IF headphones are not confirmed, show a non-blocking tip about using them.
4. THE SYSTEM SHALL NOT block recording when headphones are not detected.
5. IF a beat exists THEN the system SHALL offer "Record with beat" (beat plays while recording) and "Record without beat".

### Requirement 2 — Multi-Take Recording

**User Story:** As a singer, I want to record as many takes as I like without losing any, so that I can keep my best moments.

#### Acceptance Criteria

1. THE SYSTEM SHALL present a large, unmistakable record button that is clearly red while recording.
2. WHILE recording THE SYSTEM SHALL show a live mic level meter, a timer, and a stop control, and play the beat if "Record with beat" was chosen.
3. WHEN a take completes THEN the system SHALL show it as a card with waveform, duration, timestamp, and label.
4. THE SYSTEM SHALL NOT delete a take unless the user explicitly deletes it, and re-recording SHALL create a new take rather than overwrite.
5. WHEN the user labels a take THEN the system SHALL persist the label.

### Requirement 3 — Take Comparison

**User Story:** As a singer, I want to compare takes, so that I can choose the one that feels best.

#### Acceptance Criteria

1. THE SYSTEM SHALL allow selecting takes to compare side by side, each with its own play control.
2. WHEN the user sets a take as active THEN the system SHALL record it as the active vocal.

### Requirement 4 — Pitch Analysis and Display

**User Story:** As a singer, I want to see where my pitch wandered without being judged, so that I feel informed rather than criticized.

#### Acceptance Criteria

1. WHEN a take is uploaded THEN the system SHALL run librosa `pyin` and store the pitch contour.
2. THE SYSTEM SHALL present pitch as color only — green in tune, yellow slightly off, red noticeably off — with no note names or frequencies.
3. WHERE color conveys tuning THE SYSTEM SHALL ensure the information is not conveyed by color alone (per accessibility steering).

### Requirement 5 — Pitch Correction (Three Modes)

**User Story:** As a singer, I want to choose how much tuning is applied in plain language, so that I keep control over how natural or produced my voice sounds.

#### Acceptance Criteria

1. THE SYSTEM SHALL offer three plain-language modes: "Just the obvious mistakes" (>50 cents), "Tighten it up" (>20 cents), and "Lock it in" (full snap).
2. WHEN "Lock it in" is chosen THEN the system SHALL perform real per-note snapping to the nearest pitch with crossfades, not a global average.
3. WHEN correction is applied THEN the system SHALL create a new processed take labeled "(tuned)" and SHALL always preserve the original.
4. THE SYSTEM SHALL apply correction as an async job using Rubber Band via `pylibrb`.
5. THE SYSTEM SHALL let the user compare original versus corrected before choosing.

### Requirement 6 — Vocal Comping

**User Story:** As a singer, I want the best moments from my takes stitched together, so that I get a strong composite without editing audio myself.

#### Acceptance Criteria

1. WHERE the user has two or more takes THE SYSTEM SHALL offer "Put together the best version".
2. WHEN a comp is requested THEN the system SHALL score segments by pitch confidence and energy and assemble the best sequence.
3. THE SYSTEM SHALL present the comp as a suggestion and show which take each segment came from.
4. WHEN the user asks to use a specific take for a section THEN the system SHALL adjust the comp accordingly.
5. THE SYSTEM SHALL store the comp as a `vocal_comps` record without touching the source takes.

### Requirement 7 — Harmony Layering

**User Story:** As a singer, I want a harmony generated from my own voice, so that I get a richer sound without recording again.

#### Acceptance Criteria

1. WHEN the user asks to add a harmony THEN the system SHALL generate a harmony part from the active vocal by pitch-shifting via Rubber Band.
2. THE SYSTEM SHALL choose the harmony interval from the fingerprint's key and mode (mode-aware: major vs minor third).
3. THE SYSTEM SHALL offer "higher harmony", "lower harmony", or "both" in plain language with no interval names.
4. THE SYSTEM SHALL store the harmony as its own layer that the Mix Room can turn on or off, and SHALL NOT require a second recording.

### Requirement 8 — Voice Room API

**User Story:** As a developer, I want take, correction, comp, and harmony endpoints, so that the room is fully server-backed with async processing.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/voice/takes` receives an upload THEN the system SHALL return `{ take_id, audio_url }` immediately and trigger an async pitch-analysis job.
2. WHEN `GET /projects/{project_id}/voice/takes` is called THEN the system SHALL list takes with pitch data.
3. WHEN `DELETE /projects/{project_id}/voice/takes/{take_id}` is called THEN the system SHALL soft-delete (flag set, file kept).
4. WHEN `POST /.../takes/{take_id}/correct` is called with a mode THEN the system SHALL return a `job_id`.
5. WHEN `POST /.../voice/comp` or `POST /.../voice/harmony` is called THEN the system SHALL return a `job_id`.
6. WHEN `POST /.../voice/active` is called THEN the system SHALL set the active vocal (take or comp).
7. WHEN `POST /.../voice/conversation` is called THEN the system SHALL respond as a patient vocal producer with `{ message, actions }`.

### Requirement 9 — Processing Preservation and Storage

**User Story:** As the product, I want every original preserved and playback copies kept small, so that no take is ever lost and streaming stays within free-tier limits.

#### Acceptance Criteria

1. THE SYSTEM SHALL preserve original takes as WAV and SHALL NOT overwrite them.
2. THE SYSTEM SHALL store corrected, comp, and harmony playback copies as MP3.
3. THE SYSTEM SHALL perform audio downloads inside worker threads so the request handler is not blocked.
4. WHEN correction runs THEN the system SHALL write `processed_url`; harmony and comp SHALL create new records.

### Requirement 10 — Active State and Status

**User Story:** As a user, I want my chosen vocal reflected across the studio, so that later rooms use the right take.

#### Acceptance Criteria

1. WHEN a take is uploaded or chosen THEN the system SHALL update `project_active_state.active_vocal_id`.
2. WHEN a comp is created THEN the system SHALL update `active_comp_id`.
3. WHEN vocal content exists THEN the system SHALL set the Voice Room sidebar status indicator to "has content".
