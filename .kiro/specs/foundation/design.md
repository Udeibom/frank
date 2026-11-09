# Foundation — Design

## Overview

The foundation is a three-tier monorepo: a Next.js 14 frontend, a FastAPI backend, and a Supabase Postgres database with Storage. This spec wires the three together so that a project can be created, listed, opened, renamed, and navigated across six rooms — with every piece of state persisted. It builds the bones; later specs attach audio, LLM, and generation flesh.

The guiding steering here is `structure.md` (layout and naming), `design-and-ui.md` (studio feel, dark theme, no jargon, accessibility), and `project-layer.md` (project shape, active-pointer model, "never lose creative work").

## Architecture

```
Browser (Next.js, Zustand)
  │  REST/JSON over HTTPS
  ▼
FastAPI (routers → db access layer)
  │  supabase-py (service role)
  ▼
Supabase (Postgres + Storage)
```

Key boundaries:
- The frontend never talks to Supabase directly for project data; it goes through the FastAPI backend. (Direct Supabase access from the client is reserved for later signed-URL audio streaming.)
- The backend always uses the service role key; the anon key never runs server-side.
- Routers are thin; business logic and all DB calls live in `app/db/`.

## Components and Interfaces

### Frontend

- `app/layout.tsx` — root layout: dark background, Inter font, global CSS variables for the palette.
- `app/page.tsx` — landing page: name, tagline, single "Start a Song" CTA. No nav header.
- `app/(studio)/layout.tsx` — studio shell hosting the persistent nav.
- `app/(studio)/page.tsx` — dashboard: lists projects, empty state, "New Project".
- `app/(studio)/[projectId]/layout.tsx` — loads the project and populates the project store.
- `app/(studio)/[projectId]/{idea,feel,beat,voice,mix,export}/page.tsx` — six placeholder rooms.
- `components/studio/StudioNav.tsx` — sidebar: editable title, six layers with status indicators, back link.
- `store/{project,session,audio}.ts` — Zustand stores.
- `types/{project,audio,api}.ts` — shared types.
- `lib/api/projects.ts` — typed client functions.

### Backend

- `app/main.py` — app factory, CORS, health check, router registration.
- `app/config.py` — pydantic-settings loading and validating env vars.
- `app/routers/*.py` — one router per domain; placeholders return `{"status": "not_implemented"}`.
- `app/routers/projects.py` — the only fully-implemented router in this spec.
- `app/db/client.py` — Supabase client singleton (service role).
- `app/db/projects.py` — async project data functions.
- `app/models/` — Pydantic request/response models.

### API surface (this spec)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | — | `{status, service}` |
| POST | `/projects` | `{title?}` | `Project` |
| GET | `/projects` | — | `Project[]` |
| GET | `/projects/{id}` | — | `Project` + `active_state` |
| PATCH | `/projects/{id}` | `{title?, status?}` | `Project` |

## Data Models

The schema is created by `001_initial_schema.sql`. Twelve tables; the authoritative column lists live in the requirements and the migration file. The shape follows `project-layer.md`:

- `projects` is the song root.
- One table per versioned artifact family (`lyrics_versions`, `feel_fingerprints`, `texture_samples`, `beat_versions`, `beat_stems`, `vocal_takes`, `vocal_comps`, `mix_versions`, `exports`).
- `project_active_state` holds the "active pointer" per layer — the version that plays when the user hits play. Changing a pointer is a cheap update, not a re-render.
- `async_jobs` backs long-running generation/mix jobs introduced in later specs.

Design decision — active state as a separate table rather than columns on `projects`: it keeps the project row stable and lets each pointer be a nullable foreign key resolved independently, matching the "active pointer is instant" rule in `project-layer.md`.

Design decision — never delete on supersede: superseded rows are only dereferenced (the active pointer moves). This directly serves "Data That Must Never Be Lost."

## Error Handling

- Missing env vars: `config.py` raises at startup with the offending variable named (fail fast, never boot half-configured).
- API client failures: `lib/api/projects.ts` catches, logs, and returns a typed error result so the UI can show plain-language messaging rather than a stack trace.
- Backend route errors: return structured JSON with an HTTP status; no raw 500 HTML reaches the client.

## Testing Strategy

- Manual end-to-end smoke: open app → create project → navigate all six rooms → refresh → project persists.
- Backend health and projects routes exercised via HTTP.
- Later specs add property-based tests; the foundation's pure surface (status mapping, title defaulting) is a candidate for those.
