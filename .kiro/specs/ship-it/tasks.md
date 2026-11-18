# Ship It - Implementation Plan (spec 13)

Needs from the founder: a Render account (API key, or create the service in the dashboard) and a Vercel token
(or link the GitHub repo in the Vercel dashboard). Everything else Frank's side can do.

- [x] 1. `render.yaml`, production settings, shared heavy-job semaphore, memory logging — _Evidence: render.yaml (Docker web service, free plan, health check /health, secrets `sync: false`, ENVIRONMENT=production); backend/app/config.py `environment`; jobs/heavy.py `HEAVY` (one heavy job at a time, used by the beat, refine, intake and surprise runners), `release_memory`, `log_memory`. No test covers the gate_
  - _Requirements: 1.1, 2.1_
- [x] 2. Backend deployed on Render; health check green; memory measured on a full beat — _Evidence: `GET https://frank-api-pzjo.onrender.com/health` returned {"status":"ok"} when I checked today; scripts/ops/e2e.py (a full walk through build, mix and export) passed on it several times (build-progress Nov 18); jobs/heavy.py records a beat peaking near 435 MB and 353 MB resident falling to 277 MB after `malloc_trim` (measured Nov 17-18; figures not re-measured by me)_
  - _Requirements: 1.1, 2.1_
- [ ] 3. Frontend deployed on Vercel; CORS locked; Supabase redirect URLs — _PARTLY DONE: https://frank-bay-zeta.vercel.app returned 200 today; CORS checked by me against the deployed API: a preflight from that origin gets `access-control-allow-origin: https://frank-bay-zeta.vercel.app`, a preflight from https://evil.example gets 400. MISSING: the Supabase redirect URLs were not checked_
  - _Requirements: 1.2, 1.3_
- [ ] 4. All migrations on production; RLS audit by the Database Steward agent — _PARTLY DONE: build-progress records migrations 005 to 009 applied and scripts/ops/rls_check.py "RLS OK" with two users (Nov 18). MISSING: no record that 001 to 004 and 006 were checked on production, and no Database Steward audit; I did not query the live database_
  - _Requirements: 1.4_
- [ ] 5. Secrets and dev bypass audit — _NOT DONE: no audit is recorded. Facts seen: backend/.env is git-ignored and no .env file is tracked; render.yaml sets ENVIRONMENT=production and the bypass is tied to that setting (config.py, auth.py), not tested on the deployed API_
  - _Requirements: 1.5_
- [ ] 6. Cold start and progress wording checked on the deployed URL — _NOT DONE: no "Frank is waking up" message exists in the frontend (searched for "waking" and "wake" in frontend/app, components, lib: no match), so deployment.md's 3-second rule is not built_
  - _Requirements: 2.2, 2.3_
- [ ] 7. Demo stories 1, 2, 3 run on the deployed URL with a fresh account; records in docs/demo-runs/ — _NOT DONE: there is no docs/ folder. scripts/ops/e2e.py creates a fresh account and walks the story over HTTP on the deployed backend, with story 3 inside it (build-progress Nov 18), but that is not a browser run of the three stories and no run record is saved in the repo_
  - _Requirements: 3.1, 3.2_
- [ ] 8. Licence file — _NOT DONE: no LICENSE file in the repository root_
  - _Requirements: 4.1_
