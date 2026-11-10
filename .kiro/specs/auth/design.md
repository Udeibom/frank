# Auth — Design

## Overview

Supabase Auth issues the session; the frontend holds it in cookies via `@supabase/ssr`; the backend validates each bearer token and checks project ownership in one dependency. The database refuses anonymous access with Row Level Security.

## Architecture

```
Browser ── supabase-js (anon key) ──▶ Supabase Auth  (signUp / signIn / refresh)
   │  session in cookies (@supabase/ssr)
   │  middleware.ts: no session on a studio page → /login?next=…
   │
   └─ fetch ── Authorization: Bearer <access_token> ──▶ FastAPI
                                                        │ app/auth.py
                                                        │  GET {SUPABASE_URL}/auth/v1/user  (cached 60 s)
                                                        │  → user id
                                                        │ require_project_access(project_id, user)
                                                        │  → project row, 404 unless owner
                                                        ▼
                                                  service-role DB access (bypasses RLS)
```

## Decisions

- **Validate by asking Supabase (`/auth/v1/user`), not by verifying the JWT locally.** Projects may use either legacy HS256 secrets or newer asymmetric signing keys; asking Auth works with both and needs no secret on our side. The cost is one network call per request, so we cache a validated token for 60 seconds, bounded in size.
- **Ownership is a router-level dependency.** All project-scoped routers share the `/projects/{project_id}/…` prefix, so `include_router(..., dependencies=[Depends(require_project_access)])` covers every route, including future ones. This replaces the per-route check that only `projects.py` had.
- **404, not 403.** A foreign project returns exactly what a missing project returns.
- **RLS on, with no policies.** The browser never queries tables directly; all data goes through the backend using the service role, which bypasses RLS. Enabling RLS with no policies therefore closes the anon/authenticated roles completely and costs the backend nothing. The advisory raised earlier worried this would lock out the backend; that concern was wrong for the service role and is verified in tasks.
- **Dev bypass is guarded twice.** `AUTH_REQUIRED=false` only takes effect when `ENVIRONMENT=development`. Production default is strict.
- **Dashboard moves to `/songs`.** Two pages (`app/page.tsx` and `app/(studio)/page.tsx`) resolved to `/`; the landing page won and the dashboard was unreachable. The landing page keeps `/`.

## Components

Frontend: `lib/supabase/client.ts`, `lib/supabase/middleware.ts`, `middleware.ts`, `app/(auth)/login`, `app/(auth)/signup`, a shared `AuthForm`, `lib/api/client.ts` (adds the bearer token), `store/session.ts` (real user), `StudioNav` (log out), `app/(studio)/songs/page.tsx`.

Backend: `app/auth.py` (`get_current_user_id`, `require_project_access`), `config.py` (`auth_required`), `main.py` (mounting), `routers/jobs.py` (job ownership).

Database: migration `002_enable_rls.sql`.

## Error Handling

- 401 for a bad or missing token; the frontend sends the user to `/login`.
- Login errors never say which of email or password was wrong.
- If Supabase Auth is unreachable the backend returns 503, not 401, so a flaky network does not log people out.

## Testing Strategy

- Property-based: ownership rule (a project is accessible iff its `user_id` equals the caller), and the bypass flag is ignored outside development.
- Live: with auth on, no token → 401; user A's token on user B's project → 404; own project → 200; `/health` → 200.
- After RLS: the backend still reads and writes; the anon key reads nothing.

## Known limits

- Storage buckets other than `exports` are public, so audio URLs work without a token for anyone who has the URL. URLs are unguessable but not secret. Making them private needs signed URLs everywhere audio is played.
- No password reset, no email verification, no rate limiting on login (Supabase applies its own).
