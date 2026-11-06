# Spec 06 — Mix Room

## Overview

The Mix Room is where everything comes together. The vocal, the beat, and the harmonies are combined into a single song. The user controls the mix entirely through listening and conversation — no faders, no sliders, no technical controls visible. The system makes adjustments, renders a preview, and the user reacts until it sounds right.

---

## Requirements

### R1 — Mix Assembly
- On entering the Mix Room, the system takes stock of what exists:
  - Active vocal (take or comp)
  - Harmony stems (if generated)
  - Active beat version (all sections assembled)
- If both vocal and beat exist: auto-assemble an initial mix and play it
- If only one exists: show what's available and explain what's missing
- Initial mix uses default gain levels: vocal at 0dB, beat at -6dB relative (to give vocal prominence)
- The system greets: "Here's how it sounds. What do you think?"

### R2 — Mix Conversation
All mix control happens here. The user describes what they hear, the system adjusts:

- "The vocals feel buried" → raise vocal gain, reduce beat gain slightly
- "The beat is too loud" → lower beat gain
- "It sounds muddy" → high-pass filter on the beat, slight clarity boost on vocal
- "I want more warmth" → gentle saturation on vocal, warm EQ on beat
- "The chorus should be bigger" → increase gain/energy on chorus sections
- "Something feels off but I don't know what" → system analyzes and suggests: "The beat feels a bit heavy in the low end — want me to clean that up?"
- "Add more space" → reverb on vocal
- "The drop needs to hit harder" → compression + gain on the drop section

Every adjustment renders a new mix preview (async). The user listens and reacts.

### R3 — Mix Versions
- Every mix adjustment creates a new mix version
- Mix versions panel (collapsible): "Mix v1," "Mix v2," etc.
- Each version: play button, timestamp, label, current params visible as plain text summary ("vocals louder, more warmth")
- Set any version as active
- Label any version

### R4 — Mix Preview vs Full Render
- **Preview render**: fast, 64kbps MP3, available in ~10-15 seconds
  - Used for all listening during the mix conversation
  - Waveform shown, duration shown, play/pause
- **Full render**: 44.1kHz WAV → MP3 320kbps, takes 30-60 seconds
  - Triggered explicitly: "Render the full quality version"
  - Used for export

### R5 — Individual Section Control
- The conversation can reference sections: "Make the chorus louder than the verses"
- Section-level gain adjustments are stored per section in mix_params
- The mix render applies per-section adjustments

### R6 — Stem Balance View
- A read-only panel shows what stems are in the mix:
  - Vocal (main)
  - Harmony (if exists, with on/off toggle)
  - Beat (assembled)
- The user can turn harmony on/off directly here (not just via conversation)
- No gain sliders — the numbers stay hidden. The toggle is the only direct control.

### R7 — Mix Room Conversation
Action types the Beat Room LLM can emit:
- `adjust_levels`: `{ vocal_gain_db: float, beat_gain_db: float }`
- `apply_effect`: `{ target: "vocal"|"beat"|"harmony", effect: string, params: object }`
- `section_adjust`: `{ section_id: string, gain_db: float }`
- `render_preview`: `{}` — triggers a preview render
- `analyze_mix`: `{}` — system analyzes the current mix and describes what it hears

### R8 — Backend: Mix Room Endpoints
- `POST /projects/{project_id}/mix/render` — render a mix version
  - Request: `{ mix_params: object, quality: "preview" | "full" }`
  - Response: `{ job_id: string }`
- `GET /projects/{project_id}/mix/versions` — list mix versions
- `POST /projects/{project_id}/mix/versions/active` — set active mix version
- `POST /projects/{project_id}/mix/conversation` — Mix Room conversation

### R9 — Backend: Mix Rendering
- `services/audio/mixing.py`:
  - Load vocal stem, harmony stems, beat stems
  - Apply gain levels from mix_params
  - Apply effects from mix_params using pedalboard
  - FFmpeg overlay all stems into a single audio file
  - For preview: output 64kbps MP3
  - For full: output WAV, then convert to MP3 320kbps
- Section-level rendering: apply per-section params before global mix

### R10 — Backend: Mix Analysis
- `services/audio/mixing.py` analyze function:
  - Run basic audio analysis on the current mix render: frequency balance, dynamic range, vocal prominence
  - Translate findings to plain language for the LLM to use in its response
  - Never surface raw analysis numbers to the user

---

## Design Notes

- The Mix Room is the closest to "done" — the user can feel the finish line from here
- The initial auto-mix should sound decent from the start — the defaults matter
- "Something feels off but I don't know what" is a real scenario and the system must handle it gracefully — analyze and suggest, don't ask the user to be more specific
- The preview render progress should feel fast and light — it's a quick listen, not a production step
- When the full render completes, it should feel like a milestone: "Your song is ready to export."

---

## Implementation Tasks

### Task 1 — Mix assembly on entry
- [ ] Detect available stems on entry
- [ ] Auto-assemble and play initial mix
- [ ] Missing stems notification (if beat or vocal absent)

### Task 2 — Mix conversation
- [ ] Wire conversation to `POST /projects/{id}/mix/conversation`
- [ ] Handle all action types
- [ ] Trigger preview render after adjustment actions
- [ ] Show render progress and play result

### Task 3 — Mix versions panel
- [ ] Collapsible versions list
- [ ] Play each version, set active, label

### Task 4 — Stem balance view
- [ ] Read-only stem list
- [ ] Harmony on/off toggle

### Task 5 — Backend: mix rendering pipeline
- [ ] `services/audio/mixing.py` with FFmpeg overlay
- [ ] pedalboard effects chain
- [ ] Preview (fast) vs full quality render
- [ ] Async job for rendering

### Task 6 — Backend: mix conversation
- [ ] Mix Room system prompt
- [ ] Mix analysis function
- [ ] All action type handlers

### Task 7 — Active state and sidebar
- [ ] `project_active_state.active_mix_id` updated
- [ ] Sidebar status indicator updates
