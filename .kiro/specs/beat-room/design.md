# Beat Room — Design

## Overview

The Beat Room builds and shapes an instrumental from the musical fingerprint using Frank's procedural engine. The defining design choice: the composition is explicit (chords, bassline, melody, drum patterns derived from key/mode/tempo/energy/density), so every edit — "the bass is too busy", "take the keys out of the bridge" — is a precise parameter change and a targeted re-render, not a re-roll of a black box. This is the "two-way production" the product promises, and the reason the engine beats MusicGen for this product even setting aside cost.

## Architecture

```
Entry ─▶ fingerprint present? ─ yes ─▶ "Build the beat"
                                └ no ──▶ abbreviated feel discovery ─▶ simplified fingerprint saved
"Build" ─▶ POST /beat/generate ─▶ async job
     composer: fingerprint → MIDI per section (intro/verse/chorus/bridge/outro)
     renderer: MIDI → FluidSynth + SoundFont → per-stem audio
     assemble: FFmpeg overlay stems → beat render (MP3)
     persist: beat_versions + beat_stems, active_beat_version_id
Conversation ─▶ POST /beat/conversation ─▶ llm ─▶ actions
     regenerate_section | add_stem | mute_stem | reorder_sections
     | generate_full_beat | restore_version | set_section_label
```

## Components and Interfaces

### Frontend
- `components/studio/BeatTimeline.tsx` — sections as warm colored blocks; click to scrub; playing section highlighted; inline label edit.
- `components/studio/BeatLayers.tsx` — plain-language layer list per section with mute toggles that trigger a re-render.
- Versions panel — collapsible list, per-version play, set-active, label.
- Conversation panel wired to `/beat/conversation` with async job polling for generation actions.

### Backend
- `routers/beat.py` — generate, generate-section, add-stem, conversation, versions, active, section PATCH.
- `services/generation/theory.py` — key/mode → chord progression, scales, intervals.
- `services/generation/composer.py` — builds MIDI per section (chords, bass, melody/pad, drums) from the fingerprint.
- `services/generation/renderer.py` — MIDI → audio via a shared FluidSynth `SynthSession` + SoundFont; renders section-by-section, accumulating and releasing to stay within memory.
- `services/audio/mixing.py` — FFmpeg overlay to assemble stems.
- `db/beat.py` — version/stem records, active pointer.

## Data Models

- `beat_versions` (project_id, render_url, label, params JSONB).
- `beat_stems` (project_id, beat_version_id, stem_type, section, audio_url, version_of).
- `project_active_state.active_beat_version_id`.

Design decisions:
- **Procedural engine, not MusicGen** — no free hosted MusicGen; and explicit composition is what makes "the bass feels too busy" a real, controllable change. (tech.md, audio-architecture.md)
- **Sections known by construction** — the engine defines boundaries, so no `librosa.onset` segmentation guesswork is needed (the original single-file spec assumed MusicGen + onset detection; the engine removed that whole class of error).
- **MP3 for stored playback** — a full WAV beat (~25MB) blows past Supabase's 50MB upload limit and streams slowly; WAV stays in memory only during processing. (audio-architecture.md)
- **Label-only section PATCH** — reordering changes audio, so it goes through a re-render that yields a new version, avoiding timeline/audio desync.

## Error Handling

- Generation runs in a worker; failures mark the job failed with an error the UI can phrase plainly.
- Memory-frugal rendering (section accumulate-and-release, shared synth session) prevents the OOM seen on the 4GB dev box / Render free tier.
- Upload retry on transient Storage failures; single-threaded persist to avoid races.

## Testing Strategy

- Manual: build a beat, confirm sections and stems, mute the keys in a section and hear the change, request "a different beat" and confirm a new version with the old preserved, restore the first version.
- Property-based candidates (later spec): section gain changes actually change the audio; mix length ≥ longest input.

## Deferred (tracked)

1. **Preview with vocal (R8).** Depends on the Voice Room; implemented after it as a temporary non-persisted overlay of the active vocal over the active beat.
2. **Per-section re-render optimization (W1).** Edits currently re-render the whole beat (correct, but pays full render+upload each time). Optimize to re-render only the changed section and reuse unchanged section audio. A speed improvement, not a correctness issue.
3. **Reorder / duplicate / remove UI (R3).** Only rename is reachable in the timeline; reorder needs the re-render path, duplicate/remove need new endpoints. Not demo-critical for the voice-first path.
4. **Beat-First fingerprint persistence (S1).** Persist the normalized Beat-First fingerprint to the feel layer on first generation so downstream layers share it. Small follow-up.
5. **`duration_hint` accepted but ignored (W4).** The default 8-section arrangement covers the MVP.
