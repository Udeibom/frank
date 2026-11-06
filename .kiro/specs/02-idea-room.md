# Spec 02 — Idea Room

## Overview

The Idea Room is where a song starts. It is a lyrics editor with an AI co-writer that thinks like a songwriter. The user writes, the system assists — but the user is always the author. Every version of the lyrics is saved automatically. Nothing is ever overwritten.

This spec builds the complete Idea Room: the editor, the co-writer conversation, lyric version history, and the backend endpoints that power it.

---

## Requirements

### R1 — Lyrics Editor
- A clean, distraction-free text editor for writing lyrics
- Full-screen feel — the editor takes up the main content area
- Font is readable and slightly larger than body text — this is writing, not coding
- The editor auto-saves after 2 seconds of inactivity (debounced)
- The editor supports basic structure markers: the user can label sections (Verse, Chorus, Bridge, Hook, Outro) — these are plain text labels, not special formatting
- No word count, no character limit, no grammar checking overlays
- The editor is a textarea or a controlled rich-text component — not a code editor

### R2 — Lyric Version History
- Every auto-save that differs from the previous version creates a new lyrics_version record
- A version history panel (collapsible, on the right or as a slide-over) lists all versions by timestamp
- Each version shows: timestamp, first line of the lyrics, and an optional label
- The user can click any version to preview it (read-only side-by-side with current)
- The user can "restore" any version — this creates a new version from the old content, does not delete the current
- The user can label any version: click the timestamp, type a label, press Enter
- The active version is the most recently saved one by default

### R3 — AI Co-Writer (Conversation Panel)
- The conversation panel is present in the Idea Room as defined in `design-and-ui.md`
- The co-writer knows the current lyrics at all times (passed as context)
- Capabilities the user can invoke through conversation:
  - "Help me with this line" — user selects a line in the editor, asks for suggestions
  - "I need a rhyme for [word]" — returns rhyme options
  - "This verse feels off — what do you think?" — system responds to the feeling, offers alternatives
  - "Write me a chorus for this theme" — system drafts a chorus as a suggestion in the conversation, not injected into the editor
  - "How does this flow?" — system comments on meter and rhythm in plain language (no "iambic pentameter" — "this line feels rushed compared to the others")
- The system NEVER rewrites the user's lyrics without explicit instruction
- When the system drafts lyrics, they appear in the conversation as a block. The user has two options: "Add to editor" or "Ignore"
- "Add to editor" appends the draft to the current lyrics as a new section, does not replace

### R4 — Lyric Structure Awareness
- The system can recognize when lyrics have sections (based on the user labeling them or based on typical patterns like repeated lines)
- It can reference sections by name: "Your chorus is strong — the second verse feels like it needs more energy"
- Section awareness feeds into the Beat Room later (verse sections map to beat sections)

### R5 — Voice Memo Input
- A microphone button in the Idea Room allows the user to record a voice memo
- The voice memo is uploaded to the backend, transcribed via Whisper, and the transcription appears in the conversation: "Here's what I heard — want to add any of this to your lyrics?"
- The transcription is never automatically inserted into the editor
- The original audio is stored (will be useful for the Feel Lab humming feature)
- This is for capturing ideas, not for recording the final vocal

### R6 — Backend: Lyrics Endpoints
- `POST /projects/{project_id}/lyrics` — save a new lyrics version, returns the version id
- `GET /projects/{project_id}/lyrics` — list all lyrics versions for a project
- `GET /projects/{project_id}/lyrics/{version_id}` — get a specific version
- `PATCH /projects/{project_id}/lyrics/{version_id}` — update a version's label
- `POST /projects/{project_id}/lyrics/active` — set the active lyrics version

### R7 — Backend: Co-Writer Conversation Endpoint
- `POST /projects/{project_id}/conversation/idea` — send a message to the Idea Room co-writer
- Request body: `{ message: string, current_lyrics: string, selected_text?: string, history: [...] }`
- Response: structured JSON per the conversation layer spec — `{ message: string, actions: [...] }`
- The only action type in the Idea Room: `{ type: "suggest_lyrics", params: { content: string, section_label?: string } }`
- The backend builds the full prompt from: Idea Room system prompt + current lyrics + history + user message
- LLM call goes to Groq (Llama 3.3 70B)

### R8 — Backend: Voice Memo Transcription
- `POST /projects/{project_id}/lyrics/voice-memo` — accepts a multipart audio file upload
- Converts to WAV if needed via FFmpeg
- Calls Whisper via Hugging Face Inference API
- Stores the audio file in Supabase Storage under `voice-memos/`
- Returns: `{ transcription: string, audio_url: string }`

---

## Design Notes

- The Idea Room should feel like a notebook, not a form. Dark, quiet, spacious.
- The version history panel should feel like flipping through drafts — not a scary "version control" system.
- When the co-writer makes a suggestion, it should feel like a collaborator leaning over: low-key, offered, not pushed.
- The voice memo button is subtle — it's an option, not the main event. A small mic icon in a corner.
- There is no "Submit" or "Done" button. The user moves to the next layer when they're ready. The lyrics are always there.

---

## Implementation Tasks

### Task 1 — Lyrics editor
- [ ] Build the lyrics editor component (`components/studio/LyricsEditor.tsx`)
- [ ] Debounced auto-save (2 second delay)
- [ ] Wire to `POST /projects/{id}/lyrics` on save

### Task 2 — Version history
- [ ] Version history panel component (`components/studio/LyricsVersionHistory.tsx`)
- [ ] List versions from `GET /projects/{id}/lyrics`
- [ ] Preview mode (side-by-side comparison)
- [ ] Restore version action
- [ ] Label editing

### Task 3 — Co-writer conversation
- [ ] Wire the conversation panel to `POST /projects/{id}/conversation/idea`
- [ ] Handle the `suggest_lyrics` action — display suggestion block in chat with "Add to editor" / "Ignore"
- [ ] Pass selected text from editor to the conversation when relevant

### Task 4 — Voice memo
- [ ] Mic button in the Idea Room
- [ ] In-browser recording via MediaRecorder API (reusable recorder hook)
- [ ] Upload to `POST /projects/{id}/lyrics/voice-memo`
- [ ] Display transcription result in conversation panel

### Task 5 — Backend: lyrics routes
- [ ] All five lyrics endpoints implemented
- [ ] Auto-save deduplication (don't create a new version if content is identical to previous)

### Task 6 — Backend: co-writer
- [ ] Idea Room system prompt written and stored in `services/llm/prompts.py`
- [ ] Groq client call with structured output
- [ ] Conversation history management (last 20 turns, then summarize)

### Task 7 — Backend: voice memo transcription
- [ ] FFmpeg conversion to WAV
- [ ] Hugging Face Whisper API call
- [ ] Supabase Storage upload
- [ ] Return transcription and URL

### Task 8 — Active state
- [ ] Update `project_active_state.active_lyrics_id` when a new version is saved
- [ ] Idea Room loads the active lyrics version on entry
- [ ] Sidebar status indicator for Idea Room updates to "has content" when lyrics exist
