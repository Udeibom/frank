# Idea Room — Implementation Plan

- [x] 1. Lyrics editor
  - [x] 1.1 Build `components/studio/LyricsEditor.tsx` with 2s debounced auto-save
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 1.2 Wire the editor to `POST /projects/{id}/lyrics` on save
    - _Requirements: 6.1_

- [x] 2. Version history
  - [x] 2.1 Build `components/studio/LyricsVersionHistory.tsx` listing versions
    - _Requirements: 2.3_
  - [x] 2.2 Preview (side-by-side), restore, and label editing
    - _Requirements: 2.4, 2.5, 2.6_

- [x] 3. Co-writer conversation
  - [x] 3.1 Wire the conversation panel to `POST /projects/{id}/conversation/idea`
    - _Requirements: 3.1, 7.1_
  - [x] 3.2 Render `suggest_lyrics` blocks with "Add to editor" / "Ignore"
    - _Requirements: 3.4, 3.5, 7.2_
  - [x] 3.3 Pass editor-selected text into the conversation when relevant
    - _Requirements: 3.2_

- [x] 4. Voice memo
  - [x] 4.1 Subtle mic button and reusable MediaRecorder hook
    - _Requirements: 5.1_
  - [x] 4.2 Upload to `POST /projects/{id}/lyrics/voice-memo`, show transcription in chat
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 5. Backend: lyrics routes
  - [x] 5.1 Implement all five lyrics endpoints
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [x] 5.2 Auto-save dedup (skip identical content)
    - _Requirements: 2.1, 2.2_

- [x] 6. Backend: co-writer
  - [x] 6.1 Idea Room system prompt in `services/llm/prompts.py`
    - _Requirements: 7.3_
  - [x] 6.2 Groq call with structured output
    - _Requirements: 7.1, 7.3_

- [x] 7. Backend: voice memo transcription
  - [x] 7.1 FFmpeg conversion to WAV
    - _Requirements: 8.1_
  - [x] 7.2 Groq Whisper transcription and Storage upload
    - _Requirements: 8.2, 8.3_

- [x] 8. Active state and status
  - [x] 8.1 Update `active_lyrics_id` on save; load active lyrics on entry
    - _Requirements: 6.6, 9.2_
  - [x] 8.2 Sidebar status indicator reflects "has content"
    - _Requirements: 9.1_
