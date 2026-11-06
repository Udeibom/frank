# Frank — Project and Version System

## What a Project Is

A project in Frank represents one song. It has a name, a state for each of the six layers, a full version history, and a collection of audio files.

One user can have multiple projects. Projects are never deleted — they can be archived.

## Project State Schema (simplified)

```
project
  id
  user_id
  title
  created_at
  updated_at
  status: draft | in_progress | exported

  layers:
    idea:
      lyrics_versions: [{ id, content, created_at, label }]
      active_lyrics_id

    feel:
      fingerprint: { ...musical fingerprint JSON }
      conversation_history: [...]
      texture_samples: [{ id, audio_url, approved: bool }]

    beat:
      stems: [{ id, type, section, audio_url, version_of }]
      arrangement: { sections: [...], stem_assignments: {...} }
      beat_versions: [{ id, render_url, created_at, label }]
      active_beat_version_id

    voice:
      takes: [{ id, audio_url, created_at, label, pitch_data, processed_url }]
      comp: { id, audio_url, segments: [...] }
      active_vocal_id

    mix:
      mix_versions: [{ id, render_url, params, created_at, label }]
      active_mix_id
      mix_params: { stem_levels: {...}, effects: {...} }

    export:
      exports: [{ id, audio_url, format, quality, created_at }]
```

## Version History Rules

1. Every significant action creates a version record — not a full copy of the project, a record of what changed
2. Audio files are never deleted from storage when superseded — only dereferenced
3. The user can label any version: "before I changed the chorus," "original take"
4. Branching: the user can fork from any prior version to explore a different direction, keeping both
5. Auto-save happens after every action that changes state — there is no manual save

## What "Active" Means

Each layer has an "active" pointer. The active version is what plays when the user hits play. Changing the active pointer is instant — no re-render needed if the file already exists.

## Project Dashboard

The user sees all their projects on the home page. Each project shows:
- Title
- Last worked on
- Which layers have content (visual indicator for each of the 6 layers)
- A play button to hear the current mix/latest audio

## Naming

Project titles are auto-suggested from the first line of the lyrics, or from the feel description if no lyrics exist yet. The user can rename at any time.

Takes are auto-named by timestamp. The user can rename them.

Beat versions are auto-named: "Beat v1," "Beat v2," etc. User can rename.

## Data That Must Never Be Lost

- Every lyric version ever written
- Every vocal take ever recorded
- Every beat version ever generated
- The original unprocessed version of every vocal take
- The musical fingerprint at every point in time

If in doubt, keep it. Storage is cheap. Lost creative work is devastating.
