# Frank — Deployment

## Free Tier Architecture

Every service in Frank's production deployment uses a free tier. No credit card required anywhere.

| Component | Service | Free Tier Limits |
|---|---|---|
| Frontend | Vercel | Unlimited deploys, 100GB bandwidth/month |
| Backend API | Render (free web service) | 750 hours/month, spins down after 15min inactivity |
| Database | Supabase | 500MB database, 1GB storage, 50MB file uploads |
| LLM | Groq | 6,000 tokens/min on free tier |
| Speech-to-text | Hugging Face Inference API | Rate limited but free |
| Music generation | Hugging Face or Replicate | Replicate: $0.000225/sec, HF: free with rate limits |
| Audio storage | Supabase Storage | Included in free tier |

## Render Cold Start

Render free tier spins down after 15 minutes of inactivity. On the first request after spin-down, the response takes 30–60 seconds.

Mitigation: Show a "Frank is waking up..." message on the frontend if the backend health check takes more than 3 seconds to respond. Do not let this look like an error.

## Environment Configuration

### Frontend (Vercel)
Environment variables set in Vercel dashboard:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` (the Render backend URL)

### Backend (Render)
Environment variables set in Render dashboard:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GROQ_API_KEY`
- `HUGGINGFACE_API_KEY`
- `REPLICATE_API_TOKEN`
- `ALLOWED_ORIGINS` (Vercel frontend URL for CORS)

## CORS

The backend must only accept requests from the Vercel frontend URL in production. In development, `localhost:3000` is allowed.

## Audio File Size Limits

Render free tier has memory limits. Audio processing jobs must:
- Process files in chunks if large
- Clean up temp files immediately after processing
- Not hold large files in memory longer than needed

Upload size limit: 50MB per file (enforced at the API level).

## Deployment Checklist (Before Submission)

- [ ] All environment variables set on Vercel and Render
- [ ] CORS configured correctly
- [ ] Supabase Row Level Security policies set (after auth is added)
- [ ] Health check endpoint on backend (`GET /health`)
- [ ] Frontend handles backend cold start gracefully
- [ ] Full voice-first demo path tested on production URL
- [ ] Beat-first path tested on production URL
- [ ] Export produces a downloadable MP3
- [ ] No API keys in the codebase
