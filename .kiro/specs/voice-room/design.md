# Voice Room — Design

## Overview

The Voice Room records the user's vocal and does the technical work on the server: pitch analysis, correction, comping, and harmony. The emotional design principle from `conversation-layer.md` governs everything — the system is a patient vocal producer that never criticizes the singing and always offers rather than decides. The audio principle from `audio-architecture.md` governs the rest — the original take is sacred and never overwritten; every derived file is new.

## Architecture

```
useRecorder (MediaRecorder) ─▶ POST /voice/takes ─▶ Storage vocals/ (WAV)
                                   └─▶ async: librosa pyin → pitch_data (contour + confidence)
Correct ─▶ POST /voice/takes/{id}/correct(mode) ─▶ job ─▶ pylibrb per-segment shift ─▶ processed_url (MP3)
Comp   ─▶ POST /voice/comp(take_ids) ─▶ job ─▶ score segments → FFmpeg concat ─▶ vocal_comps (MP3)
Harmony─▶ POST /voice/harmony(type) ─▶ job ─▶ pylibrb interval shift (mode-aware) ─▶ harmony stem (MP3)
Active ─▶ POST /voice/active ─▶ active_vocal_id / active_comp_id
```

## Components and Interfaces

### Frontend
- `hooks/useRecorder.ts` — reusable recorder (shared with the Idea Room voice memo).
- `components/audio/VocalRecorder.tsx` — record button, timer, live level meter, stop, beat sync.
- Take cards — waveform, duration, label, play; select-to-compare.
- `components/audio/PitchDisplay.tsx` — color-coded tuning view (green/yellow/red) with a non-color cue.
- Conversation panel wired to `/voice/conversation`, driving correct / comp / harmony via async jobs.

### Backend
- `routers/voice.py` — takes, correct, comp, harmony, conversation, active, delete.
- `services/audio/pitch.py` — `pyin` contour + confidence; `apply_correction` with three strengths; `_snap_to_grid` for full mode.
- `services/audio/comp.py` — per-segment scoring + FFmpeg concat.
- `services/audio/harmony.py` — mode-aware interval selection from the fingerprint + `pylibrb` shift, level-matched.
- `db/voice.py` — takes, comps, active pointers; soft-delete flag.

## Data Models

- `vocal_takes` (audio_url WAV, processed_url, pitch_data JSONB, label, soft-delete flag).
- `vocal_comps` (audio_url, segments JSONB for visualization).
- `project_active_state.active_vocal_id`, `active_comp_id`.
- Pitch contour: `[{ time, note, confidence }, ...]`; confidence → color (>0.8 green, 0.5–0.8 yellow, <0.5 red).

Design decisions:
- **librosa pyin over Basic Pitch** — Basic Pitch needs TensorFlow (~500MB, neural), breaking the free-tier memory budget. pyin gives an accurate-enough contour to color the display and drive correction. (tech.md)
- **pylibrb over pyrubberband/librosa pitch_shift** — pylibrb binds `librubberband` directly (no CLI) and is ~100x faster than librosa's pitch_shift; the native lib is installed in the Dockerfile. (tech.md)
- **Harmony derived, not recorded** — the harmony is a pitch-shift of the user's own take, so no second recording is needed; it serves the "magic, not a chore" design note.
- **Originals WAV, derivatives MP3** — lossless preservation of the source; small, fast-streaming playback copies within Supabase limits.

## Error Handling

- The Spec-05 correction crash (`y`/`sr` vs `y_full`/`sr_full`) is fixed and verified across all three modes; the earlier happy-path test had masked it by landing on the no-op path.
- Job failures mark the job failed with a plain-language error.
- Harmony takes receive an empty `pitch_data` list so the UI does not show "analyzing" forever.
- Downloads happen inside worker threads, keeping the event loop responsive.

## Testing Strategy

- Manual: record multiple takes, confirm none are lost; run all three correction modes and confirm "Lock it in" audibly snaps; build a comp and confirm segment provenance; add a harmony and confirm it tracks the melody in key.
- Property-based candidates (later spec): pitch-shift preserves duration; correction never mutates the original file.

## Deferred (tracked)

1. **Alternating "play both" A/B comparison (R3).** Per-take playback and select-to-compare exist; 4-bar alternating playback is a nice-to-have, not demo-critical.
2. **Pitch display as a waveform overlay + show/hide toggle (R4).** The current bar view conveys "where are the rough spots" without jargon; the overlay and toggle are polish.
3. **Vocal effects preview — "add space" / "smooth" / "warm up" (R8 of the original spec).** These are effects and belong with the Mix Room's pedalboard chain; build there and expose a preview here if time allows.
4. **Multi-take alignment (W1/W6).** Comp assumes takes start aligned (true for record-with-beat from the top); drift isn't compensated. A start-timestamp + alignment pass is future work.
5. **Concurrency cap (W9).** No global limit on simultaneous heavy jobs; a single-slot queue would harden the free-tier instance. Acceptable for a single-user demo.
6. **Active-vocal vs active-comp reconciliation (S6).** Settled in the Mix Room, where the active vocal actually feeds the mix.
