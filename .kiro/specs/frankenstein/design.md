# Frankenstein - Design (spec 14)

## Where each organ runs

| Body | Runtime | Holds |
|---|---|---|
| Render web service (512 MB, CPU) | existing Docker image | orchestration, the engine, Listener, Basic Pitch (ONNX), word timings (Groq), Gemini listening and looking, CMU dictionary, Datamuse, MusicBrainz, ListenBrainz, Jamendo, Freesound, Exa, Firecrawl, Open-Meteo, MIDI export, groove and chord tables, sfizz rendering, studio plugins, pgvector store |
| Space `frank-ears` (Gradio, ZeroGPU hardware, CPU by default) | `spaces/frank-ears/` in this repo, pushed to HF | CLAP, Discogs-EffNet + mood heads (ONNX), allin1, Chordino, BS-RoFormer, Audiobox Aesthetics, PESTO, GoEmotions, Matchering, DeepFilterNet |
| Space `frank-hands` (Gradio, ZeroGPU) | `spaces/frank-hands/` | Anticipatory Music Transformer, DDSP timbre, DiffSinger guide, Kokoro, Stable Audio 3 Small, Diff-MST, ACE-Step (blind test only) |
| Kaggle notebooks (offline) | `data/mining/*.py`, run with the Kaggle CLI | Groove MIDI templates, Chordonomicon tables, Lakh/Slakh arrangement stats, Song Describer calibration, MTG-Jamendo mood check |
| Browser | Next.js | WaveSurfer, Tiptap, React Flow, MediaPipe hands, Realtime subscription. Plays and records only. |

Free accounts can host two ZeroGPU Spaces, so all models go in these two. Each Space function runs on CPU unless
it is marked `@spaces.GPU`; GPU is used only where CPU is too slow (Stable Audio, ACE-Step, Diff-MST, BS-RoFormer
on long files). ZeroGPU quota is per caller, so every GPU function has a CPU path or a plain "not right now".

## The remote organ client

`backend/app/services/remote/spaces.py`:
- `call(space, api_name, *args, timeout) -> Any` through `gradio_client` with the HF token, one shared client
  per Space, a wake-up wait (Spaces sleep), and a `RemoteUnavailable` error carrying a plain reason.
- `audio_arg(bytes, ext)` writes a temp file for upload; results come back as files or JSON.
- Calls run inside the existing heavy gate only when they also do local work; a pure remote call does not hold
  the gate (it uses no local memory).
- `available(space) -> bool` cached for 60 s for the UI ("Frank's ears are waking up").

## Data (migration 010, additive)

- `create extension if not exists vector`.
- `sound_embeddings(id, user_id, project_id, kind: texture|part|beat|mix|reference|taste, ref_id, model,
  embedding vector(512), meta jsonb, created_at)` with an ivfflat index; RLS by owner.
- `references(id, project_id, source: upload|jamendo|named, title, artist, license, attribution, analysis jsonb,
  created_at)`. Audio is never stored for uploads; Jamendo tracks keep only their id and licence.
- `provenance(id, project_id, layer, version_id, organ, plain, attribution, created_at)` for the credits page.
- `vocal_takes.words jsonb` (word timings).
- `async_jobs` added to the `supabase_realtime` publication, with an owner select policy.

## How organs report to the brief

- `services/song/brief.py` gains a "what Frank heard" block: reference fingerprint, style labels, aesthetic
  score trend, lyric emotion arc, photo feeling words. Budget stays 6000 characters.
- `services/provenance.py`: `note(project_id, layer, version_id, organ, plain, attribution=None)`. Every job that
  used an organ calls it; `ChangeLine` shows the `plain` text; Finish shows the list.
- Plain-language guard covers all new text. New jargon words (stem, LUFS, MIDI) stay banned in UI text; the
  MIDI download is called "the notes".

## Per organ

- **CLAP** (`ears.embed_audio`, `ears.embed_text`): textures and parts are embedded after render; Feeling ranks
  directions by cosine to the user's words; taste stores liked embeddings; "more like this" queries pgvector.
- **EffNet labels** (`ears.labels`): top styles and moods; Listener rule `rule_style_drift` compares with
  `genre_proximity` in the fingerprint.
- **Gemini listening** (`services/llm/gemini_audio.py: listen(audio_bytes, numbers, concern)`): native
  `generateContent` with inline audio; returns up to three notes; each note is checked against Listener
  findings with matching tags before it becomes an action; unconfirmed notes are said as "I think", not acted on.
- **Gemini looking** (`gemini_audio.look(image_bytes)`): mood words plus colour hints; `services/intake/photo.py`
  also measures colours with Pillow (warmth from hue, brightness from value, energy from saturation) so the
  mapping is visible and testable.
- **Audiobox** (`ears.aesthetics`): refine previews are scored; the proposal says whether the score rose.
- **allin1 + Chordino** (`ears.structure`, `ears.chords`): reference analysis and voice-first sections.
- **Basic Pitch** (`intake/basic_pitch.py`): ONNX runtime on Render, returns the same `RawNote` list as
  `segment_notes`; `extract_melody(..., tracker="basic_pitch"|"pyin")`; `scripts/pitch_compare.py` compares both on
  fixed synthetic hums. PESTO through ears for the Voice contour comparison.
- **Groove templates** (`generation/grooves.json`, `generation/grooves.py`): per style, per tier, 16-step offsets
  (fraction of a step) and velocities mined from GMD; `compose_drums` applies them when the style's
  `groove` key is set; ops `looser`, `tighter` move between templates.
- **Chord tables** (`generation/chord_tables.json`): per genre and section, transition weights between scale
  degrees; `theory.build_progression` multiplies its own choices by the weights.
- **Arrangement stats** (`generation/arrangement_stats.json`): per style, probability each part plays per
  section; `layers_for_section` uses them as priors.
- **AMT** (`hands.accompany(notes, bars, bpm)`): returns notes; Frank maps them into a `Part` named
  `accompaniment`, rendered by the engine, editable by ops.
- **sfizz** (`generation/sfz_renderer.py`): `sfizz_render` subprocess for `keys` (Salamander-free CC0 piano from
  VCSL), `strings` (VSCO-2 CE); FluidSynth for the rest; failure falls back to FluidSynth.
- **Studio plugins** (`audio/plugins.py`): Dragonfly Room/Plate and LSP compressor as VST3 loaded by pedalboard,
  used by "Add space" and the master; missing plugin falls back to the built-in pedalboard effects.
- **Atmosphere** (`services/sounds/freesound.py`, `hands.ambience`): search CC0/CC BY sounds by the brief's
  words, or generate; added as layer `atmosphere`.
- **DDSP** (`hands.timbre(audio, instrument)`): derived take of kind `instrument`, usable as a part.
- **DiffSinger** (`hands.sing(lyrics, notes)`): guide vocal; replaces the GM "voice oohs" guide when available.
- **DeepFilterNet** (`ears.denoise`): derived take of kind `quiet`.
- **Word timings** (`llm/whisper.py: transcribe_words`): `verbose_json`, word granularity; stored on the take.
- **Kokoro** (`hands.speak(text)`): mp3 of Frank's note; frontend toggle "Frank reads notes aloud".
- **CMU dictionary** (`services/words/sound.py`): syllables, stress, rhyme part; Datamuse in
  `services/words/datamuse.py`; endpoint `POST /lyrics/analyse`.
- **GoEmotions** (`ears.emotions(lines)`): per-section emotion; offered as "the song's shape".
- **References** (`services/reference/`): `from_upload`, `from_jamendo`, `describe` (BS-RoFormer parts, then the
  ears), `compare(reference, song)`; `metadata.py` (MusicBrainz, ListenBrainz); `research.py` (Exa, Firecrawl).
- **Matchering** (`ears.match_master(song, reference)`): second master in Finish.
- **Diff-MST** (`hands.mix_like(parts, reference)`): predicted gains and effect amounts mapped onto
  `mix_params`.
- **Open-Meteo** (`services/intake/moment.py`): time of day and weather to feeling words.
- **Realtime** (frontend `lib/api/realtime.ts`): subscribe to the job row; poll as fallback.
- **WaveSurfer, Tiptap, React Flow, MediaPipe**: frontend components named in tasks.
- **Region gate** (`services/region.py`): the frontend sends `X-Frank-Region` from a Vercel edge route that reads
  `x-vercel-ip-country`; the backend skips Gemini for EEA, CH and GB.

## Rejected here (with reasons, so nobody re-adds them)

Deezer and iTunes previews (terms forbid AI use and copies), Music Flamingo, MUSDB18 and DEAM (research-only
licences), Magenta RealTime 2 (needs streaming hardware Frank does not have for free), YuE, DiffRhythm and other
full-song generators (product rule), Modal (card on file), Web MIDI input (serves instrument owners).

## Testing

Property tests (Hypothesis) for every pure mapping: groove application keeps notes inside the bar and velocities
in range; chord weighting never produces an out-of-key chord; syllable counts are positive and stable; colour to
fingerprint stays in 0..1; provenance lines pass the plain-language guard; region gate blocks exactly EEA, CH, GB;
remote fallback never raises to the route. Frontend fast-check for the version tree layout and realtime/poll
merge. Live checks run against the deployed Render service and Spaces, not localhost.
