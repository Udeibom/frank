# Song Record - Design

## Overview

Add a thin layer over what exists. Existing tables stay (lyrics_versions, feel_fingerprints,
beat_versions, vocal_takes, vocal_comps, mix_versions, project_active_state). New tables hold the
facets that had no home (intent, feeling, melody, structure, references, identity brief), a general
version/lineage mechanism, and a decisions log. One module builds the brief that all LLM calls use.

## Data model (migration 003)

```
song_facet_versions            -- append-only; never updated or deleted
  id UUID PK
  project_id UUID -> projects
  facet TEXT        -- intent | feeling | melody | structure | references | identity_brief
  content JSONB
  parent_id UUID -> song_facet_versions (nullable for the first version)
  operation TEXT    -- e.g. "user_set", "extract_from_hum", "restore"
  op_params JSONB
  author TEXT       -- "user" | "frank" | role name
  label TEXT
  created_at TIMESTAMPTZ

song_facet_active              -- the pointer; changing it is instant
  project_id UUID, facet TEXT, version_id UUID  -- PK (project_id, facet)

song_decisions                 -- append-only
  id, project_id, summary, rationale, proposed_by, options JSONB, evidence JSONB,
  chosen_option TEXT, user_reaction TEXT, created_at

project_active_state           -- existing; add:
  phase TEXT NOT NULL DEFAULT 'creating'   -- creating | refining
```

Facet content shapes (Pydantic in `models/song.py`):
- intent: `{text: str}` verbatim.
- feeling: `{summary: str, themes: [str], imagery: [str], emotional_arc: str|null}`.
- melody: `MelodySketch` (defined in spec 02).
- structure: `{sections: [{name, lines: [int], bars: int|null}]}` (line indexes into the active lyrics).
- references: `{items: [{text, source: "user"|"research", notes}]}` (filled by spec 10).
- identity_brief: `{borrow: [str], avoid: [str], distinct: [str]}` (filled by spec 10).

Branching: a branch is just a version whose parent is not the current head. Each facet's lineage
is the parent chain. The active pointer picks which head is live.

## Backend

- `db/song.py` - append_version, set_active, list_versions, get_active, record_decision, list_decisions.
- `services/song/record.py` - `get_record(project_id) -> SongRecord`: reads song facets plus the active
  lyrics, fingerprint, beat, vocal and mix via existing db modules.
- `services/song/brief.py` - `build_brief(record, role: str | None, budget_chars: int) -> str`: a PURE
  function. Fixed section order: intent, feeling, phase, active lyrics, melody and structure
  summary, fingerprint (internal wording), beat/vocal/mix status, recent decisions, rejected options.
  Trims in this order when over budget: older decisions, long lyrics (keep section starts), then
  detail. Intent and phase are never trimmed.
- `routers/song.py` - `GET /projects/{id}/song` (record summary for the UI), `POST .../song/facets/{facet}`
  (append version, optionally activate), `GET .../song/facets/{facet}/versions`,
  `POST .../song/facets/{facet}/restore`, `POST .../song/decisions`, `PATCH .../song/phase`.
- All existing conversation endpoints replace their own context builders with `build_brief` (done
  incrementally, room by room, in spec 07).

## Frontend

- `types/song.ts` mirrors the models. `store/song.ts` (Zustand) loads the record on project entry and
  refreshes on the existing `revision` counter used for cross-room state.
- A small "Where your song is" summary in the studio layout (plain language: what we know, what we're
  missing). No raw fields.

## Migration safety

Migration 003 only adds tables and one defaulted column. Old projects work unchanged; their new
facets are empty. RLS follows the pattern in 002 (owner-only via projects.user_id).

## Correctness properties (for PBT)

1. Append-only: after any sequence of writes, previously stored versions are byte-identical.
2. Lineage: every version's parent chain is acyclic and ends at a root in the same project and facet.
3. Restore: restoring version V then reading the active content equals V's content, and a new version
   exists whose parent is V.
4. Brief determinism: same record gives the same brief; brief length never exceeds the budget;
   intent text and phase are always present.
5. Brief trimming monotonic: lowering the budget never removes intent/phase and removes older
   items before newer ones.
