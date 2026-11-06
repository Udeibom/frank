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
│   │   │       ├── idea/        # Layer 1: Idea Room
│   │   │       ├── feel/        # Layer 2: Feel Lab
│   │   │       ├── beat/        # Layer 3: Beat Room
│   │   │       ├── voice/       # Layer 4: Voice Room
│   │   │       ├── mix/         # Layer 5: Mix Room
│   │   │       └── export/      # Layer 6: Export Room
│   │   ├── api/                 # Next.js API routes (thin proxies only)
│   │   ├── layout.tsx           # Root layout
│   │   └── page.tsx             # Landing page
│   ├── components/              # Shared UI components
│   │   ├── ui/                  # shadcn/ui base components
│   │   ├── studio/              # Studio-specific components
│   │   ├── audio/               # Audio player, waveform, recorder
│   │   └── conversation/        # Chat/conversation UI
│   ├── lib/                     # Utilities and helpers
│   │   ├── audio/               # Audio utility functions
│   │   ├── api/                 # API client functions
│   │   └── utils.ts             # General utilities
│   ├── store/                   # Zustand stores
│   │   ├── project.ts           # Project state
│   │   ├── session.ts           # Current session state
│   │   └── audio.ts             # Audio playback state
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
│   │   │   │   ├── musicgen.py  # MusicGen API wrapper
│   │   │   │   └── fingerprint.py # Musical fingerprint system
│   │   │   ├── llm/             # LLM integration
│   │   │   │   ├── groq.py      # Groq API client
│   │   │   │   ├── prompts.py   # All system prompts
│   │   │   │   └── translator.py # Language → audio parameter translation
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

## The Six Layers Are Pages, Not Modals

Each layer (Idea, Feel, Beat, Voice, Mix, Export) is its own route inside a project. The user navigates between them. All layers are always accessible — the user is never locked into a linear flow. The studio layout persists across all layer pages.

## Audio Files Never Live in the Repo

All audio files (takes, stems, beats, exports) are stored in Supabase Storage. The frontend receives signed URLs from the backend and streams/downloads from Supabase directly. Never commit audio files.

## TypeScript Is Required on the Frontend

All `.tsx` and `.ts` files must be properly typed. No `any` unless there is an explicit comment explaining why. API response types must be defined in `types/api.ts`.

## Python Type Hints Are Required on the Backend

All function signatures must have type hints. Pydantic models must be used for all request and response bodies.
