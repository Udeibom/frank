# Idea Room — Requirements

## Introduction

The Idea Room is where a song starts. It is a distraction-free lyrics editor with an AI co-writer that thinks like a songwriter. The user writes; the system assists — but the user is always the author. Every version of the lyrics is saved automatically and nothing is ever overwritten. This spec covers the editor, the co-writer conversation, lyric version history, voice-memo capture, and the backend endpoints that power them. It traces to `conversation-layer.md` (Idea Room behavior), `project-layer.md` (version history), and `design-and-ui.md`.

## Requirements

### Requirement 1 — Lyrics Editor

**User Story:** As a writer, I want a quiet, spacious place to write lyrics that saves itself, so that I can focus on words and never fear losing a draft.

#### Acceptance Criteria

1. THE SYSTEM SHALL present a distraction-free editor occupying the main content area, with readable text slightly larger than body copy.
2. WHEN the user stops typing for 2 seconds THEN the system SHALL auto-save (debounced).
3. THE SYSTEM SHALL allow plain-text section labels (Verse, Chorus, Bridge, Hook, Outro) without special formatting.
4. THE SYSTEM SHALL NOT display word counts, character limits, or grammar overlays.
5. THE SYSTEM SHALL NOT present a "Submit" or "Done" button; the user leaves when ready and the lyrics persist.

### Requirement 2 — Lyric Version History

**User Story:** As a writer, I want every draft kept and restorable, so that I can experiment freely and always return to an earlier version.

#### Acceptance Criteria

1. WHEN an auto-save differs from the previous version THEN the system SHALL create a new `lyrics_versions` record.
2. IF a save's content is identical to the previous version THEN the system SHALL NOT create a new version.
3. THE SYSTEM SHALL show a collapsible version history listing each version by timestamp, first line, and optional label.
4. WHEN the user clicks a version THEN the system SHALL preview it read-only alongside the current lyrics.
5. WHEN the user restores a version THEN the system SHALL create a new version from that content and SHALL NOT delete the current one.
6. WHEN the user labels a version THEN the system SHALL persist the label.
7. THE SYSTEM SHALL treat the most recently saved version as active by default.

### Requirement 3 — AI Co-Writer

**User Story:** As a writer, I want a collaborator who offers ideas on request, so that I get help with lines, rhymes, and flow without losing authorship.

#### Acceptance Criteria

1. THE SYSTEM SHALL keep the co-writer aware of the current lyrics as context on every exchange.
2. WHEN the user asks for help with a selected line, a rhyme, a reaction to a verse, a drafted chorus, or a flow check THEN the system SHALL respond in plain language without music-theory jargon.
3. THE SYSTEM SHALL NOT rewrite the user's lyrics without an explicit instruction.
4. WHEN the system drafts lyrics THEN the system SHALL present them as a block in the conversation with "Add to editor" and "Ignore" options.
5. WHEN the user chooses "Add to editor" THEN the system SHALL append the draft as a new section and SHALL NOT replace existing lyrics.

### Requirement 4 — Structure Awareness

**User Story:** As a writer, I want the system to understand my song's sections, so that later rooms can map lyrics to musical sections.

#### Acceptance Criteria

1. THE SYSTEM SHALL recognize sections from user labels or repeated-line patterns.
2. WHEN referencing lyrics THE SYSTEM SHALL name sections (e.g. "the second verse") rather than line numbers.
3. THE SYSTEM SHALL make section information available to the Beat Room downstream.

### Requirement 5 — Voice Memo Capture

**User Story:** As a writer, I want to speak an idea and see it transcribed, so that I can capture a thought without typing.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide a subtle microphone control that records a voice memo in-browser.
2. WHEN a memo is recorded THEN the system SHALL upload it, transcribe it, and show the transcription in the conversation.
3. THE SYSTEM SHALL NOT insert the transcription into the editor automatically.
4. THE SYSTEM SHALL store the original audio for later reuse (e.g. the Feel Lab hum feature).

### Requirement 6 — Lyrics API

**User Story:** As a developer, I want lyrics endpoints that persist and version content, so that the editor and history are backed by durable storage.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/lyrics` is called THEN the system SHALL save a new version and return its id.
2. WHEN `GET /projects/{project_id}/lyrics` is called THEN the system SHALL list all versions.
3. WHEN `GET /projects/{project_id}/lyrics/{version_id}` is called THEN the system SHALL return that version.
4. WHEN `PATCH /projects/{project_id}/lyrics/{version_id}` is called THEN the system SHALL update the version's label.
5. WHEN `POST /projects/{project_id}/lyrics/active` is called THEN the system SHALL set the active lyrics version.
6. WHEN a new version is saved THEN the system SHALL update `project_active_state.active_lyrics_id`.

### Requirement 7 — Co-Writer Conversation API

**User Story:** As a developer, I want a structured conversation endpoint, so that the UI renders a message and dispatches any actions.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/conversation/idea` is called with the message, current lyrics, optional selected text, and history THEN the system SHALL return `{ message, actions }`.
2. THE SYSTEM SHALL support exactly one action type in the Idea Room: `suggest_lyrics` with `{ content, section_label? }`.
3. THE SYSTEM SHALL build the prompt from the Idea Room system prompt, current lyrics, history, and the user message, and call Groq.

### Requirement 8 — Voice Memo Transcription API

**User Story:** As a developer, I want a transcription endpoint, so that recorded memos become text reliably on free-tier services.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/lyrics/voice-memo` receives a multipart audio file THEN the system SHALL convert it to WAV via FFmpeg if needed.
2. THE SYSTEM SHALL transcribe via Groq Whisper (`whisper-large-v3-turbo`), since the Hugging Face inference domain was retired.
3. THE SYSTEM SHALL store the audio under `voice-memos/` and return `{ transcription, audio_url }`.

### Requirement 9 — Status Reflection

**User Story:** As a user, I want the Idea Room to show as having content once I've written, so that the studio map reflects my progress.

#### Acceptance Criteria

1. WHEN lyrics exist for a project THEN the system SHALL set the Idea Room sidebar status indicator to "has content".
2. WHEN the Idea Room is entered THEN the system SHALL load the active lyrics version.
