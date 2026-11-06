# Frank

> You have the song. Frank handles the rest.

Frank is a web-based music production platform for people who have music inside them but no music knowledge, no instruments, and no money for a producer. It is not a music generator — it is a collaborative production environment where the user and the system work together, iteratively, until the song in the user's head is a real, finished song.

---

## Project Structure

```
Frank/
├── frontend/       # Next.js 14 app (Vercel)
├── backend/        # Python FastAPI server (Render)
└── .kiro/          # Kiro specs, steering docs, hooks, agents
```

---

## Local Setup

### Prerequisites

- Node.js 18+
- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier)
- A [Groq](https://console.groq.com) API key (free tier)

### 1. Clone and install

```bash
git clone <repo-url>
cd Frank

# Frontend
cd frontend
npm install

# Backend
cd ../backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
# Frontend
cp frontend/.env.local.example frontend/.env.local
# Fill in your Supabase URL and anon key

# Backend
cp backend/.env.example backend/.env
# Fill in your Supabase URL, service role key, and API keys
```

### 3. Set up the database

1. Open your Supabase project
2. Go to **SQL Editor**
3. Copy and run the contents of `backend/db/migrations/001_initial_schema.sql`

### 4. Run the development servers

In two separate terminals:

```bash
# Terminal 1 — Frontend
cd frontend
npm run dev
# Runs at http://localhost:3000

# Terminal 2 — Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
# Runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

---

## The Six Layers

| Layer | What happens |
|---|---|
| **Idea Room** | Write and develop your lyrics with an AI co-writer |
| **Feel Lab** | Discover the feeling of your song through conversation and sound |
| **Beat Room** | Build the instrumental, section by section, through listening |
| **Voice Room** | Record, compare, and refine your vocal takes |
| **Mix Room** | Balance everything until it sounds right |
| **Export** | Download your finished song as an MP3 |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React, Tailwind CSS, shadcn/ui, Zustand |
| Backend | Python FastAPI, Supabase |
| Audio processing | FFmpeg, librosa, pyrubberband, pedalboard (Spotify), Basic Pitch (Spotify) |
| AI | Groq (Llama 3.3 70B), Whisper (Hugging Face), MusicGen (Meta) |
| Deployment | Vercel (frontend), Render (backend), Supabase (database + storage) |

---

## Deployment

See `.kiro/steering/deployment.md` for the full deployment guide.

Both services deploy from `main` — frontend to Vercel, backend to Render. All free tier.

---

Built with [Kiro](https://kiro.dev) for Kiroween 2026.
