# Export Room — Requirements

## Introduction

The Export Room is the finish line. The user listens to the final mix one more time, optionally applies a mastering pass, and downloads their song as an MP3. It is the simplest room in Frank and should feel like a celebration, not a form. This spec traces to `audio-architecture.md` (mastering chain, 320 kbps export), `project-layer.md` (export records, never lose work), and `design-and-ui.md` (warm, single-purpose finish).

## Requirements

### Requirement 1 — Final Listen

**User Story:** As a user, I want to hear my finished song one last time, so that the ending feels like the end of a journey.

#### Acceptance Criteria

1. WHEN the user enters the Export Room THEN the system SHALL load the active mix version ready to play with a warm greeting.
2. THE SYSTEM SHALL present a single large play button for the full song.

### Requirement 2 — Optional Mastering

**User Story:** As a user, I want a one-button "radio ready" polish I can undo, so that I get a stronger sound without risk.

#### Acceptance Criteria

1. THE SYSTEM SHALL offer a single "Make it radio ready" action.
2. WHEN mastering is requested THEN the system SHALL apply a mastering chain server-side (multiband compression, limiting, loudness normalization to -14 LUFS) as an async job.
3. WHEN mastering completes THEN the system SHALL auto-play the result and allow comparison with the un-mastered mix.
4. THE SYSTEM SHALL keep mastering non-destructive and preserve the un-mastered mix.
5. WHEN the user prefers the original THEN the system SHALL return to the un-mastered version in one click.

### Requirement 3 — Export and Download

**User Story:** As a user, I want a single download that is instant once ready, so that taking my song is effortless.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide a single "Download" button that downloads the MP3.
2. THE SYSTEM SHALL name the file `[project-title].mp3`, sanitized for filesystem use.
3. IF no current full render exists (or the mix changed since the last one) THEN the system SHALL run the full render before download, showing "Preparing your download...".
4. WHEN a matching export already exists THEN the system SHALL reuse it so the download is instant.
5. WHEN a download succeeds THEN the system SHALL show a warm closing message.

### Requirement 4 — Export History

**User Story:** As a user, I want my past exports kept and re-downloadable, so that I never lose a finished version.

#### Acceptance Criteria

1. THE SYSTEM SHALL store every export as a record in the `exports` table, including which mix version it came from and whether it was mastered.
2. THE SYSTEM SHALL show a collapsible panel of past exports with date and source mix version.
3. WHEN the user re-downloads a past export THEN the system SHALL serve it directly.

### Requirement 5 — Export API

**User Story:** As a developer, I want export endpoints with signed-URL delivery, so that downloads are private and deduplicated.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/export` is called with a mix version id and a mastering flag THEN the system SHALL return a `job_id`.
2. WHEN `GET /projects/{project_id}/exports` is called THEN the system SHALL list all exports.
3. WHEN `GET /projects/{project_id}/exports/{export_id}/download` is called THEN the system SHALL return a time-limited signed Supabase Storage URL.
4. THE SYSTEM SHALL deduplicate exports by (mix_version_id + mastered) so repeat downloads do not re-render or create duplicate rows.

### Requirement 6 — Mastering Chain

**User Story:** As the product, I want a CPU-only mastering chain producing a 320 kbps MP3, so that "radio ready" is real and free-tier compatible.

#### Acceptance Criteria

1. WHEN mastering runs THEN the system SHALL take the mix WAV, apply a pedalboard chain (multiband compressor, limiter, loudness normalization to -14 LUFS), and output MP3 at 320 kbps via FFmpeg.
2. THE SYSTEM SHALL store the result under `exports/` in a private bucket.
