# Voice-to-Export Flow — Requirements

## Introduction

Each room was specified and built on its own. The bugs that hurt most were between rooms: state loaded once and never refreshed, a new take that the Mix Room ignored, a preview that moved the active pointer. This spec covers the cross-room contract for the voice-first path (Idea → Feel → Beat → Voice → Mix → Export). It exists so those seams have written, testable requirements.

It adds no new features. It defines how the existing active pointers (`active_beat_version_id`, `active_vocal_id`, `active_comp_id`, `active_mix_id`) must stay consistent between rooms.

## Requirements

### Requirement 1 — Rooms Share One Source of Truth

**User Story:** As a user moving between rooms, I want every room to show the same current state of my song, so that nothing feels disconnected.

#### Acceptance Criteria

1. WHEN the user navigates to any room THEN the system SHALL re-read the project's active state from the backend rather than relying on state loaded earlier.
2. WHEN a room changes an active pointer THEN the system SHALL make the change visible to all other rooms without a page reload.
3. THE SYSTEM SHALL keep a single `project_active_state` row per project as the only authority on what is active.

### Requirement 2 — A New Take Becomes the Vocal the Mix Uses

**User Story:** As a singer, I want my newest recording to be what I hear in the mix, so that I don't have to hunt for a setting.

#### Acceptance Criteria

1. WHEN a take is uploaded THEN the system SHALL set it as the active vocal.
2. WHEN a take is uploaded and an older comp is active THEN the system SHALL make the new take the vocal the Mix Room uses, not the older comp.
3. WHEN the user explicitly chooses a comp as active THEN the system SHALL make the comp the vocal the Mix Room uses.
4. THE SYSTEM SHALL define exactly one rule for which of take or comp wins, applied identically in every room.
5. IF a corrected ("tuned") take exists for the active take THEN the Mix Room SHALL use the corrected audio.

### Requirement 3 — Beat Changes Reach the Mix

**User Story:** As a producer-by-conversation, I want a changed beat to be what the Mix Room mixes, so that the mix never plays an outdated beat.

#### Acceptance Criteria

1. WHEN a new beat version is created or chosen THEN the system SHALL set it as `active_beat_version_id`.
2. WHEN the Mix Room renders THEN the system SHALL use the beat version active at render time.
3. IF the active beat changes after a mix version was created THEN the system SHALL keep the existing mix version unchanged and SHALL let the user render a new one.

### Requirement 4 — Previews Never Change Saved State

**User Story:** As a user, I want listening to a preview to leave my song untouched, so that experimenting is safe.

#### Acceptance Criteria

1. WHEN a "hear it with my vocal" preview is rendered THEN the system SHALL NOT create a mix version.
2. WHEN a preview is rendered THEN the system SHALL NOT change any active pointer.
3. WHEN a Beat Room preview and a Mix Room render run for the same project THEN the system SHALL keep the saved mix list identical to what it was before the preview.

### Requirement 5 — Export Uses the Mix the User Last Chose

**User Story:** As a user finishing a song, I want the Export Room to hand me exactly the mix I last chose, so that the download matches what I heard.

#### Acceptance Criteria

1. WHEN the user enters the Export Room THEN the system SHALL load `active_mix_id`.
2. IF no mix exists THEN the system SHALL explain what is missing and SHALL link to the Mix Room.
3. WHEN the user exports THEN the system SHALL record the `mix_version_id` it came from.
4. IF the user exports the same mix twice with the same mastering choice THEN the system SHALL reuse the existing export.

### Requirement 6 — Nothing Is Lost Across Rooms

**User Story:** As an artist, I want every earlier version to stay available however many times I move between rooms, so that I never lose creative work.

#### Acceptance Criteria

1. WHEN an active pointer moves THEN the system SHALL keep the previously active record and its audio file.
2. THE SYSTEM SHALL never delete a take, beat version, mix version, or export as a side effect of any other room's action.
3. WHEN a take is soft-deleted THEN the system SHALL keep its file and row.

### Requirement 7 — Sidebar Status Matches Reality

**User Story:** As a user, I want the studio map to show what exists, so that I trust it.

#### Acceptance Criteria

1. WHEN a room creates its first content THEN the system SHALL update that room's sidebar indicator to "has content" without a reload.
2. THE SYSTEM SHALL derive each indicator only from the active state, never from local component state.
