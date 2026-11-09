# Feel Lab — Requirements

## Introduction

The Feel Lab is where a song finds its emotional and musical identity. The user never touches a technical parameter — they describe feelings, react to sounds, and optionally hum. The system listens, asks sensory questions, plays short textures, and builds a musical fingerprint that seeds everything in the Beat Room. This spec covers the two input modes, texture generation, hum analysis, the progressive fingerprint, the async job system, and return-visit handling. It traces to `feel-lab.md`, `conversation-layer.md`, and `audio-architecture.md`.

Note on generation: textures are produced by Frank's own procedural engine (FluidSynth + SoundFont), not MusicGen. During build we confirmed there is no free hosted path to MusicGen, and the procedural engine fits the "controllable, not one-shot" vision better. See `tech.md`.

## Requirements

### Requirement 1 — Two Coexisting Input Modes

**User Story:** As a non-musician, I want to either talk about a feeling or hum one, so that I can reach a direction whichever way is natural to me.

#### Acceptance Criteria

1. THE SYSTEM SHALL support a conversation + texture-listening mode where the user describes or reacts and the system plays a short texture and waits.
2. WHEN the user reacts to a texture THEN the system SHALL either generate a new texture or refine the current direction.
3. WHEN the user asks for another option THEN the system SHALL generate a different texture.
4. THE SYSTEM SHALL provide a prominent "Hum it" control that records a hum in-browser.
5. WHEN a hum is recorded THEN the system SHALL analyze it and respond in plain language describing what it heard.
6. THE SYSTEM SHALL allow both modes to be used in the same session.

### Requirement 2 — Texture Playback

**User Story:** As a user, I want each sound to arrive and play on its own, so that reacting feels like a conversation rather than operating a tool.

#### Acceptance Criteria

1. THE SYSTEM SHALL play textures inline with no new page or modal, showing a waveform and a play/pause control when ready.
2. WHEN a texture becomes ready THEN the system SHALL auto-play it once, loop once, and stop, with a visible mute option.
3. WHILE a texture is generating THE SYSTEM SHALL show "Finding a sound..." and allow the conversation to continue.
4. THE SYSTEM SHALL keep played textures in the conversation history and allow replay on click.

### Requirement 3 — Progressive Musical Fingerprint

**User Story:** As a user, I want the system to quietly figure out the musical details, so that I never have to name a tempo, key, or genre.

#### Acceptance Criteria

1. THE SYSTEM SHALL build the fingerprint progressively across exchanges and SHALL NOT show it to the user.
2. THE SYSTEM SHALL merge fingerprint updates after each exchange, accumulating list-valued fields rather than overwriting them.
3. WHEN a texture is approved THEN the system SHALL set `reference_texture_id`.
4. WHERE a hum was recorded THE SYSTEM SHALL set `hum_reference_file`.
5. WHEN the user signals approval THEN the system SHALL offer to take the direction to the Beat Room or keep exploring.
6. WHEN a direction is approved THEN the system SHALL save the fingerprint to `feel_fingerprints` and set `project_active_state.active_fingerprint_id`.
7. THE SYSTEM SHALL clamp normalized fingerprint fields (energy, density, brightness, warmth) to the range 0–1.

### Requirement 4 — Revisiting the Feel Lab

**User Story:** As a returning user, I want the Feel Lab to remember where we landed, so that I can continue or deliberately start fresh.

#### Acceptance Criteria

1. IF a fingerprint already exists THEN the system SHALL open the Feel Lab with it loaded and greet the user with a plain-language summary of what was established.
2. WHEN the user chooses to keep going THEN the system SHALL continue from the existing fingerprint and conversation.
3. WHEN the user chooses to start fresh THEN the system SHALL create a new fingerprint session and SHALL preserve the old one.

### Requirement 5 — Feel Lab API

**User Story:** As a developer, I want Feel Lab endpoints for conversation, texture, hum, and fingerprint, so that the room is fully backed by the server.

#### Acceptance Criteria

1. WHEN `POST /projects/{project_id}/feel/conversation` is called with message, fingerprint, and history THEN the system SHALL return `{ message, fingerprint_update, actions }` where actions include `generate_texture` and `approve_direction`.
2. WHEN `POST /projects/{project_id}/feel/texture` is called with a fingerprint THEN the system SHALL return a `job_id` for an async job.
3. WHEN `GET /jobs/{job_id}/status` is called THEN the system SHALL return the job status, and on completion the result including `audio_url`.
4. WHEN `POST /projects/{project_id}/feel/hum` receives an audio upload THEN the system SHALL return `{ analysis: { description, fingerprint_hints }, audio_url }`.
5. WHEN `POST /projects/{project_id}/feel/fingerprint` is called THEN the system SHALL save the fingerprint and conversation summary and return the saved record.

### Requirement 6 — Texture Generation (Procedural Engine)

**User Story:** As the product, I want atmospheric textures generated from the fingerprint on CPU for free, so that a non-musician hears a direction without any paid or GPU dependency.

#### Acceptance Criteria

1. THE SYSTEM SHALL build the generating parameters from the fingerprint and render an 8–12 second atmospheric texture via the procedural engine (FluidSynth + SoundFont).
2. THE SYSTEM SHALL run generation as an async job: create an `async_jobs` record, return a job id, and update it on completion.
3. THE SYSTEM SHALL store generated audio in Supabase Storage under `textures/` as MP3.
4. WHERE a deterministic `cache_key` for the generating params already has a texture THE SYSTEM SHALL reuse the cached texture.

### Requirement 7 — Hum Analysis

**User Story:** As a user, I want my hum understood in feeling terms, so that the first textures already point the right way.

#### Acceptance Criteria

1. WHEN a hum is uploaded THEN the system SHALL convert it to WAV via FFmpeg.
2. THE SYSTEM SHALL detect the pitch contour via librosa `pyin` and the tempo via librosa, rather than Basic Pitch.
3. THE SYSTEM SHALL produce a plain-language description of what was heard and extract fingerprint hints (approximate tempo, energy, mood direction).
4. THE SYSTEM SHALL store the hum under `hums/`.

### Requirement 8 — Async Job System

**User Story:** As a user, I want long generation to never freeze the room, so that I can keep working while a sound is prepared.

#### Acceptance Criteria

1. THE SYSTEM SHALL back long operations with the `async_jobs` table and process them out of the request path.
2. WHEN the frontend polls every 2 seconds and the job is complete THEN the system SHALL return the result and the UI SHALL update.
3. IF a job fails THEN the system SHALL mark it failed and the UI SHALL show a friendly error with a retry option.
4. THE SYSTEM SHALL guard job-status writes so a failure is recorded rather than leaving the job stuck silently.
