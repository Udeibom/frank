# Frank — Tech Stack

## Guiding Constraint

Every technology choice must work on a free tier and must not require GPU compute on the developer's local machine (Core i5 3rd gen, 4GB RAM). Heavy lifting happens in the cloud.

## Frontend

- **Next.js 14** (App Router) — main application shell
- **React 18** — UI layer
- **Tone.js** — in-browser audio scheduling, playback, real-time effects
- **Web Audio API** — low-level audio recording and playback
- **MediaRecorder API** — in-browser vocal recording
- **Zustand** — client-side state management for project/session
- **shadcn/ui** — UI component library
- **Tailwind CSS** — styling
- **TypeScript** — all frontend code is TypeScript
- Deployed to **Vercel** (free tier)

## Backend

- **Python 3.11+** with **FastAPI** — main API server
- **Supabase** — PostgreSQL database, user auth (email/password only), file storage
- **Supabase Storage** — audio file storage (takes, beats, stems, exports, voice memos)
- Deployed to **Render** (free tier)

## Audio Processing (Server-Side, CPU Only)

- **Rubber Band Library** (via pyrubberband) — pitch shifting and time stretching
- **FFmpeg** — audio encoding, mixing, format conversion, MP3 export
- **librosa** — audio analysis, pitch detection, tempo detection, onset detection
- **pedalboard (Spotify)** — audio effects chain (reverb, compression, EQ, limiting)
- **Basic Pitch (Spotify)** — pitch detection and MIDI extraction from vocal recordings
- **soundfile / pydub** — audio file I/O

All audio processing runs on the Render backend. No GPU required — all operations are CPU-based.

## AI / ML (External APIs, Free Tiers)

- **Groq API** (`openai/gpt-oss-120b`) — conversation layer, plain language to music parameter translation, lyric co-writing, mix instruction interpretation. Note: Groq's model lineup shifts over time; `llama-3.3-70b-versatile` was retired from this account, so Frank uses `openai/gpt-oss-120b`, the strongest JSON-mode-capable chat model currently on the free tier. The model name lives in one place: `backend/app/services/llm/groq_client.py`.
- **Whisper** (`whisper-large-v3-turbo` via Groq) — speech-to-text for voice memo transcription. Originally planned for Hugging Face, but HF retired the `api-inference.huggingface.co` domain; Groq hosts Whisper directly and is already our provider, so transcription runs through Groq.
- **Basic Pitch** — runs locally on backend server, no API needed

### Instrumental generation: Frank's own procedural engine (not MusicGen)

MusicGen was the original plan, but during Spec 03 we confirmed there is **no free hosted path** to it anymore: Hugging Face retired the inference-API domain and `hf-inference` no longer serves MusicGen; Replicate requires paid credit (402 Insufficient credit). Self-hosting a 3B-parameter model needs a GPU and gigabytes of RAM — impossible on Render's free tier.

So Frank generates instrumentals with its **own procedural music engine**, which turns out to fit the product vision better than MusicGen ever did:

- **Music theory in code** → chord progressions, basslines, melodies, and drum patterns are derived explicitly from the musical fingerprint (key, mode, tempo, energy, density).
- **MIDI → audio via FluidSynth + SoundFont** → real recorded instrument samples (SF2 SoundFonts), rendered on CPU. A piano sounds like a piano.
- **Fully controllable** → because every element is an explicit musical decision, "the bass feels too busy" is a real change to the bass pattern, not a re-roll of a black box. This is the two-way production Frank promises, and the opposite of one-shot generation.
- **Free, CPU-only, no rate limits, never sleeps** → runs anywhere, including Render free tier.

Engine stack:
- **FluidSynth** (`libfluidsynth`, system package) + **pyfluidsynth** — SoundFont-based audio synthesis
- **SoundFont (SF2)** — instrument samples. A GM SoundFont (e.g. the free FluidR3_GM or GeneralUser GS) is bundled/downloaded at build time and committed-by-reference, not stored in the repo.
- **mido / MIDIUtil** — MIDI construction in Python
- **numpy** — sample buffer handling
- The engine lives in `backend/app/services/generation/` and is used by both the Feel Lab (short textures) and the Beat Room (full instrumentals).

Note: a neural model like MusicGen could be added later as an optional "richer texture" enhancement via a self-hosted Space, but the procedural engine is Frank's reliable core.

## Key Architectural Principles

1. **The frontend never processes audio** — all DSP happens server-side. The browser records and plays back only.
2. **Every audio operation is versioned** — nothing is ever destructively overwritten.
3. **The LLM never outputs audio** — it outputs structured JSON parameters that the audio pipeline executes. The LLM interprets; the pipeline creates.
4. **Free tier first** — if a component requires paid access, find the open-source or free-tier equivalent before considering paid options.
5. **No local model inference** — no Ollama, no local Whisper, no local anything that requires meaningful RAM or CPU on the developer machine.

## API Communication

- Frontend to Backend: REST (JSON) over HTTPS
- Audio files: multipart form upload to backend, stored in Supabase Storage, URLs returned
- Long-running jobs (beat generation, mastering): async task queue with polling or websocket status updates
- LLM calls: always made from the backend, never directly from the frontend (keys never exposed to client)

## Environment Variables

All secrets live in environment variables, never in code:
- `GROQ_API_KEY`
- `HUGGINGFACE_API_KEY`
- `REPLICATE_API_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL`
