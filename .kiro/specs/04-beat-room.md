# Spec 04 — Beat Room

## Overview

The Beat Room is where the instrumental comes to life. It starts from the musical fingerprint built in the Feel Lab, generates an initial beat, then allows the user to shape it — section by section, element by element — entirely through listening and conversation. No faders. No technical controls. Just: "the verse feels too empty" and the system responds.

The Beat Room also supports building a beat from scratch without a Feel Lab fingerprint (Beat First path), where the discovery happens here.

---

## Requirements

### R1 — Two Entry States

**Entry from Feel Lab (fingerprint exists)**
- The Beat Room loads with the fingerprint already set
- The system greets: "Your feel is ready. Want me to start building the beat, or do you want to describe anything specific first?"
- One action: "Build the beat" — triggers initial generation
- The user can also describe specific things first (instrument preferences, energy per section) before generating

**Entry without fingerprint (Beat First path)**
- The Feel Lab conversation happens here instead — abbreviated version
- The system asks: "Let's find the feel first. How do you want this song to move?"
- Once a direction is established, generation begins
- A simplified fingerprint is created and saved

### R2 — Initial Beat Generation
- Triggered by user instruction or "Build the beat" action
- MusicGen generates a full-length instrumental (~2–3 minutes based on a standard verse-chorus structure)
- The backend segments the result into sections: Intro, Verse, Chorus, Bridge/Hook, Outro
- Segmentation uses librosa onset/energy detection — not perfect, can be user-corrected
- Each section is stored as a separate stem
- A full assembled beat version is rendered from all section stems
- The assembled beat is stored as `beat_versions` record
- All stems stored in `beat_stems`
- The beat plays in the Beat Room: a simple waveform with a play button, sections labeled along a timeline

### R3 — Section Timeline
- A horizontal timeline shows the beat sections: Intro | Verse | Chorus | Verse | Chorus | Bridge | Outro
- Each section is a colored block proportional to its duration
- Clicking a section jumps playback to that point
- The currently playing section is highlighted
- Section labels can be renamed by the user (click to edit): "Second Verse," "Main Hook," etc.
- Sections can be reordered by dragging (no drag-and-drop library — use mouse events or a simple swap UI)
- Sections can be duplicated or removed

### R4 — Stem Layer View
- Each section has layers (stems): kick/drums, bass, melody, pads/atmosphere, etc.
- The layers are named in plain language (not "stem 1"), named by what they sound like
- The user can toggle layers on/off per section (mute a layer to hear the others)
- The user can never see raw audio files or waveforms per stem — only the assembled section plays
- Layer visibility is for understanding, not editing. The editing happens through conversation.

### R5 — Conversation-Driven Beat Editing
The conversation panel controls the beat. All of these must work:

- "The verse feels too empty" → system adds a layer to verse sections
- "The chorus needs to hit harder" → system increases energy/density on chorus sections
- "Remove the [instrument sound] from the bridge" → system mutes that layer in the bridge
- "The bass is too busy" → system reduces complexity/density on bass stem
- "Start fresh on the chorus" → system regenerates only the chorus section stems
- "Make the intro shorter" → system trims the intro section
- "Try a completely different beat" → generates a new beat version (old one preserved)
- "Go back to the first version" — restores a previous beat version

Every action creates a new version or modifies stems. The user can always go back.

### R6 — Element-by-Element Building (Alternative Approach)
Instead of generating the whole beat and refining, the user can build it up:
- "Start with just the drums" → generate a percussion-only beat
- "Add a bass line" → generate and layer a bass stem onto the existing drums
- "Now add something melodic" → add a melody/keys layer
- "Layer in some atmosphere" → add pads/texture layer

Each "add" is a separate generation call for that stem type only. The user hears it added in real time (once the job completes). This approach is conversational — no UI for adding stems, just the conversation.

### R7 — Beat Versions
- Every significant change creates a new beat version record
- Beat versions are listed in a collapsible "Versions" panel: "Beat v1," "Beat v2," etc.
- Each version has a play button — the user can listen to any previous version
- "Use this version" sets it as the active beat
- Versions can be labeled by the user

### R8 — Sync with Vocal (Voice-First Path)
- If vocal takes exist (user came from the Voice Room), the Beat Room can play the vocal over the beat
- A "Hear it with my vocal" button loads the active vocal take and mixes it temporarily for preview
- This is not the final mix — just a preview to judge whether the beat fits the vocal
- The vocal is not mixed in permanently from here

### R9 — Backend: Beat Room Endpoints
- `POST /projects/{project_id}/beat/generate` — start full beat generation
  - Request: `{ fingerprint: object, duration_hint?: number }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/beat/generate-section` — regenerate a single section
  - Request: `{ section_id: string, fingerprint: object, instruction?: string }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/beat/add-stem` — add a stem layer to a section
  - Request: `{ section_id: string, stem_type: string, fingerprint: object }`
  - Response: `{ job_id: string }`
- `POST /projects/{project_id}/beat/conversation` — Beat Room conversation
  - Request: `{ message: string, beat_state: object, history: [...] }`
  - Response: `{ message: string, actions: [...] }`
- `GET /projects/{project_id}/beat/versions` — list all beat versions
- `POST /projects/{project_id}/beat/versions/active` — set active beat version
- `PATCH /projects/{project_id}/beat/sections/{section_id}` — update section label or order

### R10 — Backend: Beat Generation Pipeline
- `services/generation/musicgen.py` handles MusicGen calls
- For full beat: generate a full-length audio file, then segment
- For section regeneration: generate only that section duration with matching parameters
- For stem addition: generate only that instrument type at the right section length
- Segmentation uses librosa (`librosa.onset.onset_detect`, energy analysis)
- After generation and segmentation, assemble the beat version via FFmpeg overlay
- Store all stems and the assembled render in Supabase Storage

### R11 — Backend: Beat Conversation
- Beat Room system prompt: knows current beat state (which sections exist, which stems are in each, which version is active)
- Action types the LLM can emit:
  - `regenerate_section`: `{ section_id, instruction }`
  - `add_stem`: `{ section_id, stem_type }`
  - `mute_stem`: `{ section_id, stem_id, muted: bool }`
  - `reorder_sections`: `{ new_order: [section_id, ...] }`
  - `generate_full_beat`: `{ instruction }`
  - `restore_version`: `{ version_id }`
  - `set_section_label`: `{ section_id, label }`

---

## Design Notes

- The timeline is the heart of the Beat Room UI — it should feel alive, not like a progress bar
- The section colors should be consistent with Frank's palette: warm, not neon
- The Beat Room is where the user spends the most time. It needs to be robust and feel satisfying to work in.
- "Build the beat" should feel like pressing play for the first time — a moment of anticipation
- Generation takes time. Show something visually interesting, not a blank spinner. A waveform building, something that feels like the music is being made.

---

## Implementation Tasks

### Task 1 — Beat Room entry state
- [ ] Detect fingerprint presence on entry, show appropriate greeting
- [ ] "Build the beat" action button
- [ ] Beat First path: abbreviated Feel Lab conversation in the Beat Room

### Task 2 — Section timeline component
- [ ] `components/studio/BeatTimeline.tsx` — sections as colored blocks, playback scrubbing
- [ ] Section highlight on playback
- [ ] Section label editing
- [ ] Section reordering (swap UI)

### Task 3 — Stem layer view
- [ ] `components/studio/BeatLayers.tsx` — plain-language layer list per section
- [ ] Mute/unmute toggle (visual only — triggers backend call to re-render section)

### Task 4 — Beat versions panel
- [ ] Collapsible versions list
- [ ] Play each version
- [ ] Set active version
- [ ] Label editing

### Task 5 — Beat conversation
- [ ] Wire conversation to `POST /projects/{id}/beat/conversation`
- [ ] Handle all action types: regenerate, add stem, mute, reorder, restore
- [ ] Async job polling for generation actions
- [ ] "Hear it with my vocal" preview (if vocal exists)

### Task 6 — Backend: MusicGen pipeline
- [ ] Full beat generation with segmentation
- [ ] Section-only regeneration
- [ ] Stem-only generation
- [ ] FFmpeg beat assembly
- [ ] Supabase Storage upload for all stems and renders

### Task 7 — Backend: Beat conversation route
- [ ] Beat Room system prompt
- [ ] LLM call with beat state context
- [ ] All action type handlers

### Task 8 — Backend: Beat persistence
- [ ] `beat_versions` and `beat_stems` records created correctly
- [ ] `project_active_state.active_beat_version_id` updated
- [ ] Sidebar status indicator updates
