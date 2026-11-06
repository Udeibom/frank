# Spec 08 — Authentication

## Overview

Authentication is the last thing built. Email and password only. Supabase Auth handles everything. This spec is intentionally minimal.

Do not implement this spec until Specs 01–07 are complete and working.

---

## Requirements

### R1 — Signup Page
- Route: `/signup`
- Fields: email, password, confirm password
- On success: redirect to `/` (project dashboard)
- Error states: password mismatch, email already in use, weak password — all in plain language
- No email verification — just create the account and go

### R2 — Login Page
- Route: `/login`
- Fields: email, password
- On success: redirect to `/` or the page they tried to access
- Error: "That email and password didn't match" — do not specify which was wrong
- A link to `/signup`

### R3 — Session Management
- Supabase Auth handles the session token and refresh
- Next.js middleware (`middleware.ts`) protects all routes under `/(studio)/`
- Unauthenticated requests to studio routes redirect to `/login`
- The hardcoded dev user ID is removed and replaced with the real user ID from the session

### R4 — Backend JWT Validation
- Remove the hardcoded dev user bypass
- All backend routes extract the user ID from the Supabase JWT
- The Supabase service role key verifies the JWT
- Requests without a valid JWT return 401

### R5 — Logout
- A logout option in the studio sidebar (small, unobtrusive)
- Clears the Supabase session and redirects to `/login`

---

## Implementation Tasks

### Task 1 — Supabase Auth setup
- [ ] Enable email/password auth in Supabase dashboard
- [ ] Disable email confirmation (not needed for MVP)
- [ ] Install `@supabase/ssr` in the frontend

### Task 2 — Auth pages
- [ ] `/signup` page
- [ ] `/login` page
- [ ] Shared auth form component

### Task 3 — Middleware
- [ ] `frontend/middleware.ts` — protect studio routes
- [ ] Redirect logic

### Task 4 — Backend JWT validation
- [ ] Remove dev bypass
- [ ] JWT verification on all routes
- [ ] User ID extraction

### Task 5 — Logout
- [ ] Logout button in sidebar
- [ ] Session clear and redirect
