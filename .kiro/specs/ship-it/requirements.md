# Ship It - Requirements (spec 13)

## Introduction
Frank on the public internet, free tier, with the three demo stories working on the deployed URL. Follows
`deployment.md`.

## Requirements

### Requirement 1 - Deployed
#### Acceptance Criteria
1. THE backend SHALL run on Render as a Docker web service from `backend/Dockerfile` (FluidSynth, FFmpeg,
   Rubber Band, SoundFont fetched at build), with `GET /health`.
2. THE frontend SHALL run on Vercel with `NEXT_PUBLIC_API_URL` pointing at the backend.
3. CORS SHALL allow only the Vercel URL (and localhost in development).
4. Every migration SHALL be applied to the production database, and row level security SHALL be on for every
   table holding user data (auth checklist).
5. No secret SHALL be in the repository; the dev auth bypass SHALL be off in production.

### Requirement 2 - Works within the free tier
#### Acceptance Criteria
1. THE backend SHALL stay within the free instance's memory (512 MB) during a full beat render, a mix and an
   export, measured on the deployed service.
2. A cold start SHALL show "Frank is waking up..." when the health check takes longer than 3 seconds, never an error.
3. Long jobs SHALL show honest progress and wait times measured on the deployed service.

### Requirement 3 - The demo stories pass on the deployed URL
#### Acceptance Criteria
1. Demo 1 (a feeling and lyrics become a sung, finished song), demo 2 (a phone hum becomes a produced song),
   and demo 3 (the "something feels wrong" producer conversation) SHALL each be run end to end on the
   deployed URL with a fresh account, and the run recorded (steps, outputs, times, problems).
2. The voice-first and beat-first paths and an MP3 download SHALL be checked (deployment checklist).

### Requirement 4 - Ready to show
#### Acceptance Criteria
1. THE repository SHALL have a licence file.
2. THE founder records the demo video and write-up (founder tasks; Frank's side is a demo script and a
   working deployment).
