# Voice-to-Export Flow — Design

## Overview

This is a contract spec. It covers how four active pointers move between rooms, and how the frontend keeps them fresh. The rule behind every decision: `project_active_state` is the only authority, and every room re-reads it.

## Architecture

```
Voice Room  ──upload/choose take──▶ active_vocal_id = take, active_comp_id = NULL
            ──comp job completes──▶ active_comp_id = comp
            ──choose comp─────────▶ active_comp_id = comp
Beat Room   ──new/chosen version──▶ active_beat_version_id
Mix Room    ──resolve layers──────▶ reads vocal, beat, harmony at render time
            ──render (saved)──────▶ mix_versions row + active_mix_id
            ──vocal preview───────▶ throwaway URL only
Export Room ──reads active_mix_id─▶ exports row (mix_version_id, mastered)

Frontend: layout re-syncs on pathname change; store.revision bumps → rooms re-read.
```

## The vocal resolution rule (Requirement 2)

"The most recently chosen vocal wins."

- Choosing or uploading a take sets `active_vocal_id` and clears `active_comp_id`.
- A completed comp job, or choosing a comp, sets `active_comp_id`.
- The Mix Room uses the comp if `active_comp_id` is set, otherwise the active take's tuned audio (`processed_url`) if present, otherwise its original audio.

Before this spec, only the comp-wins half existed. A new recording after a comp was silently ignored by the Mix Room. Clearing the comp pointer fixes this without deleting the comp, so nothing is lost (Requirement 6).

## Known gaps in the Mix Room's resolution (tracked, not yet fixed)

1. `_resolve_layers` fetches the comp with `get_latest_comp`, not by `active_comp_id`. With several comps it can use the wrong one.
2. Harmony is found by label prefix `"harmony"`, so renaming a take breaks it. It needs an `is_harmony` flag.
3. `_resolve_layers` is I/O-bound and hard to unit-test. Splitting the decision into a pure function would let property-based tests cover it.

## Error Handling

- A missing layer is explained to the user, not raised as an error (Mix Room Requirement 1.3, Export Requirement 5.2).
- Pointer writes are single-row updates, so a room can't leave `project_active_state` half-updated.

## Testing Strategy

- **Browser integration test (Playwright MCP):** record a take, build a comp, record another take, then open the Mix Room and check it uses the new take.
- **Property-based tests:** the pure resolution rule, "an upload always yields vocal = new take," and "a preview leaves mix versions unchanged."
- **Database check (Supabase MCP):** after each step, read `project_active_state` directly and compare it with what the UI shows.
