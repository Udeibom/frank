# Third-party models, data, services and code

Frank's own source code is MIT (see `LICENSE`). Frank is stitched together from the parts below, and each part keeps its own licence. Some of them allow only non-commercial use, so **Frank as a whole is a non-commercial project**. Inside the app, the Finish room credits every part that shaped a song (`backend/app/services/provenance.py`).

## Licence notes

- **Licence decision: MIT for Frank's own code**, including the two Spaces' code in `spaces/`. MIT is an open-source licence and is compatible with the GPL. The backend imports `pedalboard` (GPL-3.0) and `pylibrb` / Rubber Band (GPL-2.0+), runs Dragonfly Reverb (GPL-3.0) as a plugin, and the frank-ears Space runs Matchering (GPL-3.0). These run as services and are not redistributed by this repo, so their licences do not change Frank's. Anyone who distributes a built image that bundles them must follow the GPL for that bundle; all source is public here either way.
- **Non-commercial parts.** These allow non-commercial use only: Chordonomicon (CC BY-NC 4.0), the Essentia Discogs-EffNet and MTG-Jamendo heads (CC BY-NC-SA 4.0), and the Tiger DiffSinger voicebank (CC BY-NC-ND 4.0 + Commons Clause). The voicebank is downloaded at runtime from its official release and is never redistributed in this repo.
- **Tables derived from datasets.** These files hold counts and statistics, never the songs themselves, and they keep their sources' terms:
  - `backend/app/services/generation/styles/grooves.json`: Groove MIDI, CC BY 4.0.
  - `chord_tables.json`: Chordonomicon, CC BY-NC 4.0.
  - `arrangement_stats.json`: Lakh MIDI, CC BY 4.0.
  - `feeling_words.json`: Song Describer, CC BY-SA 4.0.
- **No copyrighted music is stored.** A reference song chosen by the person is either a Jamendo track (Creative Commons) or an upload they confirmed they have rights to. Uploads are analysed in memory and never stored. Deezer and iTunes previews were rejected, because their terms forbid this kind of use.
- **Music in the demo video.** The video uses only music Frank made with the founder (the founder's voice and words, Frank's engine, and the CC0 or Creative Commons parts listed here, credited on screen when the licence asks). No commercial recordings and no reference songs appear in it.
- **Gemini region rule.** Google's Gemini API terms allow only paid services for people in the EEA, Switzerland and the UK. Frank never calls Gemini for those regions, and it treats an unknown region the same way (`backend/app/services/region.py`).

## Models

| Part | What Frank uses it for | Licence | Where it runs |
|---|---|---|---|
| LAION CLAP (`laion/larger_clap_music_and_speech`) | Matching sounds to words; sound memory | Apache-2.0 | frank-ears Space |
| Essentia Discogs-EffNet + MTG-Jamendo mood/genre heads (MTG-UPF) | Style check | CC BY-NC-SA 4.0 | frank-ears Space |
| Meta Audiobox Aesthetics | "Did the change make it sound better made" | CC BY 4.0 | frank-ears Space |
| madmom chord recogniser (CPJKU) | Chords of a reference song | BSD-3 (code); models CC BY-NC-SA 4.0 | frank-ears Space |
| PESTO pitch | Pitch of a reference vocal | LGPL-3.0 | frank-ears Space |
| All-In-One music structure (`all-in-one-infer`) | Sections of a reference song | MIT | frank-ears Space |
| BS-RoFormer via `audio-separator` | Splitting a reference into parts | MIT | frank-ears Space |
| Matchering 2 | Matched master | GPL-3.0 | frank-ears Space |
| DeepFilterNet | "Quiet the background" on a take | MIT / Apache-2.0 | frank-ears Space |
| GoEmotions (`SamLowe/roberta-base-go_emotions`) | Feelings in the lyrics | MIT | frank-ears Space |
| Anticipatory Music Transformer (`stanford-crfm/music-medium-800k`) | A new part written around the person's tune | Apache-2.0 | frank-hands Space |
| Kokoro-82M | Reading Frank's notes aloud | Apache-2.0 | frank-hands Space |
| DDSP (Google Magenta) | The person's hum played as an instrument | Apache-2.0 | frank-hands Space |
| DiffSinger (OpenVPI) + Tiger voicebank | Guide voice singing the words | Apache-2.0 (engine); CC BY-NC-ND 4.0 + Commons Clause (voicebank) | frank-hands Space |
| Stable Audio Small / Open (Stability AI) | Atmosphere made from words | Stability AI Community Licence (gated) | frank-hands Space |
| Basic Pitch (Spotify), ONNX | Second hum tracker, used for comparison only | Apache-2.0 | Backend |
| Groq `openai/gpt-oss-120b` | Conversation | Apache-2.0 weights; Groq API terms | Groq API |
| Whisper `whisper-large-v3-turbo` | Voice memos; word timings | MIT weights; Groq API terms | Groq API |
| Google Gemini | Listening to the mix and vocals; looking at a picture | Gemini API terms (region rule above) | Gemini API |

## Datasets (mined offline into small tables)

| Dataset | Licence | Mined by |
|---|---|---|
| Groove MIDI Dataset (Google Magenta) | CC BY 4.0 | `backend/scripts/mine_grooves.py` |
| Chordonomicon | CC BY-NC 4.0 | `backend/scripts/mine_chords.py` |
| Lakh MIDI Dataset, clean subset (Colin Raffel) | CC BY 4.0 | `data/mining/lakh_arrangement/mine.py` (Kaggle) |
| Song Describer (Manco et al., 2023), recordings from MTG-Jamendo | Captions CC BY-SA 4.0; recordings Creative Commons | `data/mining/song_describer/mine.py` (Kaggle) |
| CMU Pronouncing Dictionary (`cmudict`) | BSD-2 | `backend/scripts/build_words_db.py` |

## Sounds and instruments

| Part | Licence |
|---|---|
| MuseScore General SoundFont | MIT |
| Versilian Studios VSCO-2 CE (upright piano, violin section) | CC0 |
| Freesound clips (atmosphere) | Each clip's own Creative Commons licence; Frank credits the author and licence per clip |

## Services (free tiers)

| Service | Use | Terms |
|---|---|---|
| Supabase | Database, auth, storage, realtime | Supabase terms |
| Render | Backend | Render terms |
| Vercel | Frontend | Vercel terms |
| Hugging Face ZeroGPU Spaces | frank-ears, frank-hands | Hugging Face terms |
| Open-Meteo | Weather for "this moment" | CC BY 4.0 (attribution shown) |
| MusicBrainz / ListenBrainz | Facts about a reference song | Data CC0; API terms |
| Jamendo API | Free reference music | Non-commercial API key; tracks under Creative Commons |
| Freesound API | Recorded atmosphere | Free API key; per-clip CC licences |
| Datamuse | Near rhymes | Free API |
| Exa, Firecrawl | Researching a reference song | Free tiers |

## Code libraries

**Backend**
- FastAPI: MIT
- librosa: ISC
- soundfile: BSD-3
- numpy: BSD-3
- FluidSynth: LGPL-2.1
- pyfluidsynth: LGPL
- sfizz: BSD-2
- FFmpeg: LGPL/GPL
- pedalboard: GPL-3.0
- pylibrb / Rubber Band: GPL-2.0+
- Dragonfly Reverb: GPL-3.0
- LSP Plugins: LGPL-3.0
- mido: MIT
- pretty_midi: MIT
- mir_eval: MIT
- onnxruntime: MIT
- gradio_client: Apache-2.0

**Frontend**
- Next.js: MIT
- React: MIT
- Tone.js: MIT
- Zustand: MIT
- shadcn/ui: MIT
- Tailwind CSS: MIT
- Tiptap: MIT
- WaveSurfer.js: BSD-3
- MediaPipe Tasks: Apache-2.0
- fast-check: MIT
- vitest: MIT
