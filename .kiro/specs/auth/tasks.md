# Auth — Implementation Plan

- [x] 1. Supabase setup
  - [x] 1.1 (user) "Confirm email" turned off in the Supabase dashboard
    - _Requirements: 1.5_
  - [x] 1.2 `@supabase/ssr` and `@supabase/supabase-js` already installed
    - _Requirements: 3.3_

- [x] 2. Backend token validation and ownership
  - [x] 2.1 `app/auth.py`: `get_current_user_id` (validate via Supabase, 60 s cache, guarded dev bypass)
    - _Requirements: 4.1, 4.2, 4.4_
  - [x] 2.2 `require_project_access` dependency (404 for missing or foreign)
    - _Requirements: 5.1, 5.2_
  - [x] 2.3 All project-scoped routers mounted with the dependency; `/health` stays public; `projects.py` uses it too
    - _Requirements: 4.3, 5.4_
  - [x] 2.4 Job ownership check in `/jobs/{id}/status`
    - _Requirements: 5.3_
  - [x] 2.5 Property tests for the ownership rule and bypass guard (`tests/test_properties_auth.py`)
    - _Requirements: 4.4, 5.2_

- [x] 3. Row Level Security
  - [x] 3.1 Migration `002_enable_rls.sql` enabling RLS on all 12 tables
    - _Requirements: 6.1, 6.2_
  - [x] 3.2 Applied. Before: the public anon key read projects, lyrics and takes. After: it reads 0 rows, and the backend (service role) still reads everything.
    - _Requirements: 6.3_
  - [x] 3.3 Remaining exposure recorded (public buckets, below)
    - _Requirements: 6.4_

- [x] 4. Frontend session
  - [x] 4.1 Supabase browser client + `middleware.ts` (protect studio, keep public pages public, refresh session)
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 4.2 API client attaches the bearer token; a 401 sends the user to `/login`
    - _Requirements: 4.1, 4.2_
  - [x] 4.3 Session store no longer pretends to be a dev user
    - _Requirements: 3.4_

- [x] 5. Pages
  - [x] 5.1 `/signup` with plain-language errors
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 5.2 `/login` with the non-revealing error and post-login redirect
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 5.3 Log-out control in the sidebar
    - _Requirements: 7.1, 7.2_
  - [x] 5.4 Dashboard moved to `/songs`; "All Songs" and the landing CTA fixed; a missing or foreign song redirects to `/songs`
    - _Requirements: 8.1, 8.2_

- [x] 6. Verify end to end
  - [x] 6.1 Live, two real accounts: 17/17 request checks plus 3 job-ownership checks passed (no token 401, foreign project 404, own project 200, `/health` public)
    - _Requirements: 4.2, 5.2_
  - [x] 6.2 Browser: signed-out `/songs` redirects to login with `next`; wrong login shows the vague message; mismatched passwords blocked; sign-up lands on `/songs`; new song opens; log out; opening the song URL signed out redirects; login returns to that song
    - _Requirements: 1.2, 1.4, 2.2, 2.3, 3.1, 7.2_

## Known gaps (not done)

- Storage buckets other than `exports` are public. Audio URLs play without a token for anyone who holds the URL.
- Existing songs belong to the old dev user id (`00000000-…-0001`), so no real account can see them until they are reassigned.
- Not tested: expired-token refresh mid-session, and `AUTH_REQUIRED=false` against a running server (only the rule is property-tested).
- No password reset and no rate limiting beyond what Supabase Auth applies.
