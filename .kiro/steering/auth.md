# Frank — Authentication

## Approach

Frank uses Supabase Auth with email and password. That is the only authentication method for this version.

No OAuth, no magic links, no phone auth, no social login.

## When to Implement

Authentication is implemented **last**, after all production features (Idea Room, Feel Lab, Beat Room, Voice Room, Mix Room, Export Room) are working.

During development, all routes are accessible without auth. A hardcoded dev user ID is used in local development.

## Why Last

Authentication is infrastructure, not product. The judges are evaluating Frank on what it does for the user musically, not on how securely it gates access. Building auth first is a common trap that consumes time without delivering user value.

## Implementation (When the Time Comes)

- Supabase Auth handles the session, JWT, and token refresh
- Next.js middleware protects `/studio` routes — redirect to `/login` if no session
- The backend validates the Supabase JWT on every request using the Supabase service role key
- User ID from the JWT is used for all database queries — users can only access their own projects

## Pages Needed (Built Last)

- `/login` — email + password form
- `/signup` — email + password + confirm password
- No email verification for MVP (too much friction)
- No password reset for MVP (can add if time allows)

## Dev Bypass

In local development (`NODE_ENV=development`), a middleware bypass allows accessing studio routes without a session. This must be removed before production deployment.
