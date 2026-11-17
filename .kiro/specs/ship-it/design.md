# Ship It - Design (spec 13)

- Render: Docker web service, root `backend/`, Dockerfile path `backend/Dockerfile`, health check `/health`,
  env vars per deployment.md (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, `ALLOWED_ORIGINS`,
  `ENVIRONMENT=production`, optional `GEMINI_API_KEY`). Created through the Render dashboard or the Render API
  with an API key from the founder; `render.yaml` blueprint committed so it is repeatable.
- Vercel: project root `frontend/`, env `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_URL`. Deployed with the Vercel CLI using a token from the founder, or by linking the GitHub
  repo in the Vercel dashboard (deploys from `main`).
- Memory: one heavy job at a time already (semaphores in beat, hum, intake runners); add a single process-wide
  heavy-job semaphore shared by beat, mix, export and listen; measure peak RSS during a full beat with
  `/proc/self/status` logged at job end.
- Supabase Auth: add the Vercel URL to allowed redirect URLs.
- Demo runs: scripted with the Integration Tester agent and Playwright against the production URL; results in
  `docs/demo-runs/`.
- Licence: MIT unless the founder chooses otherwise (the founder's call; flagged).
