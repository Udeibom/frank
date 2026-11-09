# Foundation — Requirements

## Introduction

This spec establishes the complete skeleton of Frank: the monorepo structure, the Next.js frontend shell, the FastAPI backend shell, the Supabase database schema, and the wiring between all three. When this spec is complete, a developer can run both the frontend and backend locally, navigate between all six studio layers for a project, and the project state is persisted to Supabase.

No audio processing is built in this spec. No LLM calls are made. This is the bones everything else attaches to. It traces directly to the `structure.md`, `design-and-ui.md`, and `project-layer.md` steering documents.

## Requirements

### Requirement 1 — Repository Structure

**User Story:** As a developer, I want the repository laid out exactly as the structure steering defines, so that every later feature has a predictable place to attach.

#### Acceptance Criteria

1. WHEN the repository is cloned THEN the system SHALL expose a `frontend/` directory and a `backend/` directory at the workspace root.
2. WHERE the layout is compared against `structure.md` THE SYSTEM SHALL match the documented directory tree for both frontend and backend.
3. THE SYSTEM SHALL include a root `.gitignore` covering `node_modules`, `.env` files, `__pycache__`, `.next`, and `venv`.

### Requirement 2 — Frontend Application Shell

**User Story:** As a non-musician visitor, I want to land on a warm studio door and start a song in one click, so that I feel invited in rather than onboarded through a form.

#### Acceptance Criteria

1. THE SYSTEM SHALL build the frontend on Next.js 14 App Router with TypeScript and Tailwind CSS.
2. THE SYSTEM SHALL configure shadcn/ui with the dark theme described in `design-and-ui.md` (deep warm background, amber accent, off-white text).
3. WHEN the root layout renders THEN the system SHALL apply the dark background, the Inter font, and the global color variables.
4. WHEN a visitor opens the landing page THEN the system SHALL display the name "Frank", the tagline "Use Frank.", and a single CTA button labeled "Start a Song".
5. THE SYSTEM SHALL provide a studio layout with a persistent six-layer navigation that does not disappear across layer pages.
6. WHERE a layer page has no content yet THE SYSTEM SHALL render a placeholder that names the layer and invites the user in, never a blank page or a generic "Coming Soon".
7. WHEN the project dashboard loads with no projects THEN the system SHALL show the empty state "You don't have any songs yet. Start one."
8. WHEN the user activates "New Project" THEN the system SHALL create a project and navigate to that project's Idea room.

### Requirement 3 — Frontend State Stores

**User Story:** As a developer, I want typed client stores for project, session, and audio state, so that every room reads and writes shared state consistently.

#### Acceptance Criteria

1. THE SYSTEM SHALL initialize a `store/project.ts` holding the current project, its title, status, and layer states.
2. THE SYSTEM SHALL initialize a `store/session.ts` holding the current user ID (a hardcoded dev UUID for now) and session metadata.
3. THE SYSTEM SHALL initialize a `store/audio.ts` holding the currently playing audio URL, playback state (playing/paused/idle), and current position.
4. THE SYSTEM SHALL type all three stores using the definitions in `types/`.

### Requirement 4 — Frontend TypeScript Types

**User Story:** As a developer, I want complete type definitions up front, so that no room introduces untyped shapes or `any`.

#### Acceptance Criteria

1. THE SYSTEM SHALL define `types/project.ts` with Project, layer states, LyricsVersion, MusicalFingerprint, BeatStem, VocalTake, MixVersion, and ExportRecord.
2. THE SYSTEM SHALL define `types/audio.ts` with AudioFile, PitchData, WaveformData, and PlaybackState.
3. THE SYSTEM SHALL define `types/api.ts` with all API request and response shapes, which MAY be stubs at this stage but SHALL be declared.

### Requirement 5 — Backend Application Shell

**User Story:** As a developer, I want a running FastAPI server with a health check and all routers mounted, so that the frontend has stable endpoints to call from day one.

#### Acceptance Criteria

1. THE SYSTEM SHALL run a Python 3.11+ FastAPI application in `backend/`.
2. THE SYSTEM SHALL pin every dependency in `requirements.txt` to an exact version.
3. WHEN the application starts THEN the system SHALL enable CORS allowing `localhost:3000` in development and mount every router listed in `structure.md`.
4. WHEN `GET /health` is called THEN the system SHALL respond with `{"status": "ok", "service": "frank-api"}`.
5. WHERE a route has not been implemented yet THE SYSTEM SHALL respond with `{"status": "not_implemented"}`.
6. IF a required environment variable is missing THEN the system SHALL fail to start with a clear validation error naming the missing variable.
7. THE SYSTEM SHALL provide a `backend/.env.example` listing every required variable with a description comment.

### Requirement 6 — Database Schema

**User Story:** As the product, I want every creative artifact to have a durable home with full version history, so that no lyric, take, beat, or mix is ever lost.

#### Acceptance Criteria

1. THE SYSTEM SHALL create the schema via a migration at `backend/db/migrations/001_initial_schema.sql`.
2. THE SYSTEM SHALL create the tables: projects, lyrics_versions, feel_fingerprints, texture_samples, beat_versions, beat_stems, vocal_takes, vocal_comps, mix_versions, exports, async_jobs, and project_active_state.
3. THE SYSTEM SHALL constrain `projects.status` to one of `draft`, `in_progress`, `exported`.
4. THE SYSTEM SHALL constrain `async_jobs.status` to one of `pending`, `processing`, `complete`, `failed`.
5. THE SYSTEM SHALL key `project_active_state` on `project_id` with foreign keys to the active lyrics, fingerprint, beat version, vocal take, comp, and mix.
6. WHERE a record is superseded THE SYSTEM SHALL dereference it rather than delete it, preserving history.

### Requirement 7 — Backend Database Access Layer

**User Story:** As a developer, I want a thin typed DB layer using the service role, so that routers never touch the client directly and the anon key never runs on the server.

#### Acceptance Criteria

1. THE SYSTEM SHALL initialize the Supabase Python client in `backend/app/db/client.py`.
2. THE SYSTEM SHALL provide `backend/app/db/projects.py` with: `create_project`, `get_project`, `list_projects_by_user`, `update_project_title`, `get_project_active_state`, and `update_project_active_state`.
3. THE SYSTEM SHALL use the service role key for all backend DB access and SHALL NOT use the anon key on the backend.
4. THE SYSTEM SHALL declare type hints on every DB function signature.

### Requirement 8 — Projects API

**User Story:** As a user, I want to create, list, open, and rename my songs, so that I can manage my work from the dashboard.

#### Acceptance Criteria

1. WHEN `POST /projects` is called THEN the system SHALL create a project and return it with its id.
2. WHEN `GET /projects` is called THEN the system SHALL return all projects for the dev user.
3. WHEN `GET /projects/{project_id}` is called THEN the system SHALL return the project together with its active state.
4. WHEN `PATCH /projects/{project_id}` is called THEN the system SHALL update the project title or status.
5. THE SYSTEM SHALL use Pydantic models for every request and response body.

### Requirement 9 — Frontend API Client

**User Story:** As a developer, I want typed client functions mirroring the backend routes, so that the UI never hand-rolls fetch calls or untyped responses.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide `frontend/lib/api/projects.ts` with `createProject()`, `listProjects()`, `getProject(id)`, and `updateProject(id, data)`.
2. WHEN a request fails THEN the system SHALL handle the error gracefully and return a typed result rather than throwing uncaught.
3. THE SYSTEM SHALL type every client function against `types/api.ts`.

### Requirement 10 — Dashboard Wired to Backend

**User Story:** As a user, I want the dashboard to show my real songs from the database, so that my work persists between visits.

#### Acceptance Criteria

1. WHEN the dashboard loads THEN the system SHALL call `listProjects()` and display the real projects.
2. WHEN the user activates "New Project" THEN the system SHALL call `createProject()` and navigate to `/[projectId]/idea`.
3. THE SYSTEM SHALL show each project's title, a status badge, and a "last worked on" date.
4. WHEN the user clicks a project THEN the system SHALL navigate to `/[projectId]/idea`.

### Requirement 11 — Studio Layer Navigation

**User Story:** As a user, I want an always-visible map of the six rooms with status at a glance, so that I can move freely and never feel locked into a sequence.

#### Acceptance Criteria

1. THE SYSTEM SHALL render `components/studio/StudioNav.tsx` showing the project title, all six layers (Idea, Feel, Beat, Voice, Mix, Export), and a back link to the dashboard.
2. WHEN the user clicks the project title THEN the system SHALL allow inline editing, and WHEN the field blurs THEN the system SHALL save the new title.
3. THE SYSTEM SHALL show a per-layer status indicator (empty / in-progress / has-content) driven by the project's active state.
4. WHERE color conveys status THE SYSTEM SHALL also convey it by a non-color indicator, per the accessibility steering.
5. THE SYSTEM SHALL highlight the currently active layer.
6. THE SYSTEM SHALL NOT impose any lock or prerequisite between layers.

### Requirement 12 — Environment and Documentation

**User Story:** As a developer picking up Frank, I want example env files and a setup README, so that I can run both servers and apply the migration without guessing.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide `frontend/.env.local.example` and `backend/.env.example` listing every required variable.
2. THE SYSTEM SHALL provide a root `README.md` with instructions to install dependencies, set env vars, run both dev servers, and apply the migration.
3. WHEN a developer follows the README THEN the system SHALL support the full flow: open app, create project, navigate all six layers, and persist the project across a refresh.
