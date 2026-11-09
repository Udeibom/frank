# Idea Room — Design

## Overview

The Idea Room pairs a debounced, auto-saving lyrics editor with an LLM co-writer and a voice-memo capture path. The core design principle from `conversation-layer.md` is that the co-writer offers, never overwrites: it is a collaborator leaning over the page, not an author. From `project-layer.md`: every differing save is a kept version, and restore is additive.

## Architecture

```
LyricsEditor ──debounced save──▶ POST /lyrics ──▶ db/lyrics ──▶ lyrics_versions
     │                                                      └──▶ project_active_state.active_lyrics_id
ConversationPanel ──▶ POST /conversation/idea ──▶ llm (Groq) ──▶ { message, actions }
MicButton ──▶ POST /lyrics/voice-memo ──▶ FFmpeg→WAV ──▶ Groq Whisper ──▶ { transcription, audio_url }
                                                       └──▶ Storage voice-memos/
```

## Components and Interfaces

### Frontend
- `components/studio/LyricsEditor.tsx` — controlled textarea, 2s debounced save, section-label friendly.
- `components/studio/LyricsVersionHistory.tsx` — version list, read-only preview, restore, label editing.
- Conversation panel wired to the Idea Room endpoint; renders `suggest_lyrics` blocks with Add/Ignore.
- A reusable recorder hook (MediaRecorder) shared later with the Feel Lab hum feature.

### Backend
- `routers/lyrics.py` — the five lyrics routes plus the voice-memo route.
- `routers/conversation.py` — the `/conversation/idea` route.
- `services/llm/groq_client.py` — single source of the model name (`openai/gpt-oss-120b`).
- `services/llm/prompts.py` — the Idea Room system prompt.
- `services/storage/files.py` — Supabase Storage upload (and signed URLs for later).
- `db/lyrics.py` — version create/list/get/label, active-pointer update, dedup check.

## Data Models

Uses `lyrics_versions` (id, project_id, content, label, created_at) and the `active_lyrics_id` pointer on `project_active_state`. Restore writes a new row rather than mutating; this is the version-history rule made concrete.

Design decision — transcription provider: the original plan was Hugging Face Whisper, but HF retired the `api-inference.huggingface.co` domain. Groq already hosts `whisper-large-v3-turbo` and is our LLM provider, so transcription runs through Groq. This is captured in `tech.md`.

## Error Handling

- Dedup: `get_latest_version` compares content before inserting; identical content is a no-op save.
- Transcription failures return a plain-language error the panel can show ("I couldn't quite catch that — want to try again?").
- The co-writer always returns a `message`; an empty `actions` array is valid.

## Testing Strategy

- Manual: write lyrics, confirm auto-save and a new version per change, restore an old version, label a version.
- Co-writer: verify it suggests without overwriting and that "Add to editor" appends.
- Voice memo: record, confirm transcription appears in chat and is not auto-inserted.

## Deferred (tracked)

1. Cross-session conversation persistence + summarization — built once as a reusable mechanism when the Feel Lab adds the second conversation surface, rather than a one-off here.
2. Lyrics dedup tie-break — `created_at DESC` could tie on same-tick saves; the 2s debounce makes this very unlikely. Add a monotonic sequence column only if it surfaces.
3. Private storage + signed URLs for voice memos — switch user buckets to private with `create_signed_url` when auth + RLS land (Auth spec).
