# Feeling room (the representative room): what was built, and the evidence

Status: **built and tested in a browser; waiting for your approval before the other five rooms.**
Direction and system: `AUDIT.md` (sections 3–5) and `.kiro/steering/design-and-ui.md`.

## Before and after

| | Before | After |
|---|---|---|
| Empty | `before/05-feel-empty.png` | `after/02-feeling-empty.png` |
| Hearing a direction | `before/07-feel-texture.png` | `after/11-feeling-final-1440.png` |
| Two directions, switching | not possible (two played at once, `before/16`) | `after/07-feeling-two-directions.png` |
| A direction fails | chat sentence only (`before/14`, Beat room) | `after/09-feeling-failure-in-place.png` |
| Kept direction, then another room | sound stops, nothing shown | `after/08-music-room-sound-continues.png` |
| 1024 px | `before/17-beat-1024.png` (squashed, truncated) | `after/10-feeling-1024.png` |

**Font caveat:** `after/03` to `after/07` were taken before I found that the fonts weren't loading (see "Found and fixed during testing"). They show the layout correctly but in fallback faces. `after/02`, `08`–`11` show the real Inter and Newsreader.

## What changed, and which audit finding it answers

| Change | Finding |
|---|---|
| **Song Strip** on every room: song name in the written face, what is playing, sections and four lanes, the one transport with minutes:seconds | D-1, D-4, C-2 |
| **Rail** with plain names (Words, Feeling, Music, Voice, Blend, Finish), no status circles; account and extras in one "You" menu | T-1, D-3, D-8 |
| The shell **never unmounts**; loading shows inside the stage, not a black page | P-7 |
| **One AudioEngine**: one sound at a time, keeps playing across rooms, switches in time | X-1, D-4 |
| Rooms not yet redesigned still create their own audio; a guard makes those obey one-sound-at-a-time too | X-1 |
| **Listening bench**: every direction is a card with its sound shape, play, "This is it / Not this"; kept direction marked and shown in the strip's feeling lane | S-6, C-1 |
| **Frank note on the stage** with answers as buttons; the stage never says "talk on the right" | S-6 |
| **Hum / Tap** are stage controls, not links over the chat input | T-4 |
| **In place loading** (ghost card, progress sweep) and **in place failure** with Try again | S-1, S-2, X-6 |
| **Frank panel** without bubbles; "What Frank knows" at the top; changes shown as a change line with "Hear it" | G-2, D-5 |
| Tokens: warm graphite, four material colours, amber for "sounding / the one action" only; six-step type scale; one focus ring | H-1–H-5, G-1–G-4 |
| Fonts bundled and loaded locally (Inter, Newsreader) | H-3 |
| Skip link, landmarks, distinct accessible names on every play control, Space / arrows / 1–6 shortcuts | X-2, X-4 |
| First-run drawer no longer opens over the room by itself; "Start with whatever you have" is in the strip and the You menu | T-5 |
| Backend: two read-only routes (list a song's directions, measure one direction's shape) and the texture job now returns the shape | needed so directions survive a reload and show their sound |

Not changed: how Frank talks (same prompts, same actions), the fingerprint and how it is saved, hum and rhythm intake logic, the jobs and polling flow, versioning.

## Journeys tested in the browser (1440×900 unless stated)

| # | Journey | Result |
|---|---|---|
| 1 | New song → Feeling → type a feeling on the stage → "Play me a first sound" | Ghost card with progress appears; the direction arrives already playing; the strip shows "Playing: Direction 1"; the change line appears in the panel. **Pass** |
| 2 | Reload the room | Direction 1 comes back from the server with its shape measured. **Pass** |
| 3 | Ask for another direction while Direction 1 plays | Direction 2 arrives and takes over; only one plays (`d1Playing false, d2Playing true`). **Pass** |
| 4 | Play Direction 1 for 5 s, then press Play on Direction 2 | Direction 2 starts at the same moment (0:10 → 0:11), and Direction 1 stops. **Pass** |
| 5 | "This is it" on Direction 2 | Card says "Kept for your song"; strip feeling lane goes solid; the Frank note offers "Build the music / Keep exploring". **Pass** |
| 6 | With it playing, go to Music (old room) | Sound keeps going (0:01 → 0:05 across the change); the strip still shows it; its transport pauses it. **Pass** |
| 7 | In the Music room, start an old-style player while the engine plays | The engine stops; pressing the strip's play stops the old player. One sound at a time. **Pass** |
| 8 | Make a direction fail (texture request forced to 500) | A red-edged card "That one didn't come out" with "Try again" appears in place; other directions untouched. **Pass** |
| 9 | Keyboard only | Tab order: skip link → stage → Frank note answers → card shape → Play. Enter plays; Space pauses and resumes from the stage; → moves 5 s; "4" goes to the Voice room while the sound continues. **Pass** (after a fix, see below) |
| 10 | 1024×768 | Page is 1024 px wide (no sideways scroll), no clipped or truncated controls, Frank panel starts as a 56 px tab, stage 948 px. **Pass** |
| 10b | A direction plays through, goes round once more, then stops (feel-lab requirement 2.2), logged once a second | `0:00…0:11, 0:00…0:11`, then stopped. **Pass** (after a fix, see below) |
| 11 | Contrast and type, script over every visible text node | 0 failures below 4.5:1 (3:1 for 20 px and larger). Sizes in use: 12, 13, 15, 17, 20, 24 (16 is only the hidden skip link). **Pass** |
| 12 | `tsc --noEmit`, `next build` (includes lint), backend tests for jobs, signing, fingerprint and the creative director | All pass. The full backend suite took longer than 14 minutes here and was stopped, so it has not been run end to end. |

## Found and fixed during testing

- **The fonts weren't loading.** `next/font/google` had silently fallen back (the computed font was `__Inter_Fallback`). The faces are now bundled in `app/fonts` (SIL Open Font License, with a licence note) and loaded with `next/font/local`. Verified: both faces have status `loaded`.
- **Directions looped forever**, which went against the Feel Lab spec (play through, round once more, stop). The spec check caught it after I deleted the old player. The engine now has a "plays twice" option, and the cards say "Plays twice". The old `TexturePlayer.tsx` (unused) is deleted, and the specs that named it or the old sidebar (foundation, feel-lab, beat-room, voice-room, auth) now point to the new files. Foundation requirement 11 is marked as amended.
- **Space crashed the shortcut handler** when the event target wasn't an element. Fixed and re-tested.
- **The bench briefly showed the first-run question before saved directions loaded.** It now waits.
- **Two parts of the shell were loading the directions list again on every change.** They now share one request.
- **Frank said the same thing twice** when a direction arrived (his reply, then "Here's a direction…"). Now it is his reply plus the change line.
- **The hum control stole focus from the question field** on page load. It now only moves focus after something it owns changes.

## Known gaps (not hidden)

- **No "based on" link between directions.** The data doesn't record which direction another came from, so I couldn't show lineage (the Endlesss idea). It is written into `feel-lab.md` as not yet done.
- **The "Frank has something waiting" dot on the rail** is planned, not built (marked as such in `design-and-ui.md`).
- **The waveform cache lives in server memory.** A new column wasn't possible: the Database Steward found no way to run schema changes from here (no DB connection string or management token). After a restart, shapes are measured again on first view. To make it permanent, run one `ALTER TABLE` in the Supabase dashboard and I'll switch it over.
- **Hum and Tap were not tested with a real microphone** (the test browser has none). Their logic is unchanged; only their look moved.
- **The other five rooms** sit in the new shell with their old stages. They inherit the new tokens, panel and one-sound rule, but they aren't redesigned yet. Some still use old patterns (Music's icon-in-a-disc empty state is visible in `after/08`).
- **Correction (Nov 20):** I wrote here that pages "jumping back to the song list" were slow dev compiles. That was wrong. It was the login check redirecting whenever Supabase failed to answer. It is found and fixed in `ROOMS.md` ("Found and fixed while testing").
- A test account `frank-design-test@example.com` holds the two test songs used here. I'll delete it when you're done reviewing, or now if you prefer.
- `frontend/.gitignore` has an uncommitted `.env*` line that I didn't add (it predates this work). I left it alone.

## What I need from you

Look at `after/11-feeling-final-1440.png` and `after/02-feeling-empty.png` (or open the room yourself). Tell me what to change. Once you approve, I'll do the same for Music next, then Words, Voice, Blend and Finish, each with the same before/after and journey record.
