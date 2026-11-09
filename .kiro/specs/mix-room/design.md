# Mix Room — Design

## Overview

The Mix Room combines the active vocal, any harmony, and the active beat into a single song, controlled entirely through conversation. The design principle from `conversation-layer.md`: the system behaves like a mix engineer who explains simply, makes at most 2–3 changes per turn, and keeps the feedback loop tight. The hardest-won correctness lesson here (Spec 06 review) was that a reported change must be a real change — section gain used to be a silent no-op, which broke the core "two-way production" promise. It now genuinely alters the audio.

## Architecture

```
Entry ─▶ take stock (active vocal/comp, harmony, active beat)
      ─▶ both present? auto-assemble + play ; else explain what's missing
Conversation ─▶ POST /mix/conversation ─▶ llm ─▶ actions
   adjust_levels | apply_effect | section_adjust | render_preview | analyze_mix
Render ─▶ POST /mix/render(mix_params, quality) ─▶ job
   mixing.render_mix: load vocal → apply gain/effects → accumulate → release
                      load harmony → accumulate → release
                      load beat → apply per-section gain windows → accumulate → release
                      preview: 64kbps MP3 ; full: WAV → 320kbps MP3
Preview-with-vocal ─▶ run_vocal_preview_job ─▶ throwaway URL (no version, no active change)
```

## Components and Interfaces

### Frontend
- Mix versions panel — collapsible, per-version play, set-active, label; plain-text summary shown in the label.
- Read-only stem balance view with a harmony on/off toggle (the only direct control).
- Conversation panel wired to `/mix/conversation`; triggers preview renders and plays results.

### Backend
- `routers/mix.py` — render, versions, active, conversation.
- `services/audio/mixing.py` — `render_mix` (gain, pedalboard effects, FFmpeg overlay, memory-frugal accumulation, per-section windowing), `analyze_mix`, `run_vocal_preview_job`.
- `services/llm/prompts.py` — Mix Room system prompt.
- `db/mix.py` — mix version records and active pointer.

## Data Models

- `mix_versions` (project_id, render_url, label, mix_params JSONB).
- `mix_params`: `{ stem_levels: {...}, effects: {...}, section_gain_db: { section: db } }`.
- `project_active_state.active_mix_id`.

Design decisions:
- **Section gain by time-windowing the beat** — the beat version's params carry section bars + tempo (boundaries known by construction), so "boost the chorus" maps to a real time window; verified the chorus reaches ~2x the verse RMS. This replaced the silent no-op.
- **Accumulate-and-release rendering** — holding vocal+beat+harmony buffers at once risked OOM on the free tier; each layer is mixed in then freed.
- **Preview 64 kbps, full 320 kbps** — fast iteration vs clean export, per `audio-architecture.md`.
- **Dedicated vocal-preview job** — keeps "hear it with my vocal" from creating versions or stealing the active pointer.
- **Effects via pedalboard** — Context7 confirmed the real API (`Compressor(threshold_db, ratio, attack_ms, release_ms)`, `Limiter`, `BrickwallLimiter(ceiling_db=...)`), correcting an earlier guessed parameter.

## Error Handling

- Render failures mark the job failed with plain-language copy.
- Analysis never returns raw dB/Hz to the UI; it returns phrasing the LLM uses directly.
- Missing-stem entry states are explained, not errored.

## Testing Strategy

- Manual: assemble on entry, "vocals feel buried" raises the vocal audibly, "make the chorus louder" measurably boosts the chorus region, versions accumulate with readable labels.
- Property-based candidates (later spec): mix length ≥ longest input; a non-zero section gain changes the audio.

## Deferred (tracked)

1. **Harmony resolved by label prefix (S1).** Brittle if a user renames the take; a dedicated `is_harmony` flag is cleaner. Low risk for the MVP.
2. **Active comp fetched via `get_latest_comp` rather than `active_comp_id` (S2).** Only matters with multiple comps; effectively one today.
3. **Full-render milestone messaging (S4).** The "your song is ready to export" moment is delivered in the Export Room instead.
4. **Server-side jargon scrub.** The no-jargon guarantee is prompt-only; a belt-and-suspenders scrub of the LLM message is possible hardening.
