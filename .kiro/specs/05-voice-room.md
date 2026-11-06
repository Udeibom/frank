# Spec 05 — Voice Room

## Overview

The Voice Room is the most personal layer. The user records their vocal — as many takes as they need — and the system handles the technical work: pitch analysis, pitch correction (with their control), vocal comping from multiple takes, and harmony layering. The user never needs to know what pitch correction is. They just need to hear their voice in the song.

---

## Requirements

### R1 — Recording Setup
- On entering the Voice Room, the system checks for microphone permission
- If no permission: show a clear, warm explanation of why Frank needs the mic, and a button to grant access
- Headphone detection: attempt to detect if audio output is via headphones
  - If headphones confirmed: proceed silently
  - If unknown/not headphones: show a friendly banner: "Tip: use headphones while recording so the beat doesn't get picked up by your mic"
  - Never block recording — just inform
- The beat (if it exists) is shown as a waveform reference — the user can choose to hear it while recording
- "Record with beat" plays the beat through headphones while recording
- "Record without beat" records in silence

### R2 — Multi-Take Recording
- A large, unmistakable record button — clear red when recording
- During recording:
  - Live mic level meter (visual feedback that the mic is working)
  - Beat plays in background if "Record with beat" was selected
  - Recording timer shown
  - A "Stop" button ends the recording
- Each completed take is shown as a card: waveform, duration, timestamp, label
- Takes are never deleted unless the user explicitly chooses to delete one
- The user can record as many takes as they want
- A take can be re-recorded (starts a new take, doesn't overwrite the old one)
- Takes can be labeled: "Take 3 - best chorus"

### R3 — Take Comparison
- The user can select two takes and compare them side by side
- "Compare" mode: both waveforms shown, each with its own play button
- A "play both alternating" mode: plays Take A from the start, then Take B from the same position, switching every 4 bars
- The user can set either take as the active vocal

### R4 — Pitch Analysis and Display
- After every take upload, the backend runs Basic Pitch and stores the pitch data
- The Voice Room shows a simple pitch visualization for the active take:
  - A color-coded line over the waveform: green = in tune, yellow = slightly off, red = noticeably off
  - No note names, no frequencies — just color. The user sees where the rough patches are.
- The pitch display is optional — the user can hide it if it's distracting

### R5 — Pitch Correction (Three Modes)
- Available after a take is recorded
- Presented as three options in plain language:
  - "Just the obvious mistakes" — light correction, natural feel preserved
  - "Tighten it up" — moderate correction, still sounds like them
  - "Lock it in" — full correction, very polished/produced sound
- Applying correction creates a new processed take — the original is always preserved
- After applying, the corrected take appears as a new card with a "(tuned)" label
- The user can compare original vs corrected before deciding which to use
- Correction is applied as an async job (Rubber Band Library via pyrubberband)

### R6 — Vocal Comping
- Available when the user has 2+ takes
- "Put together the best version" in the conversation panel triggers vocal comp
- The system analyzes all takes for pitch confidence, energy, and consistency
- It assembles a comp: best segments from each take stitched together
- The comp is presented in the conversation: "I put together a version using the best moments from your 3 takes — want to hear it?"
- A waveform shows the comp with colored segments indicating which take each segment came from
- The user can:
  - Accept the comp as-is
  - Ask for adjustments: "Use my Take 2 for the chorus"
  - Start over
- The comp is stored as a `vocal_comps` record

### R7 — Harmony Layering
- "Add a harmony" in the conversation panel triggers harmony generation
- The system generates a harmony vocal part based on the active vocal and the musical fingerprint (key/mode)
- Harmony is generated server-side using pitch shifting (Rubber Band) to create a third or fifth above/below the melody
- The harmony is a derived audio file — it does not require another recording from the user
- The user can choose the harmony type: "higher harmony," "lower harmony," "both"
- All presented in plain language — no interval names
- Harmony is stored as a stem and passed to the Mix Room
- The user can turn the harmony on/off in the Mix Room

### R8 — Vocal Effects Preview
- Three effect presets available in plain language (applied non-destructively):
  - "Add a little space" — light reverb
  - "Smooth it out" — gentle compression
  - "Warm it up" — gentle saturation + EQ low boost
- Effects are applied as an async job and return a new processed take for comparison
- These are preview/reference effects — full effects control is in the Mix Room

### R9 — Backend: Voice Room Endpoints
- `POST /projects/{project_id}/voice/takes` — upload a new vocal take (multipart)
  - Returns: `{ take_id: string, audio_url: string }` immediately, triggers pitch analysis async job
- `GET /projects/{project_id}/voice/takes` — list all takes with their pitch data
- `DELETE /projects/{project_id}/voice/takes/{take_id}` — soft delete (sets deleted flag, file kept)
- `POST /projects/{project_id}/voice/takes/{take_id}/correct` — apply pitch correction
  - Request: `{ mode: "light" | "moderate" | "full" }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/voice/comp` — generate vocal comp from takes
  - Request: `{ take_ids: string[], instruction?: string }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/voice/harmony` — generate harmony
  - Request: `{ take_id: string, type: "above" | "below" | "both", fingerprint: object }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/voice/conversation` — Voice Room conversation
- `POST /projects/{project_id}/voice/active` — set active vocal (take or comp)

### R10 — Backend: Pitch Processing
- `services/audio/pitch.py`:
  - Run Basic Pitch on uploaded WAV
  - Store pitch contour as JSON: `[{ time: float, note: int, confidence: float }, ...]`
  - Color-code data: confidence > 0.8 = green, 0.5-0.8 = yellow, < 0.5 = red
- `services/audio/pitch.py` apply_correction:
  - Three correction strengths mapped to Rubber Band pyrubberband pitch shift amounts
  - Segment-by-segment correction based on pitch contour
  - Return corrected WAV

### R11 — Backend: Vocal Comp
- `services/audio/comp.py`:
  - Score each segment of each take by pitch confidence + energy
  - Build optimal segment sequence
  - FFmpeg concat to assemble comp audio
  - Return segment list (for visualization) and assembled audio URL

### R12 — Backend: Harmony Generation
- `services/audio/harmony.py`:
  - Use pitch data from the active take to understand the melody
  - Use fingerprint key/mode to determine appropriate harmony intervals
  - Apply pitch shift via pyrubberband to create harmony vocal
  - Level-match the harmony to the original vocal

---

## Design Notes

- The record button is the centerpiece of this room. It should feel significant — not a small icon.
- The mic level meter gives the user confidence their mic is working before they commit to a take.
- The color-coded pitch visualization is feedback, not judgment. The user should feel informed, not criticized.
- When the system offers a comp, it should feel like a gift: "I put something together — want to hear it?" Not a task to complete.
- Harmony generation is magic — the user didn't have to sing a harmony and they get one. Let the UI moment reflect that.

---

## Implementation Tasks

### Task 1 — Microphone setup
- [ ] Microphone permission request flow
- [ ] Headphone detection (best effort, non-blocking)
- [ ] `hooks/useRecorder.ts` — reusable recording hook (build on Spec 02 voice memo recorder)

### Task 2 — Recording UI
- [ ] `components/audio/VocalRecorder.tsx` — record button, timer, level meter, stop
- [ ] Beat playback sync during recording
- [ ] Take card component: waveform, duration, label, play button

### Task 3 — Take management
- [ ] Take list with comparison mode
- [ ] Alternating playback comparison
- [ ] Label editing
- [ ] Set active take

### Task 4 — Pitch visualization
- [ ] `components/audio/PitchDisplay.tsx` — color overlay on waveform
- [ ] Fetch pitch data after take upload
- [ ] Show/hide toggle

### Task 5 — Pitch correction
- [ ] Three-option selector in the conversation and as UI buttons
- [ ] Async job for correction, show result as new take card
- [ ] Original vs corrected comparison

### Task 6 — Vocal comp
- [ ] Trigger from conversation: "Put together the best version"
- [ ] Comp waveform with colored segments
- [ ] Accept/adjust/redo comp options

### Task 7 — Harmony
- [ ] Trigger from conversation: "Add a harmony"
- [ ] Higher/lower/both options
- [ ] Harmony stored as a stem for Mix Room

### Task 8 — Effects preview
- [ ] Three effect presets as conversation options
- [ ] Async processing, return new take for comparison

### Task 9 — Backend: all Voice Room routes
- [ ] Upload, pitch analysis async job
- [ ] Pitch correction async job
- [ ] Comp generation async job
- [ ] Harmony generation async job
- [ ] Conversation route with Voice Room system prompt

### Task 10 — Active state and sidebar
- [ ] `project_active_state.active_vocal_id` and `active_comp_id` updated
- [ ] Sidebar status indicator updates
