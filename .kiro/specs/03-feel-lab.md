# Spec 03 — Feel Lab

## Overview

The Feel Lab is where the song finds its emotional and musical identity. The user never touches a technical parameter. They describe feelings, react to sounds, and optionally hum. The system listens, asks questions, plays textures, and builds a musical fingerprint. That fingerprint becomes the seed for everything in the Beat Room.

This spec builds the complete Feel Lab: texture generation, humming input, the fingerprint system, and the conversational feel discovery.

---

## Requirements

### R1 — Two Input Modes (Coexisting)

**Mode A: Conversation + Texture Listening**
- The user describes the feeling they want or reacts to what they hear
- The system plays short textures (8–12 seconds) and waits for a reaction
- Reactions can be anything: "too dark," "more energy," "warmer," "close but not quite," "yes, that"
- After each reaction, the system either generates a new texture or refines the current direction
- The user can request another texture at any time: "try something else"

**Mode B: Humming**
- A prominent "Hum it" button lets the user record a hum
- The hum is uploaded, analyzed, and the system responds in plain language: "I hear something slow and melancholic — like it's sitting still. Let me find some sounds that go in that direction."
- The system generates 2-3 textures based on the hum analysis
- The user can then use Mode A to refine from there
- Both modes can be used in the same session

### R2 — Texture Playback
- Textures play inline — no new page, no modal
- A waveform and play/pause button appear when a texture is ready
- The texture plays automatically once generated (with a mute option visible)
- Duration: 8–12 seconds, then loops once and stops
- While a texture is generating: "Finding a sound..." with an animated indicator — the user can keep talking in the conversation
- After playing, the conversation continues: "How does that feel?"
- The user can replay any texture from the conversation history by clicking it

### R3 — Musical Fingerprint Construction
- The fingerprint is built progressively as the conversation evolves
- It is never shown to the user
- The LLM translator updates it after each exchange:
  - First message might only fill `energy_level` and `tempo_feel`
  - After a few exchanges, `key`, `mode`, `genre_proximity` fill in
  - When a texture is approved, `reference_texture_id` is set
  - If a hum was recorded, `hum_reference_file` is set
- The fingerprint is "ready" when the user signals a direction is right — they say something like "yes," "that's it," "I like that," "let's go with this"
- The system detects approval signals and asks: "Great — want to take this direction to the Beat Room, or explore a little more?"
- The fingerprint is saved to `feel_fingerprints` and linked in `project_active_state`

### R4 — Revisiting the Feel Lab
- If a fingerprint already exists for the project, the Feel Lab opens with it loaded
- The system greets the user with a summary of what was established: "Last time we landed on something warm and slow — a quiet late-night feeling. Want to keep going from here, or try something different?"
- "Keep going" — continues from the existing fingerprint and conversation
- "Try something different" — creates a new fingerprint session (old one is preserved, not deleted)
- If the fingerprint changes significantly on a return visit, the Beat Room is flagged: the system notifies when the user navigates there: "Your feel has changed — the beat might need to catch up. Want to update it?"

### R5 — Backend: Feel Lab Endpoints
- `POST /projects/{project_id}/feel/conversation` — send a message to the Feel Lab
  - Request: `{ message: string, fingerprint: object, history: [...] }`
  - Response: `{ message: string, fingerprint_update: object, actions: [...] }`
  - Action types: `generate_texture`, `approve_direction`
- `POST /projects/{project_id}/feel/texture` — generate a texture from a fingerprint
  - Request: `{ fingerprint: object }`
  - Response: `{ job_id: string }` (async job)
- `GET /jobs/{job_id}/status` — poll for async job status
  - When complete: `{ status: "complete", result: { audio_url: string } }`
- `POST /projects/{project_id}/feel/hum` — upload and analyze a hum
  - Multipart audio upload
  - Returns: `{ analysis: { description: string, fingerprint_hints: object }, audio_url: string }`
- `POST /projects/{project_id}/feel/fingerprint` — save the final fingerprint
  - Request: `{ fingerprint: object, conversation_summary: string }`
  - Response: the saved fingerprint record

### R6 — Backend: Texture Generation
- Build a MusicGen prompt from the fingerprint (handled by `services/generation/fingerprint.py`)
- The prompt is minimal and atmospheric — not a detailed arrangement description
- Call MusicGen via Hugging Face Inference API or Replicate (whichever is available)
- Generation is async: create an `async_jobs` record, return job_id, update when done
- Generated audio stored in Supabase Storage under `textures/`
- Cache: if the same fingerprint hash has been used before and produced a texture, return the cached URL

### R7 — Backend: Hum Analysis
- Convert hum audio to WAV via FFmpeg
- Run Basic Pitch to extract pitch contour
- Run librosa for tempo detection
- Build a plain-language description of what was heard (sent to LLM for phrasing)
- Extract fingerprint hints: approximate tempo, mood direction, energy level
- Store hum audio in Supabase Storage under `hums/`

### R8 — Async Job System
- `async_jobs` table (already in the schema from Spec 01)
- Backend creates a job record, starts processing in a background thread/task
- Frontend polls `GET /jobs/{job_id}/status` every 2 seconds
- When `status == "complete"`, frontend receives the result and updates the UI
- When `status == "failed"`, frontend shows a friendly error and offers to retry
- Job types in this spec: `generate_texture`, `analyze_hum`

---

## Design Notes

- The Feel Lab should feel like the most intimate space in Frank — this is where the user digs into what the song actually feels like. The UI should be quiet and patient.
- The texture waveform that appears should feel like something alive — it just arrived, it's ready to play.
- The "Hum it" button should be easy to find but not demanding. Some users won't use it. That's fine.
- The fingerprint approval moment should feel significant — "Great — let's go." Not a form submission.
- If a texture takes 30 seconds to generate, that's okay — the conversation can continue and the texture appears when ready, like a message arriving.

---

## Implementation Tasks

### Task 1 — Feel Lab conversation
- [ ] Wire conversation panel to `POST /projects/{id}/feel/conversation`
- [ ] Handle `generate_texture` action: show "Finding a sound..." then display texture when job completes
- [ ] Handle `approve_direction` action: show confirmation message, update fingerprint in state
- [ ] Poll job status for texture generation

### Task 2 — Texture playback component
- [ ] `components/audio/TexturePlayer.tsx` — waveform + play/pause, auto-play on arrival, loops once
- [ ] Texture cards appear in the conversation history, are replayable
- [ ] "Finding a sound..." animated state

### Task 3 — Hum recording
- [ ] "Hum it" button in the Feel Lab
- [ ] Reuse the recorder hook from Spec 02
- [ ] Upload to `POST /projects/{id}/feel/hum`
- [ ] Display analysis result in conversation

### Task 4 — Fingerprint state management
- [ ] Update project store with fingerprint as it evolves
- [ ] Save fingerprint to backend on approval
- [ ] Load existing fingerprint on Feel Lab entry

### Task 5 — Backend: Feel Lab conversation route
- [ ] Feel Lab system prompt in `services/llm/prompts.py`
- [ ] LLM call with fingerprint context
- [ ] Fingerprint update extraction from LLM response
- [ ] Structured output parsing

### Task 6 — Backend: MusicGen texture generation
- [ ] `services/generation/fingerprint.py` — fingerprint to MusicGen prompt
- [ ] `services/generation/musicgen.py` — MusicGen API call (HF or Replicate)
- [ ] Async job creation and execution
- [ ] Supabase Storage upload
- [ ] Cache check before generating

### Task 7 — Backend: hum analysis
- [ ] FFmpeg conversion
- [ ] Basic Pitch analysis
- [ ] librosa tempo detection
- [ ] LLM plain-language description
- [ ] Return fingerprint hints

### Task 8 — Backend: fingerprint persistence
- [ ] `POST /projects/{id}/feel/fingerprint` saves to `feel_fingerprints`
- [ ] Updates `project_active_state.active_fingerprint_id`
- [ ] Sidebar status indicator updates to "has content"

### Task 9 — Return visit handling
- [ ] Detect existing fingerprint on Feel Lab entry
- [ ] Load conversation summary and fingerprint
- [ ] Opening message from system summarizing what was established
