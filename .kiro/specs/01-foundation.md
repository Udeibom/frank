# Spec 01 — Project Foundation

## Overview

This spec establishes the complete skeleton of Frank: the monorepo structure, the Next.js frontend shell, the FastAPI backend shell, the Supabase database schema, and the wiring between all three. When this spec is complete, a developer can run both the frontend and backend locally, navigate between all six studio layers for a project, and the project state is persisted to Supabase.

No audio processing is built in this spec. No LLM calls are made. This is the bones everything else attaches to.

---

## Requirements

### R1 — Repository Structure
The repository must match the structure defined in `structure.md` exactly. Both `frontend/` and `backend/` live at the root of the Frank workspace.

### R2 — Frontend: Next.js Application Shell
- Next.js 14 with App Router, TypeScript, Tailwind CSS
- shadcn/ui installed and configured with the dark theme matching `design-and-ui.md`
- The root `app/layout.tsx` sets the dark background, font, and global styles
- A landing page (`app/page.tsx`) with the Frank name, tagline "Use Frank.", and a single CTA button: "Start a Song"
- A studio layout (`app/(studio)/layout.tsx`) with the persistent six-layer navigation sidebar
- All six layer pages exist as routes and render a placeholder — they are not blank, each has its layer name and a one-line description
- The project dashboard (`app/(studio)/page.tsx`) shows a list of projects (empty state handled gracefully: "You don't have any songs yet. Start one.")
- A "New Project" button creates a project and navigates to it

### R3 — Frontend: Zustand Stores
Three stores must be initialized:
- `store/project.ts` — holds the current project, its title, status, and layer states
- `store/session.ts` — holds the current user ID (hardcoded dev UUID for now), session metadata
- `store/audio.ts` — holds the currently playing audio file URL, playback state (playing/paused/idle), and current position

All stores must be properly typed using the types defined in `types/`.

### R4 — Frontend: TypeScript Types
The following type files must be created with complete, accurate types:
- `types/project.ts` — Project, Layer states, LyricsVersion, MusicalFingerprint, BeatStem, VocalTake, MixVersion, ExportRecord
- `types/audio.ts` — AudioFile, PitchData, WaveformData, PlaybackState
- `types/api.ts` — All API request and response shapes (can be stubs at this stage, but must be defined)

### R5 — Backend: FastAPI Application Shell
- Python 3.11+ FastAPI application in `backend/`
- `requirements.txt` with all dependencies pinned to exact versions
- `app/main.py` starts the server, includes CORS middleware (allows localhost:3000 in dev), and mounts all routers
- A health check endpoint: `GET /health` returns `{"status": "ok", "service": "frank-api"}`
- All routers listed in `structure.md` exist and are registered, each returning a placeholder `{"status": "not_implemented"}` for all routes
- `app/config.py` loads all environment variables using pydantic-settings, with clear validation errors if required vars are missing
- A `.env.example` file at the `backend/` root listing every required environment variable with a description comment

### R6 — Supabase: Database Schema
The following tables must be created via a SQL migration file at `backend/db/migrations/001_initial_schema.sql`:

**projects**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `user_id` UUID NOT NULL (references auth.users in production, unconstrained in dev)
- `title` TEXT NOT NULL DEFAULT 'Untitled Song'
- `status` TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_progress', 'exported'))
- `created_at` TIMESTAMPTZ DEFAULT now()
- `updated_at` TIMESTAMPTZ DEFAULT now()

**lyrics_versions**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `content` TEXT NOT NULL DEFAULT ''
- `label` TEXT
- `created_at` TIMESTAMPTZ DEFAULT now()

**feel_fingerprints**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `fingerprint` JSONB NOT NULL DEFAULT '{}'
- `conversation_summary` TEXT
- `created_at` TIMESTAMPTZ DEFAULT now()

**texture_samples**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `fingerprint_id` UUID REFERENCES feel_fingerprints(id)
- `audio_url` TEXT NOT NULL
- `cache_key` TEXT  (added Spec 03 — deterministic hash of the generating params for reuse)
- `approved` BOOLEAN DEFAULT false
- `created_at` TIMESTAMPTZ DEFAULT now()

**beat_versions**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `render_url` TEXT
- `label` TEXT
- `params` JSONB DEFAULT '{}'
- `created_at` TIMESTAMPTZ DEFAULT now()

**beat_stems**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `beat_version_id` UUID REFERENCES beat_versions(id)
- `stem_type` TEXT NOT NULL
- `section` TEXT
- `audio_url` TEXT NOT NULL
- `version_of` UUID REFERENCES beat_stems(id)
- `created_at` TIMESTAMPTZ DEFAULT now()

**vocal_takes**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `audio_url` TEXT NOT NULL
- `processed_url` TEXT
- `pitch_data` JSONB
- `label` TEXT
- `created_at` TIMESTAMPTZ DEFAULT now()

**vocal_comps**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `audio_url` TEXT NOT NULL
- `segments` JSONB NOT NULL DEFAULT '[]'
- `created_at` TIMESTAMPTZ DEFAULT now()

**mix_versions**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `render_url` TEXT
- `label` TEXT
- `mix_params` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ DEFAULT now()

**exports**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `audio_url` TEXT NOT NULL
- `format` TEXT NOT NULL DEFAULT 'mp3'
- `quality` TEXT NOT NULL DEFAULT '320k'
- `created_at` TIMESTAMPTZ DEFAULT now()

**async_jobs**
- `id` UUID PRIMARY KEY DEFAULT gen_random_uuid()
- `project_id` UUID NOT NULL REFERENCES projects(id)
- `job_type` TEXT NOT NULL
- `status` TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'complete', 'failed'))
- `result` JSONB
- `error` TEXT
- `created_at` TIMESTAMPTZ DEFAULT now()
- `updated_at` TIMESTAMPTZ DEFAULT now()

**project_active_state**
- `project_id` UUID PRIMARY KEY REFERENCES projects(id)
- `active_lyrics_id` UUID REFERENCES lyrics_versions(id)
- `active_fingerprint_id` UUID REFERENCES feel_fingerprints(id)
- `active_beat_version_id` UUID REFERENCES beat_versions(id)
- `active_vocal_id` UUID REFERENCES vocal_takes(id)
- `active_comp_id` UUID REFERENCES vocal_comps(id)
- `active_mix_id` UUID REFERENCES mix_versions(id)
- `updated_at` TIMESTAMPTZ DEFAULT now()

### R7 — Backend: Database Access Layer
- `backend/app/db/` contains a `client.py` that initializes the Supabase Python client
- A `projects.py` module with async functions: `create_project`, `get_project`, `list_projects_by_user`, `update_project_title`, `get_project_active_state`, `update_project_active_state`
- All DB functions use the service role key (never the anon key on the backend)

### R8 — Backend: Projects Router
`routers/projects.py` implements:
- `POST /projects` — create a new project, returns the project with its id
- `GET /projects` — list all projects for the dev user (hardcoded user ID for now)
- `GET /projects/{project_id}` — get a single project with its active state
- `PATCH /projects/{project_id}` — update project title or status

### R9 — Frontend: API Client
`frontend/lib/api/projects.ts` implements typed fetch functions mirroring the backend routes:
- `createProject()` — POST /projects
- `listProjects()` — GET /projects
- `getProject(id)` — GET /projects/{id}
- `updateProject(id, data)` — PATCH /projects/{id}

All functions handle errors gracefully and return typed responses.

### R10 — Frontend: Project Dashboard Wired to Backend
The project dashboard (`app/(studio)/page.tsx`) must:
- Call `listProjects()` on load
- Display real projects from the database
- "New Project" calls `createProject()` and navigates to `/[projectId]/idea`
- Show the project title, status badge, and "last worked on" date for each project
- Clicking a project navigates to `/[projectId]/idea`

### R11 — Studio Layer Navigation
The studio sidebar (`components/studio/StudioNav.tsx`) shows:
- The project title (editable inline — click to edit, blur to save)
- All six layers with their icons and names: Idea, Feel, Beat, Voice, Mix, Export
- A status indicator per layer (empty/in-progress/has-content) driven by the project's active state
- The currently active layer highlighted
- A back link to the dashboard

### R12 — Environment Setup
- `frontend/.env.local.example` lists all required frontend env vars
- `backend/.env.example` lists all required backend env vars
- A `README.md` at the project root with setup instructions: how to install dependencies, set up env vars, run the dev servers, and apply the database migration

---

## Design Notes

- The landing page should feel like a studio door — dark, warm, a single light on. Not a SaaS homepage with feature bullets.
- The "Start a Song" CTA should feel like an invitation, not a signup form.
- The studio sidebar is persistent across all layer pages. It never disappears.
- Status indicators on the sidebar update in real time as the user works — they are driven by whether the active state for that layer is populated.
- The six layer placeholder pages should feel like rooms that are ready but not yet filled — a dark space with the layer name and a sentence inviting the user in, not a generic "Coming Soon."

---

## Implementation Tasks

### Task 1 — Scaffold the monorepo
- [ ] Initialize `frontend/` with `create-next-app` (TypeScript, App Router, Tailwind)
- [ ] Initialize `backend/` with the folder structure from `structure.md`
- [ ] Create root `README.md`
- [ ] Add `.gitignore` at root covering node_modules, .env files, __pycache__, .next, venv

### Task 2 — Configure the frontend
- [ ] Install and configure shadcn/ui with dark theme
- [ ] Set global CSS variables for Frank's color palette (dark background, amber accent, off-white text)
- [ ] Set up root layout with Inter font
- [ ] Create all TypeScript type files with complete types

### Task 3 — Create Zustand stores
- [ ] `store/project.ts`
- [ ] `store/session.ts`
- [ ] `store/audio.ts`

### Task 4 — Build the landing page
- [ ] `app/page.tsx` — Frank name, tagline, CTA button
- [ ] No navigation header on the landing page

### Task 5 — Build the studio shell
- [ ] `app/(studio)/layout.tsx` — studio shell with sidebar slot
- [ ] `components/studio/StudioNav.tsx` — full sidebar with layer nav and status indicators
- [ ] `app/(studio)/page.tsx` — project dashboard (empty state + project list)
- [ ] `app/(studio)/[projectId]/layout.tsx` — per-project layout that loads the project and populates the store
- [ ] All six layer placeholder pages: `idea/page.tsx`, `feel/page.tsx`, `beat/page.tsx`, `voice/page.tsx`, `mix/page.tsx`, `export/page.tsx`

### Task 6 — Set up FastAPI backend
- [ ] `backend/app/main.py` with CORS, health check, router registration
- [ ] `backend/app/config.py` with pydantic-settings
- [ ] `backend/requirements.txt` with all dependencies pinned
- [ ] `backend/Procfile` for Render deployment
- [ ] All router files created with placeholder routes

### Task 7 — Supabase schema
- [ ] Write `backend/db/migrations/001_initial_schema.sql`
- [ ] Apply the migration to the Supabase project
- [ ] `backend/app/db/client.py` — Supabase Python client initialization
- [ ] `backend/app/db/projects.py` — all project DB functions

### Task 8 — Wire projects API
- [ ] `backend/app/routers/projects.py` — all four routes implemented
- [ ] `frontend/lib/api/projects.ts` — all four client functions
- [ ] Dashboard wired to real backend data
- [ ] New project creation works end to end

### Task 9 — Studio nav wired to project state
- [ ] Project title editable inline from the sidebar
- [ ] Layer status indicators reflect active state from DB
- [ ] Navigation between layers works

### Task 10 — Environment and documentation
- [ ] `.env.example` files for both frontend and backend
- [ ] README with complete local setup instructions
- [ ] Verify the full flow: open app → create project → navigate all six layers → project persists on refresh
