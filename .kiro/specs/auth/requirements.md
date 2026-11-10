# Auth — Requirements

## Introduction

Frank uses Supabase Auth with email and password only. Until now every request ran as one hardcoded dev user, and only the projects router checked who owned a project. Every other router trusted whatever `project_id` it was given. With real accounts that is an insecure direct object reference: any signed-in user could read or change another user's song by ID. This spec therefore covers sign-in, session handling, backend token validation, and an ownership check on every project-scoped route. It also turns on Row Level Security, which the Supabase advisor flagged as disabled on all 12 tables.

It traces to `auth.md` and `deployment.md`.

## Requirements

### Requirement 1 — Sign Up

**User Story:** As a new user, I want to create an account with an email and password and go straight into Frank, so that signing up never gets in the way of making music.

#### Acceptance Criteria

1. WHEN a visitor opens `/signup` THEN the system SHALL show email, password, and confirm-password fields.
2. WHEN the passwords differ THEN the system SHALL say so in plain language and SHALL NOT submit.
3. IF the email is already registered or the password is too weak THEN the system SHALL explain it in plain language.
4. WHEN sign-up succeeds THEN the system SHALL start a session and take the user to their songs.
5. THE SYSTEM SHALL NOT require email verification.

### Requirement 2 — Log In

**User Story:** As a returning user, I want to log in and land where I was going, so that I pick up my songs quickly.

#### Acceptance Criteria

1. WHEN a visitor opens `/login` THEN the system SHALL show email and password fields and a link to `/signup`.
2. IF the credentials are wrong THEN the system SHALL say "That email and password didn't match" and SHALL NOT reveal which part was wrong.
3. WHEN login succeeds THEN the system SHALL redirect to the page the user originally tried to open, or to their songs.

### Requirement 3 — Protected Studio and Session

**User Story:** As a user, I want my studio to be private to me, so that nobody else can open my songs.

#### Acceptance Criteria

1. IF a request for a studio page has no valid session THEN the system SHALL redirect to `/login`, remembering the destination.
2. THE SYSTEM SHALL keep the landing page, `/login`, and `/signup` public.
3. WHEN a session nears expiry THEN the system SHALL refresh it without interrupting the user.
4. THE SYSTEM SHALL use the real user id from the session wherever the hardcoded dev id was used.

### Requirement 4 — Backend Token Validation

**User Story:** As the product, I want the server to know exactly who is calling, so that data access follows identity and not trust.

#### Acceptance Criteria

1. WHEN a request reaches a protected backend route THEN the system SHALL validate the bearer token with Supabase Auth and take the user id from the result.
2. IF the token is missing, invalid, or expired THEN the system SHALL respond 401 with a plain-language message.
3. THE SYSTEM SHALL keep `/health` public.
4. THE SYSTEM SHALL permit a development-only bypass only when `ENVIRONMENT=development` and `AUTH_REQUIRED=false`, and SHALL ignore that flag in any other environment.

### Requirement 5 — Ownership on Every Project Route

**User Story:** As a user, I want only me to be able to read or change my song, even if someone learns its id.

#### Acceptance Criteria

1. WHEN any route under `/projects/{project_id}/…` is called THEN the system SHALL verify the project belongs to the caller before running it.
2. IF the project does not exist or belongs to someone else THEN the system SHALL respond 404 in both cases, so it never confirms that another user's id exists.
3. WHEN `/jobs/{job_id}/status` is called THEN the system SHALL verify the job's project belongs to the caller.
4. THE SYSTEM SHALL enforce this once, at the router level, so a new route cannot forget it.

### Requirement 6 — Row Level Security

**User Story:** As the product, I want the database itself to refuse anonymous access, so that a leaked public key exposes nothing.

#### Acceptance Criteria

1. THE SYSTEM SHALL enable Row Level Security on all 12 application tables.
2. THE SYSTEM SHALL grant no table access to the `anon` or `authenticated` roles; the backend reaches data through the service role.
3. WHEN RLS is enabled THEN the system SHALL continue to work end to end for the backend.
4. THE SYSTEM SHALL record any remaining exposure, such as public storage buckets, rather than hide it.

### Requirement 7 — Log Out

**User Story:** As a user on a shared computer, I want to log out easily.

#### Acceptance Criteria

1. THE SYSTEM SHALL show a small, unobtrusive log-out control in the studio sidebar.
2. WHEN the user logs out THEN the system SHALL clear the session and redirect to `/login`.

### Requirement 8 — Songs Page Is Reachable

**User Story:** As a user, I want a page that lists my songs, so that I can come back to them.

#### Acceptance Criteria

1. THE SYSTEM SHALL serve the song list at `/songs`.
2. WHEN the user follows "All Songs" from the studio THEN the system SHALL open that list and SHALL NOT show the landing page.
