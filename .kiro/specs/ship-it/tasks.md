# Ship It - Implementation Plan (spec 13)

Needs from the founder: a Render account (API key, or create the service in the dashboard) and a Vercel token
(or link the GitHub repo in the Vercel dashboard). Everything else Frank's side can do.

- [ ] 1. `render.yaml`, production settings, shared heavy-job semaphore, memory logging
  - _Requirements: 1.1, 2.1_
- [ ] 2. Backend deployed on Render; health check green; memory measured on a full beat
  - _Requirements: 1.1, 2.1_
- [ ] 3. Frontend deployed on Vercel; CORS locked; Supabase redirect URLs
  - _Requirements: 1.2, 1.3_
- [ ] 4. All migrations on production; RLS audit by the Database Steward agent
  - _Requirements: 1.4_
- [ ] 5. Secrets and dev bypass audit
  - _Requirements: 1.5_
- [ ] 6. Cold start and progress wording checked on the deployed URL
  - _Requirements: 2.2, 2.3_
- [ ] 7. Demo stories 1, 2, 3 run on the deployed URL with a fresh account; records in docs/demo-runs/
  - _Requirements: 3.1, 3.2_
- [ ] 8. Licence file
  - _Requirements: 4.1_
