# The other five rooms: what was built, and the evidence

Status: **all five rooms built and tested in a production build.** Gaps first:

- **Nothing that needs a recorded voice has been seen in a browser**: recording a take, the take menu, best-of, second voice, a real blend, finishing and downloading. The test browser never answers the microphone prompt. These screens are built and typecheck, and their API calls are unchanged, but they need one real session with a microphone before they can be called done.
- The two Finish/Blend screens were seen only in their "something is missing" state.
- The full backend test suite has not been run end to end here (it takes over 14 minutes); the tests for the code I changed pass.
Feeling (the approved representative room) is documented in `FEELING-ROOM.md`.

## Built (code complete, typechecks)

| Room | Stage | Key changes |
|---|---|---|
| Music (`beat`) | Arrangement grid: sections across, parts down | Cells: busier / simpler / another idea / leave it out / add it here (typed beat operations). Sections: play from here / fuller / calmer / fill / rename. Versions list "How the music got here" with what changed in each. In-place building and failure. |
| Words (`idea`) | A page in the written face, drafts and sections in the margin | Plain section headings (no brackets needed); "read my words" and "hum or speak" on the stage; Frank offers to name the song from its first line; the page now opens on the draft in use, not just the newest (bug fix). |
| Voice (`voice`) | Your words beside the recorder; takes below | One "Make it sound…" menu per take instead of seven buttons; best-of version numbered by take; recording pauses everything else first (so nothing plays into the mic). |
| Blend (`mix`) | One large listen control with "compare with before"; lanes for each part | On/off shows the state, not the action (audit X-9); blocked state links to the missing room instead of a dead play button (X-7); in-place failure with "Try again". |
| Finish (`export`) | The song's name large in the written face, one step at a time | Does it match → finish it → download, one amber action per step; before/after switch keeps the moment; shape of the song once finished. |

Everything that plays now goes through the one AudioEngine; no component creates its own audio, so the interim
one-sound guard was removed.

## Browser journeys (production build, `next build` + `next start`, 1440×900)

### Music

| # | Journey | Result |
|---|---|---|
| M1 | Feeling kept, no music yet → "Build the music" (the one amber action) | The grid shows the six sections as dashed ghosts, then a sweep while building; the music arrives already playing; strip shows sections and a solid music lane. **Pass** (`after/20`, `21`, `22b`) |
| M2 | Grid at 1440 px with 8 sections | All section names readable, nothing truncated (after widening short sections to at least 80 px). **Pass** (`after/22c`) |
| M3 | Section menu → "Play from here" on the first chorus | Starts at 0:33 of 2:20, that column marked as playing; on the second chorus starts at 1:16. **Pass** (`after/25`) |
| M4 | A part cell → "Add strings here" (first verse) | Note says "Adding strings to the first verse…", only that cell sweeps; Beat v2 arrives playing; versions read "Beat v2: I brought in the strings in the first verse · In the song" over "Beat v1: Built from the feeling · Use this"; cell now says "plays". **Pass** (`after/26-music-changing-in-place`, `27`) |
| M5 | A change that changes nothing (drums simpler where they already are) | Frank's plain reason in the note with the problem rule, "The music you had is untouched", and Try again; no new version. **Pass** |

### Words

| # | Journey | Result |
|---|---|---|
| W1 | Empty page | The page in the written face with the hint, "read my words" and "hum or speak" on the stage, sections and drafts in the margin. **Pass** (`after/30`) |
| W2 | Write a verse and a chorus with plain headings (no brackets) | "Saved as a draft" after the pause; margin lists Verse, Chorus; the strip's words lane lights only the verses and choruses (intro, bridge and outro stay "nothing yet"). **Pass** (`after/31`) |
| W3 | Frank offers a name from the first line | "Want to call the song 'Streetlights hum a lullaby for me'?" with "Yes, call it that" (amber) / "Not now"; accepting renames the song in the strip and adds a change line. **Pass** (`after/32`) |

### Voice

| # | Journey | Result |
|---|---|---|
| V1 | Open with words and music, no takes | Your words in front of you beside the recorder; start-from list built from the music's sections (Verse 1, Chorus 1…); the once-only timing check offered; headphones note as a status message. **Pass** (`after/40b`) |
| V2 | Press Record | **Not testable here**: the test browser has a microphone device but its permission prompt is never answered, so the request stays waiting. The room said nothing at all while waiting; it now says "Waiting for your microphone. If your browser asks, choose Allow." Recording a take, the take card's menu, the best-of version and the second voice have **not** been seen in a browser. |

### Blend

| # | Journey | Result |
|---|---|---|
| B1 | Open with music but no voice | Blocked state: "To blend the song, it needs your voice first." with one amber "Record your voice"; no disabled play button anywhere (0 found). Frank's panel says the same thing with the room's plain name. **Pass** (`after/50b`) |
| B2 | Lanes while blocked | Showed softer/louder/on-off controls for every part, which would only fail with no voice to blend. **Fixed**: the music is one read-only lane until there's something to blend. |
| B3 | A real blend: listen, compare with before, change a lane, something feels off | **Not tested**: it needs a recorded voice, which this browser can't make (see V2). |

### Finish

| # | Journey | Result |
|---|---|---|
| F1 | Open with no blend | Blocked state with one amber "Go to Blend", and the dashed shape of where the finished song will be. **Pass** (`after/60b`) |
| F2 | Does it match → finish → download; before/after; separate parts | **Not tested**: needs a blend, which needs a voice (see V2). |

### Every room: the same check at 1024×768

The script is `docs/design-audit/room-check.js`. It checks every visible piece of text against the contrast floor, lists the font sizes in use, and checks for sideways scrolling, controls clipped or off the screen, solid amber actions, play controls sharing a name, and the skip link.

| Room | Text below the floor | Sizes in use | Sideways scroll | Clipped / off screen | Amber actions | Same-named play controls |
|---|---|---|---|---|---|---|
| Words | 0 | 12 13 15 17 20 24 | no | 0 / 0 | 0 (only when Frank offers a name) | 0 |
| Feeling | 0 | 12 13 15 20 24 | no | 0 / 0 | 0 | 0 |
| Music | 0 | 12 13 15 24 | no | 0 / 0 | 0 | 1, **fixed** (see below) |
| Voice | 0 | 12 13 15 20 24 | no | 0 / 0 | 1 (Record) | 0 |
| Blend | 0 | 12 13 15 24 | no | 0 / 0 | 1 ("Record your voice") | 0 |
| Finish | 0 | 12 13 15 24 | no | 0 / 0 | 1 ("Go to Blend") | 0 |

All six have the skip link. All sizes are on the six-step scale.

## Found and fixed while testing

- **The studio jumped to the song list in the middle of a session.** Every so often a background page prefetch hit the login check at a moment Supabase didn't answer. The check treated "couldn't ask" as "signed out", redirected to `/login`, which (seeing the real session) redirected to `/songs`, and Next.js followed that as a full page change. Seen in the request log as `beat?_rsc → 307 → /login → 307 → /songs`, about every 10 seconds. `lib/supabase/middleware.ts` now lets the page through when the auth call failed on the network. The backend still checks the token on every API call, so a session that has really ended still goes to log in. After the fix: no redirects in 70 seconds of watching. This was also the unexplained "jump back to the song list" noted in `FEELING-ROOM.md`; my earlier explanation there (slow dev compiles) was wrong.
- **Short sections cut their names** ("Bri…", "Ou…"): columns now have an 80 px minimum, and the rename pencil no longer takes the name's space.
- **Versions list squeezed the grid** at 1440 px: it moved below the arrangement.
- **The strip claimed an empty song while loading.** For a moment on every full page load it said "Untitled song · Nothing in the song yet" and offered "Start with whatever you have", for a song with music and a kept feeling. It now says "Opening your song…" until this song's record has arrived; Frank's panel says "Reading your song…".
- **Two amber actions in Voice**: the "Sing with the beat" option was solid amber next to the amber Record button. Options now show as selected (outlined in the voice colour, `aria-pressed`), leaving Record as the one action.
- **Drafts were listed by their heading** ("Verse"); they're now listed by their first line of words.
- **Two placeholders were clipped** in Frank's panel (Words, Voice); shortened.
- **Blend and Finish notes had a coral rule** (the voice colour), which read as a warning beside the problem colour. They now use the neutral rule, matching their neutral marker in the rail.
- **"Mix" in Frank's words** in Blend's greeting: now "blend the song".
- **Two controls named "Play Beat v2"** in Music: the big one and the version-list row, which play the same thing. List rows are now "Play Beat v2, in the version history" (and "…, in the list of blends" in Blend). This is in the source and typechecks; it was not rebuilt and re-checked after the change.
- **My own build step** (output piped into `head`) killed `next build` before it finished. The server then failed to start with a missing manifest. Not an app bug; rebuilt properly.
