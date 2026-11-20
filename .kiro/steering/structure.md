# Frank — Project Structure

## Repository Layout

```
Frank/
├── frontend/                    # Next.js application
│   ├── app/                     # App Router pages and layouts
│   │   ├── (auth)/              # Auth pages (login, signup) — built last
│   │   ├── (studio)/            # Main studio pages
│   │   │   ├── layout.tsx       # Studio shell with persistent nav
│   │   │   ├── page.tsx         # Project dashboard / home
│   │   │   └── [projectId]/     # Per-project studio
│   │   │       ├── page.tsx     # Project overview
│   │   │       ├── idea/        # Room 1: shown to the user as "Words"
│   │   │       ├── feel/        # Room 2: shown as "Feeling"
│   │   │       ├── beat/        # Room 3: shown as "Music"
│   │   │       ├── voice/       # Room 4: shown as "Voice"
│   │   │       ├── mix/         # Room 5: shown as "Blend"
│   │   │       └── export/      # Room 6: shown as "Finish"
│   │   ├── api/                 # Next.js API routes (thin proxies only)
│   │   ├── layout.tsx           # Root layout
│   │   └── page.tsx             # Landing page
│   ├── components/              # Shared UI components
│   │   ├── ui/                  # shadcn/ui base components
│   │   ├── shell/               # SongStrip, Rail, FrankPanel: the same in every room
│   │   ├── studio/              # Room-specific components
│   │   ├── audio/               # PlayButton, Waveform, Lane, recorder (all play through the AudioEngine)
│   │   └── conversation/        # Frank panel pieces: FrankNote, ChangeLine, message list
│   ├── lib/                     # Utilities and helpers
│   │   ├── audio/               # Audio utility functions
│   │   ├── api/                 # API client functions
│   │   └── utils.ts             # General utilities
│   ├── store/                   # Zustand stores
│   │   ├── project.ts           # Project state
│   │   ├── session.ts           # Current session state
│   │   └── audio.ts             # The AudioEngine: the one place anything plays from
│   ├── types/                   # TypeScript type definitions
│   │   ├── project.ts           # Project, layer, version types
│   │   ├── audio.ts             # Audio file, take, stem types
│   │   └── api.ts               # API request/response types
│   ├── hooks/                   # React hooks
│   └── public/                  # Static assets
│
├── backend/                     # Python FastAPI application
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── routers/             # Route handlers grouped by domain
│   │   │   ├── projects.py      # Project CRUD
│   │   │   ├── lyrics.py        # Idea Room / lyrics
│   │   │   ├── feel.py          # Feel Lab
│   │   │   ├── beat.py          # Beat Room / instrumental
│   │   │   ├── voice.py         # Voice Room / vocal processing
│   │   │   ├── mix.py           # Mix Room
│   │   │   ├── export.py        # Export / mastering
│   │   │   └── conversation.py  # LLM conversation layer
│   │   ├── services/            # Business logic
│   │   │   ├── audio/           # Audio processing services
│   │   │   │   ├── pitch.py     # Pitch detection and correction
│   │   │   │   ├── mixing.py    # Mixing and effects
│   │   │   │   ├── mastering.py # Mastering chain
│   │   │   │   └── export.py    # Format conversion
│   │   │   ├── generation/      # Instrumental generation
│   │   │   │   ├── theory.py / composer.py / renderer.py / beat.py / texture.py / hum.py  # procedural engine
│   │   │   │   └── fingerprint.py # Musical fingerprint system
│   │   │   ├── llm/             # LLM integration
│   │   │   │   ├── groq_client.py # Groq API client
│   │   │   │   ├── prompts.py   # All system prompts
│   │   │   │   └── (translator.py planned: shared song brief + role routing)
│   │   │   └── storage/         # Supabase storage operations
│   │   ├── models/              # Pydantic data models
│   │   ├── db/                  # Database access layer
│   │   └── config.py            # Settings and environment
│   ├── requirements.txt
│   └── Procfile                 # For Render deployment
│
├── .kiro/
│   ├── steering/                # Steering documents
│   └── hooks/                   # Agent hooks
│
└── README.md
```

## Naming Conventions

- **Files**: `kebab-case.tsx` for components, `camelCase.ts` for utilities
- **Components**: PascalCase, one component per file
- **API routes**: `snake_case` for Python, matching REST conventions
- **Environment variables**: `SCREAMING_SNAKE_CASE`
- **Database tables**: `snake_case`
- **Supabase storage buckets**: `kebab-case` (`voice-takes`, `beat-stems`, `exports`)

## The Six Rooms Are Pages, Not Modals

Each room is its own route inside a project. The user sees the plain names **Words, Feeling, Music, Voice, Blend, Finish**; the route slugs stay `idea`, `feel`, `beat`, `voice`, `mix`, `export` so links and saved state do not break. Code, API and database names also keep the original terms (`beat`, `mix`, `export`); only what the user reads changes. All rooms are always accessible, with no locks and no linear flow.

The shell (Song Strip, Rail, Frank panel) lives in the project layout and **never unmounts** while navigating between rooms or while the project loads. Each room fills the stage and may lay it out however its work needs (see `design-and-ui.md`). Nothing in a room creates its own `Audio`; everything plays through the single AudioEngine in `store/audio.ts`.

## Audio Files Never Live in the Repo

All audio files (takes, stems, beats, exports) are stored in Supabase Storage. The frontend receives signed URLs from the backend and streams/downloads from Supabase directly. Never commit audio files.

## TypeScript Is Required on the Frontend

All `.tsx` and `.ts` files must be properly typed. No `any` unless there is an explicit comment explaining why. API response types must be defined in `types/api.ts`.

## Python Type Hints Are Required on the Backend

All function signatures must have type hints. Pydantic models must be used for all request and response bodies.
