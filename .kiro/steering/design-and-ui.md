# Frank — Design and UI

This file governs the whole interface. It replaces the earlier "dark theme, amber accent, studio metaphor" brief. The reasoning and evidence behind it are in `docs/design-audit/AUDIT.md`; read that before changing any rule here.

## The one idea

Frank's users own **words, a voice and a feeling**, and no equipment. The interface is built around *their* material. A persistent **Song Strip** shows the song as it exists right now. **Rooms** are different working views of that one song. **Frank** is a margin of plain notes and visible, reversible changes, not a chatbot.

The user must always be able to see: what the song is, what has happened to it, what they can do next, and how a decision changes the result.

## The conceptual model (what the interface shows, not the features behind it)

```
A SONG
 ├─ four MATERIALS     words · feeling · music · voice
 ├─ SECTIONS           (intro, verse, chorus ...) defined once, shared by every material
 ├─ a PHASE            creating (adding things)  →  refining (polishing things)
 ├─ VERSIONS           of every material; exactly one is "in use" per material; each new version
 │                     is shown as based on the one before it
 └─ FRANK              who knows all of the above
```

Never show a feature list where this model should be. A button that names an operation (render, tune, stem) is a sign the model is missing from the screen.

## Rooms: names, routes, and what each is for

User-facing names are plain words. Route folders keep their original slugs so links and state do not break.

| Shown to the user | Route slug | The work | The stage is |
|---|---|---|---|
| **Words** | `idea` | Writing and capturing | A page in the written face. Sections are recognised, not typed as brackets. |
| **Feeling** | `feel` | Exploring and listening | A **listening bench**: playable directions as cells that stay in time with each other. |
| **Music** | `beat` | Arranging and deciding | An **arrangement**: sections as columns, parts as rows; each part has a style that can differ by section. |
| **Voice** | `voice` | Recording and choosing takes | **The user's words in front of them**, with the section playing; takes as cards. |
| **Blend** | `mix` | Listening and refining | The strip itself, large; hear any part alone or muted; compare before/after. |
| **Finish** | `export` | Final listening and delivery | A full-width waveform, one primary action. |

Rooms are pages, never modals. All are always reachable; nothing is locked. Do not force the rooms into one layout. They share the shell (strip, rail, Frank panel) and nothing else.

## The shell (identical in every room)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ FRANK │ Song title (serif) · what is playing │ sections + 4 lanes │ ▶ 0:21 / 2:40 │  Song Strip, 96px
├───────┼─────────────────────────────────────────────────────┬─────────────┤
│ Rail  │                    Stage                            │ Frank panel │
│ 76px  │         (different in each room)                    │   340px     │
└───────┴─────────────────────────────────────────────────────┴─────────────┘
```

### Song Strip
- Song title (written face; pencil on hover and keyboard focus), a line saying what is playing ("Beat v1 + your words"), the **sections** as proportional blocks with their names, **four lanes** (words, feeling, music, voice), one playhead, one transport with minutes:seconds.
- Lanes show three states: *in use* (solid), *tried but not kept* (outlined), *nothing yet* (dotted). A lane being built shows a progress sweep.
- Clicking a section seeks and tells the room which section is in focus. It is real buttons in a labelled group, keyboard operable.
- The creating/refining phase appears here as a quiet two-state switch.
- Autosave is visible as a small "Saved" status. There is no save button.
- The strip is the only place song status is shown. Do not add status circles to the rail.

### Rail
- Six rooms with plain names, an icon, and a text label always shown. 76px wide; no status marks. (Planned, not built: a small dot where Frank has something waiting.)
- Account, taste and "what makes this song yours" live in one "You" menu at the bottom.

### Frank panel
- A margin, not a chat. Frank's lines are plain text with no bubbles. The user's lines use the written face with a thin rule in the room's material colour.
- A one-line **"What Frank knows"** summary is pinned at the top so the user can see Frank has the song.
- Every action Frank takes shows a **change line**: what changed, **Hear it**, **Undo** ("Direction B, simpler  Undo").
- One Frank message per action. Do not announce success before the thing exists.
- Anything Frank asks that needs an answer is also shown **on the stage** as a Frank note with the answers as buttons. The stage never says "talk on the right".
- 340px; collapses to a 56px tab; at 1100px and below it overlays the stage instead of squeezing it.

## Audio

- **One audio engine for the whole app.** Every player is a view onto it. Starting one sound stops any other. It remembers position across room changes. No component creates its own `Audio`.
- **One Play component, three sizes** (stage, card, row). Same icon and focus ring everywhere. Accessible names say *what* ("Play Last bus home", "Play take 2").
- **Waveforms show structure**, not just loudness: thin marks in the material's colour, section ticks, played part at full colour, a 2px playhead. Shown wherever audio exists.
- **Switching in time**: when ideas that belong together (Feeling directions, takes, versions) are played one after another, the switch happens at the same position and in time, not one over the other.
- **Compare** is a mode of the stage: two versions, one position, one toggle.
- Time is shown as minutes:seconds. Never bars or beats unless the user asked.

## Visual system

### Typography

| Role | Face | Sizes | Use |
|---|---|---|---|
| **Written** (the user's) | Newsreader (serif), loaded with `next/font` | 17/25 quoted words, 20/26 idea titles, 24/28 song title | Song title, lyrics, what the user said, names the user chose |
| **Frank** (the tool's) | Inter (sans), loaded with `next/font` | 15/22 body, 13/18 secondary, 12/16 smallest | Everything else |
| Section label | Inter 12 semibold, uppercase, +6% tracking | | Group headings only, never controls |
| Time | Inter 13, tabular figures | | Timecodes and durations |

Six sizes only: 12, 13, 15 (the tool's), and 17, 20, 24 (the written face). Nothing under 12px. The declared font must be the one that renders: the two faces are bundled in `frontend/app/fonts` and loaded with `next/font/local`, because a font fetched at build time can fail silently and fall back to the system font (this happened during the redesign).

### Colour (values are tokens in `globals.css`; contrast ratios computed on `surface`)

| Token | Value | Contrast | Use |
|---|---|---|---|
| `ground` | `#14110E` | | App background |
| `surface` | `#1C1814` | | Panels, cards |
| `raised` | `#26211C` | | Inputs, hover |
| `line` | `#332D26` | | Hairlines, sparingly |
| `ink` | `#EFE8DC` | 14.5 | Primary text (never pure white) |
| `ink-2` | `#B5AB9C` | 7.8 | Secondary text |
| `ink-3` | `#968D7F` | 5.4 | Tertiary text. This is the floor. |
| `words` | `#D8CBB0` | 11.0 | The user's words |
| `feel` | `#8E86C9` | 5.4 | The feeling |
| `music` | `#4FA39A` | 5.9 | The music |
| `voice` | `#E27D5F` | 6.2 | The voice |
| `frank` | `#F0A830` | 8.7 | **Only** two jobs: what is sounding right now (the playhead, and the play control that is playing, in the strip and on its card) and the one action Frank wants next (a single solid amber button per screen) |
| `ok` `caution` `problem` | `#7BB58A` `#E0B64E` `#E26A5F` | 7.4 / 9.2 / 5.4 | Always with an icon and a sentence |

Rules:
- A material's colour appears in the strip, in that room's content, and on the controls that change that material, or it is not used.
- `frank` is rare on purpose. At most: whatever is sounding (which appears in two places that are the same fact: the strip's transport and the card or room control playing it) plus one solid amber action. A Frank note's side rule is the colour of the room's material (neutral `ink-3` in Blend and Finish, which are about the whole song), never amber, and the `problem` colour only when something went wrong. If a screen has two amber *actions*, one is wrong.
- Colour is never the only signal; every material also has a lane position, a label and a shape.
- No text below 4.5:1 contrast (3:1 for text 20px and larger and for UI marks). Do not use opacity tints of muted text (`/30`, `/50`, `/60`) to make text quieter; use `ink-3`.
- No gradients, glass, glow, or decorative shadow. One overlay shadow for dialogs.

### Space, shape, density

- 4px base; steps 4, 8, 12, 16, 24, 32, 48.
- Corners: 6px on controls and cards; 2px on waveform and strip marks (they should look like marks, not pills); fully round only on the play button.
- Hairlines only where two regions of the same tone meet; otherwise separate by tone.
- Minimum click target for anything drawn thin (lanes, ticks) is 24px.

### States

| State | Rule |
|---|---|
| **Empty** | Shows the *shape* of what will be there (dotted lane, ghost card, ghost section) plus one sentence and one working action. Never an icon in a circle. |
| **Loading** | In place, on the object being made: a progress sweep and "Building the music · about a minute". Other rooms stay usable; the strip shows the lane as being made. |
| **Success** | The thing appears; one change line. No toast stack. |
| **Error** | A plain sentence in the place the thing would have been, what is safe ("your earlier beat is untouched"), and **Try again** there. Never only in the Frank panel. |
| **Blocked** | The unusable control is replaced by the one thing that unblocks it, as a link ("Record your voice first → Voice"). No dimmed controls posing as primary actions. |
| **Cold start** | "Frank is waking up…" as a status in the strip, not a blank page. The shell never unmounts while the project loads. |

### Motion

Only motion that informs: the playhead moving, a lane lighting when its material arrives (150ms), the playing section highlighted, a progress sweep while building. No hover scaling, entrance animation or pulsing. Respect `prefers-reduced-motion`.

## No music jargon

Labels, buttons, headings, tooltips and error messages use plain language. Keep these examples as the standard:
- "Add space" not "Apply reverb" · "Change the speed" not "Adjust tempo" · "Tune my vocals" not "Pitch correction" · "Download separate parts" not "Export stems" · no "render", "stem", "BPM", "key", "quantise" in the UI.
- Room names are plain (table above). If a term is unavoidable, explain it where it appears.

## Accessibility

- Every interactive element is keyboard reachable with a visible 2px focus ring in the `frank` colour. One skip link to the stage. Landmarks for rail, stage and Frank panel.
- **Space** plays/pauses from anywhere outside a text field; **←/→** move through the song; number keys 1–6 jump rooms (not while typing).
- Strip sections, lane states and every play control have accessible names that say what they are.
- Every audio control has a distinct ARIA label; no two controls on a screen share the same name.
- In the Voice room, focus lands on Record and the headphone note is announced as a status message, not a modal.
- Contrast and keyboard checks run on every room before it is called done.

## Responsiveness

Desktop-first for this MVP. **1024px is a required test width** in every room, with no truncated section names and no squashed controls: the rail stays 76px, the strip keeps all lanes, and the Frank panel overlays the stage. Mobile is not a target.

## Components

Use shadcn/ui as the base where it fits, restyled with the tokens above. Frank's interface is complex in its audio interactions, not its components: keep the component layer thin. The shared pieces every room uses are: `SongStrip`, `Rail`, `FrankPanel`, `FrankNote`, `ChangeLine`, `PlayButton`, `Waveform`, `Lane`, `AudioEngine`.

## Evidence rule

A redesign is not finished because it compiles. Each room needs: before and after screenshots of the same states, the recorded user journeys passing in a real browser, a contrast and keyboard check, and a reason for every significant element on screen.

## Research this is based on

Ableton Live (Control Bar, Overview, Arrangement/Session views), BandLab Mix Editor (timeline on every screen), Descript (the familiar view first), Teenage Engineering (colour tied to function; one rare accent), Ableton Learning Music (small playable ideas), GarageBand Live Loops (in-sync cells), Logic Pro Session Players (players with a style per section, shared arrangement markers), Moises (words, chords and sections aligned), Endlesss (each change a new version based on the last), Suno/Udio comparisons (accessible *and* controllable is the open gap). Links and what was taken from each are in `docs/design-audit/AUDIT.md`.
