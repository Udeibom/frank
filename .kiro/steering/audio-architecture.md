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
- **Working format**: 44.1kHz, 16-bit or 32-bit float WAV for all internal processing
- **Output (stems)**: WAV
- **Final export**: MP3 320kbps via FFmpeg

### Pitch Processing (Basic Pitch + Rubber Band)
1. Run Basic Pitch on every vocal take immediately after upload
2. Store pitch contour data (note, confidence, timestamp) alongside the audio file
3. For pitch correction: Rubber Band Library (pyrubberband) applies pitch shifting per-segment
4. Three correction modes (presented to user in plain language):
   - "Just the obvious mistakes" — correct notes more than 50 cents from the nearest chromatic pitch
   - "Tighten it up" — correct notes more than 20 cents from nearest chromatic pitch
   - "Lock it in" — fully quantize to nearest chromatic pitch (autotune effect)
5. Original is always preserved. Correction is a new derived file.

### Beat / Instrumental Generation (MusicGen)
- MusicGen is called with a structured prompt derived from the musical fingerprint
- The prompt is built by the LLM translator from the user's emotional description
- MusicGen returns a full audio file — this is the starting point, not the finished beat
- The beat is broken into conceptual sections (intro, verse, chorus, bridge, outro) by the backend using onset/energy detection
- Individual section files are stored as stems so the user can work section by section
- Regeneration of a single section is possible without regenerating the whole beat

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
