# Foundation — Implementation Plan

- [x] 1. Scaffold the monorepo
  - [x] 1.1 Initialize `frontend/` with create-next-app (TypeScript, App Router, Tailwind)
    - _Requirements: 1.1, 1.2, 2.1_
  - [x] 1.2 Initialize `backend/` with the folder structure from structure.md
    - _Requirements: 1.1, 1.2_
  - [x] 1.3 Create root `README.md` and a root `.gitignore` (node_modules, .env, __pycache__, .next, venv)
    - _Requirements: 1.3, 12.2_

- [x] 2. Configure the frontend shell
  - [x] 2.1 Install and configure shadcn/ui with the dark theme and Frank's palette variables
    - _Requirements: 2.2, 2.3_
  - [x] 2.2 Set up the root layout with Inter font and global dark styles
    - _Requirements: 2.3_
  - [x] 2.3 Create all TypeScript type files (project, audio, api) with complete types
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 3. Create the Zustand stores
  - [x] 3.1 `store/project.ts`, `store/session.ts`, `store/audio.ts`, typed against `types/`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Build the landing page
  - [x] 4.1 `app/page.tsx` — name, tagline "Use Frank.", single "Start a Song" CTA, no nav header
    - _Requirements: 2.4_

- [x] 5. Build the studio shell
  - [x] 5.1 `app/(studio)/layout.tsx` with the persistent sidebar slot
    - _Requirements: 2.5_
  - [x] 5.2 `components/studio/StudioNav.tsx` — editable title, six layers, status indicators, back link
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  - [x] 5.3 `app/(studio)/page.tsx` — dashboard with empty state and project list
    - _Requirements: 2.7, 10.3_
  - [x] 5.4 `app/(studio)/[projectId]/layout.tsx` — load project, populate store
    - _Requirements: 3.1_
  - [x] 5.5 All six placeholder room pages (idea, feel, beat, voice, mix, export)
    - _Requirements: 2.6_

- [x] 6. Set up the FastAPI backend
  - [x] 6.1 `app/main.py` with CORS, health check, router registration
    - _Requirements: 5.1, 5.3, 5.4_
  - [x] 6.2 `app/config.py` with pydantic-settings and fail-fast validation
    - _Requirements: 5.6_
  - [x] 6.3 `requirements.txt` with pinned versions and `Procfile` for Render
    - _Requirements: 5.2_
  - [x] 6.4 All router files with placeholder `{"status": "not_implemented"}` routes
    - _Requirements: 5.5_

- [x] 7. Create the Supabase schema and DB layer
  - [x] 7.1 Write `backend/db/migrations/001_initial_schema.sql` with all 12 tables and constraints
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  - [x] 7.2 Apply the migration to the Supabase project
    - _Requirements: 6.1_
  - [x] 7.3 `app/db/client.py` — Supabase client with the service role key
    - _Requirements: 7.1, 7.3_
  - [x] 7.4 `app/db/projects.py` — all six project functions with type hints
    - _Requirements: 7.2, 7.4_

- [x] 8. Wire the projects API end to end
  - [x] 8.1 `app/routers/projects.py` — all four routes with Pydantic models
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 8.2 `frontend/lib/api/projects.ts` — four typed client functions with graceful errors
    - _Requirements: 9.1, 9.2, 9.3_
  - [x] 8.3 Dashboard wired to real backend data; "New Project" creates and navigates
    - _Requirements: 10.1, 10.2, 10.4_

- [x] 9. Wire studio nav to project state
  - [x] 9.1 Inline-editable title from the sidebar; layer status from DB active state
    - _Requirements: 11.2, 11.3_

- [x] 10. Environment and documentation
  - [x] 10.1 `.env.example` files for frontend and backend
    - _Requirements: 5.7, 12.1_
  - [x] 10.2 README with full local setup instructions
    - _Requirements: 12.2_
  - [x] 10.3 Verify full flow: create project, navigate all six layers, persist on refresh
    - _Requirements: 12.3_
