# Frank — Audio Architecture

## Core Mental Model

The frontend is a playback and recording surface. The backend is the studio. All signal processing, pitch manipulation, mixing, effects, and rendering happen on the backend. The frontend streams audio in and out.

## Frontend Audio Responsibilities

- **Recording**: Capture microphone input via MediaRecorder API, encode to WebM/Opus or WAV, upload to backend
- **Playback**: Stream audio files from Supabase Storage URLs via HTML5 Audio or Tone.js Player
- **Real-time monitoring**: During recording, route microphone input through Web Audio API for level metering only (no processing)
- **Waveform display**: Render waveform visualizations from audio data returned by the backend
- **Sync**: Keep beat and vocal playback in sync during recording (the beat plays from a URL, the mic is live)

## Headphone Detection and Handling

Recording with vocal + beat simultaneously requires headphones to avoid the mic picking up the beat.

- On entering the Voice Room, detect audio output device if possible
- If headphones cannot be confirmed, show a clear, friendly warning: "For the best recording, use headphones so the beat doesn't bleed into your mic"
- Do NOT block recording if headphones aren't detected — just warn
- If recording without headphones, the backend should attempt to separate the beat bleed from the vocal using basic source separation

## Backend Audio Pipeline

### File Formats
- **Input (vocals)**: WebM/Opus from browser, or WAV from upload — always converted to WAV for processing
- **Working format**: 44.1kHz 16-bit WAV in memory for all internal processing (synthesis, mixing)
- **Stored/playable renders (beats, section mixes, textures)**: MP3 (192kbps). A full 2.5-minute beat is ~25MB as WAV but ~3-4MB as MP3 — storing WAV blows past Supabase free-tier upload limits and streams slowly. WAV stays in memory only during processing; what lands in storage for playback is MP3.
- **Final export**: MP3 320kbps via FFmpeg

### Pitch Processing (librosa pyin + Rubber Band)
1. Run librosa `pyin` on every vocal take after upload to get a pitch contour
   (fundamental frequency over time, with a voiced/confidence flag).
2. Store the contour as JSON alongside the take: [{time, note, confidence}, ...].
   Confidence maps to a colour: >0.8 green (in tune), 0.5–0.8 yellow, <0.5 red.
3. For correction, compute how far each voiced segment sits from the nearest
   chromatic pitch and apply a per-segment pitch shift via Rubber Band (pylibrb)
   to nudge it toward the target. Strength depends on the chosen mode.
4. Three correction modes (plain language for the user):
   - "Just the obvious mistakes" — only correct notes far off (>50 cents)
   - "Tighten it up" — correct moderately off notes (>20 cents)
   - "Lock it in" — fully snap to the nearest note (the autotuned sound)
5. The original take is ALWAYS preserved. Correction produces a new derived file;
   the user compares and chooses. Nothing is overwritten.

### Harmony (Rubber Band)
A harmony part is generated from the user's own vocal by pitch-shifting it by a
musical interval (a third or a fifth above/below), chosen to fit the song's key
from the fingerprint. No second recording is needed — the harmony is derived
from the take. Stored as its own layer the Mix Room can turn on/off.

### Beat / Instrumental Generation (Frank's procedural engine)
Frank builds instrumentals with its own procedural engine (see tech.md for why — no free hosted MusicGen exists). The flow:
- The musical fingerprint (key, mode, tempo, energy, density, instrumentation hints) drives explicit musical choices.
- A **composer** layer builds MIDI: chord progression from the key/mode, a bassline, a melody/pad line, and drum patterns — per section (intro, verse, chorus, bridge, outro).
- A **renderer** layer plays that MIDI through FluidSynth + a SoundFont to produce real instrument audio per stem.
- Each instrument part (drums, bass, keys/melody, pads/atmosphere) is rendered as its own **stem** so the user can work layer by layer.
- Because the composition is explicit and parameterized, regenerating or adjusting a single section or a single stem is a precise, controllable operation — not a re-roll of a black box. "The bass feels too busy" lowers the bass pattern's note density and re-renders only the bass stem.
- Section boundaries are known by construction (we built them), so no onset-detection guesswork is needed to split sections.

### Effects Chain (pedalboard)
All effects are applied non-destructively. Each effect application creates a new derived file.

Available effects (named in plain language for the user):
- "Add space" → reverb (Convolution or FreeVerb)
- "Bring it closer" → reduce reverb, gentle compression
- "Smooth it out" → gentle compression + saturation
- "Clean up the low end" → high-pass filter at 80Hz
- "Make it sit in the mix" → EQ notch at problem frequencies
- "Radio ready" → mastering chain (multiband compression + limiting + loudness normalization to -14 LUFS)

### Mixing
- Each stem (vocal, beat elements) has a gain level stored in the project state
- The mix is rendered by FFmpeg: overlay all stems with their gain levels applied
- A "mix preview" is a low-quality fast render (64kbps MP3) for listening
- The final export is a full-quality render (WAV → MP3 320kbps)

### Version Control for Audio
Every audio operation that produces a new file:
1. Stores the new file in Supabase Storage
2. Creates a version record in the database with: parent_file_id, operation_type, operation_params, timestamp
3. Never deletes the parent file

This means the user can always return to any prior state.

## Musical Fingerprint

The Feel Lab produces a musical fingerprint — a structured JSON object passed to the Beat Room and used to generate/shape the instrumental. Schema:

```json
{
  "tempo_bpm": 90,
  "tempo_feel": "steady",
  "key": "C minor",
  "mode": "minor",
  "energy_level": 0.6,
  "density": 0.4,
  "brightness": 0.3,
  "warmth": 0.7,
  "genre_proximity": ["soul", "r&b", "lo-fi"],
  "instrumentation_hints": ["piano", "soft drums", "bass"],
  "reference_texture_id": "uuid-of-the-texture-the-user-approved",
  "hum_reference_file": "optional-uuid-of-user-hum-recording"
}
```

This object is stored with the project and can be updated from the Feel Lab at any time.

## Async Processing

Beat generation and full mix renders take time (10–60 seconds). These are async jobs:
1. Frontend submits a job, gets a job_id back immediately
2. Frontend polls `/jobs/{job_id}/status` every 2 seconds
3. When complete, the response includes the audio file URL
4. The UI shows a non-blocking progress state while waiting — the user can work in other layers

Never make the user stare at a spinner with nothing to do.
