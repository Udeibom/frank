# Original single-file specs (archived)

These are Frank's original specs as they were first written: one Markdown file per
feature, each with Overview / Requirements / Design Notes / Implementation Tasks and a
"Post-Review Follow-Ups" section. The project was built against these.

They are kept here, unedited, as an honest record of how the work actually happened:
we started vibe-style with single-file specs, built the six rooms end to end, then — after
realizing the specs weren't in Kiro's native structured format — converted each one into
the proper `<feature>/{requirements.md, design.md, tasks.md}` layout under `.kiro/specs/`.

The native specs are the source of truth going forward. Two things changed in the
conversion, both to match what was actually built rather than the original plan:

- **Generation**: the originals referenced MusicGen; the real engine is Frank's own
  procedural engine (FluidSynth + SoundFont), because no free hosted MusicGen exists.
- **Pitch**: the originals referenced Basic Pitch; the real implementation uses
  librosa `pyin` (Basic Pitch pulls in TensorFlow, too heavy for the free tier).

Mapping:

| Original | Native folder |
|---|---|
| 01-foundation.md | `foundation/` |
| 02-idea-room.md  | `idea-room/` |
| 03-feel-lab.md   | `feel-lab/` |
| 04-beat-room.md  | `beat-room/` |
| 05-voice-room.md | `voice-room/` |
| 06-mix-room.md   | `mix-room/` |
| 07-export-room.md| `export-room/` |
| 08-auth.md       | `auth/` (to be built through the native flow) |
