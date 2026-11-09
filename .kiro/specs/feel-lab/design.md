# Feel Lab — Design

## Overview

The Feel Lab turns a conversation (and optionally a hum) into a musical fingerprint, playing short atmospheric textures to confirm direction. The hard constraint from `tech.md` shapes the whole design: there is no free hosted MusicGen, so textures come from Frank's own procedural engine (music theory → MIDI → FluidSynth + SoundFont), rendered on CPU. This turns out to serve the product better — every texture is an explicit, controllable musical decision, not a black-box roll.

## Architecture

```
ConversationPanel ─▶ POST /feel/conversation ─▶ llm (Groq) ─▶ { message, fingerprint_update, actions }
   action: generate_texture
        └─▶ POST /feel/texture ─▶ async_jobs(pending) ─▶ BackgroundTask
                                        │  fingerprint → params → composer(MIDI) → renderer(FluidSynth) → MP3
                                        └─▶ Storage textures/ , job(complete, audio_url)
   poll ─▶ GET /jobs/{id}/status
HumButton ─▶ POST /feel/hum ─▶ FFmpeg→WAV ─▶ librosa pyin + tempo ─▶ { description, fingerprint_hints } , Storage hums/
Approve ─▶ POST /feel/fingerprint ─▶ feel_fingerprints , project_active_state.active_fingerprint_id
```

## Components and Interfaces

### Frontend
- `components/audio/TexturePlayer.tsx` — waveform + play/pause, auto-play once then loop-once-and-stop.
- Conversation panel wired to `/feel/conversation`; handles `generate_texture` (show "Finding a sound...", poll, then render the texture card) and `approve_direction` (confirmation + fingerprint commit).
- "Hum it" button reusing the recorder hook from the Idea Room.
- Project store holds the evolving fingerprint; it is loaded on entry if one exists.

### Backend
- `routers/feel.py` — conversation, texture, hum, fingerprint routes; `routers/jobs.py` — status polling.
- `services/generation/fingerprint.py` — fingerprint → generating params and the deterministic `cache_key`.
- `services/generation/theory.py` / `composer.py` / `renderer.py` — the procedural engine (shared with the Beat Room).
- `services/audio/` — librosa `pyin` pitch contour and tempo for hum analysis; FFmpeg conversion.
- `db/jobs.py`, `db/feel.py` — job lifecycle and fingerprint persistence.

## Data Models

- `feel_fingerprints` (project_id, fingerprint JSONB, conversation_summary).
- `texture_samples` (project_id, fingerprint_id, audio_url, `cache_key`, approved). `cache_key` is an indexed deterministic hash of generating params — it replaced the earlier fragile URL-substring cache.
- `async_jobs` (job_type `generate_texture` / `analyze_hum`, status, result, error).
- Fingerprint shape per `feel-lab.md`: tempo_bpm, tempo_feel, key, mode, energy_level, density, brightness, warmth, genre_proximity[], instrumentation_hints[], reference_texture_id, hum_reference_file.

Design decisions:
- **Procedural engine over MusicGen** — no free hosted path; CPU-only, no rate limits, controllable. (tech.md)
- **librosa pyin over Basic Pitch** — Basic Pitch pulls in TensorFlow (~500MB, neural), breaking the free-tier memory budget and the "no heavy local model" principle. pyin is accurate enough to describe a hum.
- **Accumulating merge** — list-valued fingerprint fields (genre_proximity, instrumentation_hints) accumulate across turns instead of being overwritten, so the picture sharpens rather than resets.

## Error Handling

- Job failures write `status=failed` + `error` under a guard, so the poller sees a definite outcome rather than a stuck `processing`.
- Texture auto-play respects a mute toggle and never blocks the conversation.
- Hum analysis degrades gracefully: if pitch is too quiet/unvoiced to read, it still returns a usable energy/tempo hint and a gentle description.

## Testing Strategy

- Manual: hum → hear a description → textures arrive → react → approve → fingerprint saved and sidebar shows content.
- Return visit: reopen, confirm the summary greeting and both continue/fresh paths.
- Property-based candidates (later spec): fingerprint clamps fields to 0–1; cache_key is stable for identical params.

## Deferred (tracked)

1. **Background job durability on Render free tier (W2).** Generation runs via FastAPI BackgroundTasks in-process; a spin-down mid-render could strand a job in `processing`. Acceptable for the demo (renders ~10s; spin-down needs 15 min idle). A stuck-job reaper or external worker is the real fix.
2. **Duplicate in-flight texture races (W3).** Two identical fingerprints requested before the first finishes both miss the cache and both render — wasteful, harmless. Fix by reserving the cache key at job creation or debouncing the client.
3. **"Your feel changed" Beat Room notification.** Cross-layer awareness belongs in the Beat Room spec, tracked there.
