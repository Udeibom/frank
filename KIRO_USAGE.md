# How Frank Was Built With Kiro

This is an honest record of how we used Kiro to build Frank — what worked, what
failed, what we changed as a result. We've tried not to overclaim. Where a tool
or approach fell short, we say so and say what we did about it.

---

## MCP Servers

We run three MCP servers, configured in `.kiro/settings/mcp.json` (gitignored
because it holds a Supabase access token; see `mcp.json.example` for the shape).
Each was chosen because it solved a concrete problem we actually hit — not to
tick a box.

### Why each one

- **Supabase MCP** — we had been managing our database with hand-built `curl`
  calls to the Supabase Management API, passing a personal access token on the
  command line. That worked but was clumsy and a security smell. The MCP is the
  proper interface.
- **Context7** — we burned real time guessing library APIs during the audio
  work (see "What Context7 fixed" below). Context7 pulls current, version-exact
  docs so we stop guessing.
- **Playwright (browser) MCP** — we had been finding cross-room integration bugs
  by hand (notably the Voice→Beat→Mix state bug). A browser MCP lets Kiro click
  through the studio itself and catch them.

### Setup was not smooth — and that's part of the story

Getting the servers connected took real debugging, documented here because the
process is itself evidence of using Kiro's tooling properly.

- **Symptom:** Supabase connected immediately, but Context7 and Playwright both
  failed with `Failed to connect: Connection closed` in the Kiro MCP logs.
- **False leads we ruled out:** the packages were healthy (they completed a full
  MCP `initialize` handshake when run directly), `npx` was on PATH, and the JSON
  config was valid. So it wasn't the packages, the path, or the config syntax.
- **Root cause (found via the MCP logs + reproduction):** Kiro spawns MCP
  servers with a stripped environment whose PATH resolves the **system Node
  v18.19.1** at `/usr/bin`, not the project's **nvm Node v24.18.0**. Context7 and
  Playwright need Node ≥ 20 (they use the `File` global, added in Node 20), so
  under Node 18 they crashed instantly with `ReferenceError: File is not defined`
  — which surfaced to Kiro as "Connection closed." Supabase's server tolerates
  Node 18, which is why it alone survived.
- **Fix:** install the two packages globally and point the config's `command`
  at the absolute nvm Node 24 binary running the installed entry scripts
  directly, bypassing `npx` and the wrong Node entirely. Playwright also needed
  its Chromium browser installed (`npx playwright install chromium`).

This is the kind of environment-specific issue that no amount of guessing fixes;
the MCP logs gave us the exact error, and a reproduction confirmed the Node
version gap.

### What Context7 fixed (concrete, with before/after)

During Spec 05 (Voice Room) and Spec 07 (Export Room) — written **before** we had
Context7 — we guessed audio-library APIs and paid for it in trial and error:

- `BrickwallLimiter(threshold_db=-1.0)` — **wrong**. We hit a `TypeError` and
  discovered by experiment that the parameter is `ceiling_db`.
- `pylibrb`'s `RubberBandStretcher` API — figured out by inspecting docstrings
  and trial runs, since `inspect.signature` doesn't work on its native bindings.

With Context7 connected, querying `/spotify/pedalboard` returned the exact
constructor signatures from source — `Compressor(threshold_db, ratio, attack_ms,
release_ms)`, `Limiter(threshold_db, release_ms)`, and the separate
`BrickwallLimiter` with its configurable ceiling. Had we had this during Spec 05,
the limiter bug would never have happened. Going forward, every new library API
goes through Context7 first.

### What the Supabase MCP caught immediately

On its first real use — `list_tables` to inspect our schema instead of a curl
call — the Supabase MCP surfaced a **critical security advisory we had not
noticed**: all 12 tables have Row Level Security disabled, meaning anyone with
the anon key could read or modify every row. We did not auto-apply the fix
(enabling RLS without policies would lock out our own backend), but it is now on
the record and will be addressed when we build auth (Spec 08). The hand-built
curl workflow never would have told us this.

---

## (more sections to come: specs, hooks, custom agents, PBT, and the
## integration bug story — added as we do the work)

---

## Specs — and an honest correction

Frank's specs did not start out as Kiro specs. We wrote them first as single
Markdown files — one per feature (`01-foundation.md` … `08-auth.md`) — each with
Overview / Requirements / Design Notes / Implementation Tasks. We built the six
rooms end to end against those files. They were good documents, but they were not
Kiro's native spec format, and treating them as if they were would be overclaiming.

So we converted them. Each single file became a proper feature folder under
`.kiro/specs/<feature>/` with the three native documents:

- **requirements.md** — user stories plus acceptance criteria in EARS form
  (`WHEN <event> THEN THE SYSTEM SHALL <response>`, with `IF/THEN` for conditionals
  and `WHERE` for feature-scoped rules).
- **design.md** — architecture, components and interfaces, data models, error
  handling, testing strategy, and the real engineering decisions with their
  rationale.
- **tasks.md** — a numbered implementation plan where each task cites the
  requirements it satisfies (`_Requirements: 1.2, 3.1_`).

The originals are not deleted. They're archived unedited under
`.kiro/specs/_original-single-file-specs/` with a README that maps old to new, so
the history stays honest: we started vibe-style, built the product, then adopted
the structured flow and brought the specs up to it.

### What the conversion surfaced

Rewriting the specs against what was actually built — not what was originally
planned — caught two places where the old specs had drifted from reality:

- The originals described **MusicGen** for generation. Frank actually uses its
  own **procedural engine** (FluidSynth + SoundFont), because there is no free
  hosted MusicGen anymore. The native specs say so.
- The originals described **Basic Pitch** for pitch detection. Frank actually
  uses **librosa `pyin`**, because Basic Pitch pulls in TensorFlow (~500MB,
  neural) and breaks the free-tier budget. The native specs say so.

Each converted spec also carries its real "deferred, with reasoning" list — the
follow-ups from the code-review passes — so the tasks reflect what's done, what's
intentionally postponed, and why. The `auth` spec folder is deliberately empty:
it's the one feature we haven't built yet, and we'll run it through the native
requirements → design → tasks flow from the start rather than back-filling it.
