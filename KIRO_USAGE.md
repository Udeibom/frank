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

---

## Cross-room integration spec and what writing it found

The worst bugs in Frank were between rooms, not inside them. So we wrote a spec
for the seams: `.kiro/specs/voice-to-export-flow/` (requirements, design, tasks).
It adds no features. It states how the four active pointers must stay consistent.

Writing its requirements meant checking each one against the code. Requirement 2.2
("a take recorded after a comp is what the Mix Room uses") **was false**:

- `upload_take` set `active_vocal_id` but never cleared `active_comp_id`.
- The Mix Room checks the comp first, so an old comp silently beat the newest
  recording. It also fetched "the newest comp" instead of the active one.
- **Fix:** "most recently chosen vocal wins." Uploading or choosing a take clears
  the comp pointer (the comp row is kept). The decision moved into a pure function,
  `vocal_resolution.py`, so it can be property-tested.

We have not yet driven this through the browser. Task 2.4 and the Playwright
click-through are still open in that spec's `tasks.md`.

## Property-based testing

Before this we had no automated tests. We added Hypothesis (`backend/tests/`,
18 tests, all passing; run with `python -m pytest` from `backend/`). The properties
come from invariants the product depends on:

- Fingerprint fields always land in 0..1 and tempo in 50..180, for any input.
- Normalizing twice equals normalizing once; the cache key ignores fields that
  don't shape the texture.
- A mix is never shorter than its longest input and never clips past headroom.
- Section gain changes **only** the named sections, by exactly the requested amount.
- Pitch shifting preserves duration; a zero shift returns the input untouched.
- The vocal resolution rule never drops an available vocal.

### What it caught

- **Real bug, found by a property:** `normalize()` crashed with `OverflowError` on
  `{"tempo_bpm": Infinity}`. Python's `json.loads` accepts `Infinity`, so an LLM
  reply could break a Feel Lab request. The broad fingerprint property did **not**
  find it at default settings; a focused float-only property failed immediately.
  Fixed by catching `OverflowError`.
- We did not find new bugs in the mixer, pitch shifter, or section gains. Those
  properties pass. The section-gain one exists because of the Spec 06 bug.

### Do these tests actually test anything?

We checked. We reintroduced two old bugs by hand and confirmed the tests fail:
a no-op section gain, and a resolver that ignores a tuned take. Both were caught.
This was a manual spot-check, not a mutation-testing tool.

### Not done yet

No frontend property tests (fast-check) yet. No test covers mastering loudness,
pitch correction accuracy, or comp assembly. Nothing here runs in CI.

---

## Browser-driven integration run (Playwright MCP + live database)

We ran the cross-room scenario from `voice-to-export-flow` against the real stack
(local frontend and backend, live Supabase). The Playwright MCP drove the browser.
Recording a take needs a microphone, so that one step used the HTTP API instead.

Scenario: a project with 2 takes, a beat and a mix. Build a comp, then upload a new
take, then open the Mix Room.

| Step | What we checked | Result |
|---|---|---|
| Comp job completes | `active_comp_id` set | yes |
| New take uploaded | `active_vocal_id` = new take, `active_comp_id` cleared | yes, after fix |
| Mix Room resolution | `_resolve_layers` returns the new take's audio | yes, after fix |
| Old comp row | still in the database | yes |
| Mix Room in the browser | shows "Mix v1 — balanced", stem list, versions | yes |

We did not capture a "before" run of the comp-wins bug. We found it by reading the
code while writing the spec, fixed it, and then verified the fixed behavior live.

### What the run found (none of it was in a spec)

1. **WAV uploads always failed.** `to_wav` wrote its output to the same path as a
   `.wav` input, and FFmpeg can't overwrite its own input. Browser recordings are
   WebM, so normal use never hit it. The error message also showed only FFmpeg's
   version banner, which hid the cause. Fixed: distinct output name, error shows the
   tail of stderr.
2. **Stale Supabase connection caused a 500.** The shared client reused a keep-alive
   connection the server had closed, giving `Server disconnected`. The browser showed
   it as a CORS error, because error responses carry no CORS headers. Fixed by
   dropping idle connections after 5 seconds. We checked DB and storage calls still
   work after a 12-second idle gap. We did not reproduce the original failure on
   demand, so this fix is based on the traceback, not on a before/after.
3. **Misleading loading state in the Mix Room.** For several seconds on this slow
   machine it showed "No mix yet" and the Idea Room's chat text, and a failed request
   left it that way forever. Fixed: per-room empty text and an error message.

### Tool problems we hit

- The first Playwright navigation returned `about:blank`; the second worked. We think
  it was a slow first compile of the route, but didn't confirm.
- The Supabase MCP's `execute_sql` fails with `crypto is not defined` (Node 18 again,
  since that server still runs through `npx`). We read the database through the
  backend client instead until the config is fixed.
- Our early snapshot was taken before the page finished loading and briefly looked
  like a bug. It wasn't; the page just needed more time.

---

## Hooks — what we had, what it caught, what we changed

**What we had.** Four hooks written early, all prompt-based (the hook hands a
paragraph of instructions to the model and the model judges the file).

**What they actually did.** Be careful here, because an early version of this
section would have flattered us. The "Audio Safety Check" hook fires on every save
of a `.ts`, `.tsx` or `.py` file. In this working session it fired on roughly 25
saves. It caught one real problem: a blocking FFmpeg call inside the `upload_take`
route (it would stall the server on a long recording). It raised one more fair
point about voice memos having no database row. Every other firing was "no
violations", mostly on edits that obviously couldn't violate anything. The other
three hooks (component scaffolder, stale import cleanup, spec progress check) have
no finding we can point to; we have no evidence they ever caught anything.

**The problem.** The four rules in that hook are checkable exactly by code. Asking a
model to read each file and judge them is slow, noisy, and unreliable.

**What we changed.**

1. `scripts/check_architecture.py` checks the same rules deterministically (AST for
   routes, regex for secrets and frontend imports, run over every tracked file).
   Its first run found **2 errors the hook had not**: the Feel Lab hum route and the
   voice-memo route both ran FFmpeg inline in the request handler, the same bug the
   hook had caught once in `upload_take`. Fixed both. Errors went from 2 to 0.
   It still reports 4 warnings (the "uploads audio without a version record"
   heuristic). We triaged them: two are by design (a throwaway preview that must not
   create a version; a helper whose caller records the version), one is the hum
   (referenced from the versioned fingerprint), and one is real (see below).
2. `scripts/guard_write.py` + a `PreToolUse` hook that **blocks** a write (exit 2)
   when it puts a key/token literal in code or imports an audio library into the
   frontend. We tested the script offline against six cases (two blocks, four
   allows, including garbage input). **Not yet verified live:** Kiro says new hooks
   activate on the next session, so we have not watched it block a real write.
3. A `Stop` hook that runs the checker at the end of each agent run.
4. We deleted the old prompt-based Audio Safety Check, since the scripts cover its
   four rules. Recoverable from git.

The other three prompt hooks are unchanged and unproven.

**Open gap the checker confirmed.** Voice-memo audio is stored in `voice-memos/` but
no database row points to it, so it can be orphaned from the project. Fixing it
needs a new table, so it is queued with the auth migration.

## Custom agents

We wrote three, in `.kiro/agents/`, next to the existing Frank Code Reviewer:

- **Plain Language Auditor** — runs `scripts/check_plain_language.py` (scans every
  string a user can read in the frontend) and then audits the LLM prompts, which a
  script can't. **We ran it.** The frontend scanner found nothing, and we checked it
  can fail by feeding it planted jargon (it flagged all of it and ignored identifiers
  such as `tempo_bpm`). The agent found real things the scanner couldn't:
  - `PitchDisplay` showed in-tune/out-of-tune by color alone, breaking our own
    accessibility rule, with red bars on the user's own singing. Fixed: distinct bar
    shapes, a text legend, a screen-reader summary, warmer color.
  - The Beat prompt told the model to say "the pads/atmosphere" ("pads" is studio
    slang). Fixed.
  - Several prompts banned only some jargon (Feel/Beat didn't ban reverb or
    compression; no prompt banned MIDI/DAW/VST). Fixed.
  It also correctly marked what it could not confirm: whether any component prints a
  raw error message, and what the live model actually says.
- **Frank Integration Tester** — drives the browser and compares it with the database
  pointers, against the `voice-to-export-flow` spec. **Written, not yet run as an
  agent.** (We did the same checks by hand earlier in this file's browser section.)
- **PBT Author** — writes Hypothesis/fast-check tests from acceptance criteria and
  must show each test failing against a mutation. **Written, not yet run as an
  agent.**

**Limits.** The plain-language guarantee for model-written replies still rests on
prompt wording; nothing verifies what the live model says. We have no sample of real
replies to audit yet.

---

## Auth, built through the native spec flow

This was the first feature we ran through requirements → design → tasks *before*
writing code (`.kiro/specs/auth/`). The spec had real consequences:

- **It changed the scope.** The old single-file spec said "add login pages and a
  middleware". Planning against the code showed that only the projects router checked
  who owned a project. Every other route trusted whatever `project_id` it was handed,
  so once real accounts existed any signed-in user could open another user's song by
  ID. The native spec made ownership a requirement (5.x), and the design enforces it
  once, at router mount time, so a future route can't forget it.
- **It corrected an earlier belief.** We had written that enabling Row Level Security
  without policies "would lock out our own backend". That was wrong for the service
  role, which bypasses RLS. We verified it instead of assuming.

### What we verified, with before/after

- **RLS (Supabase MCP + REST).** Before: the public anon key, which ships in every
  browser, could read the projects, lyrics and takes. After migration `002`: it reads 0
  rows on every table, and the backend still reads all of them. The MCP confirmed 12 of
  12 tables have RLS on. (The MCP is read-only by design, so the migration itself went
  through the Management API.)
- **Ownership, live, two real accounts:** 17 of 17 request checks plus 3 job checks
  passed. User B gets 404 for everything of user A's (project, voice takes, lyrics,
  rename, starting a mix job, A's job status); no token gets 401; `/health` stays
  public; a malformed id gets 404 rather than a 500. We deleted the test accounts and
  data afterwards.
- **Browser (Playwright MCP):** signed-out visit to `/songs` redirects to login with
  the destination remembered; a wrong login shows "That email and password didn't
  match."; mismatched passwords are blocked before submitting; sign-up lands on
  `/songs`; a new song opens; log out works; opening that song's URL while signed out
  redirects to login, and logging in returns to that exact song.
- Context7 confirmed the current `@supabase/ssr` pattern (`getAll`/`setAll` cookie
  handlers, cookies set on both request and response) before we wrote the middleware.

### Bugs this work exposed that no spec had

1. **The song list page was unreachable.** `app/page.tsx` (landing) and
   `app/(studio)/page.tsx` (dashboard) both resolved to `/`; the landing page won, so
   "All Songs" went back to the landing page. This had been broken since Spec 01 and
   our earlier browser run missed it because it navigated by URL. Fixed by moving the
   dashboard to `/songs`.
2. **A missing or foreign song still rendered the studio**, then told the user to
   "refresh". The project store swallowed every error, including a permanent 404.
   Fixed: a 404 clears the store and redirects to `/songs`; transient errors are still
   tolerated.
3. The Playwright run is how we found #2 and the misleading messages. A request-level
   test alone would have passed.

### Not done / limits (also in `auth/tasks.md`)

- **Audio files are still publicly readable by URL.** Only the `exports` bucket is
  private. URLs are unguessable but not secret; fixing it means signed URLs everywhere
  audio plays.
- **Existing songs are orphaned.** They belong to the old dev user id, so no real
  account sees them until they are reassigned.
- Not tested: token refresh mid-session, and `AUTH_REQUIRED=false` against a running
  server (the rule is property-tested, the wiring is not).
- No password reset. Rate limiting is whatever Supabase Auth applies.

## Hook note

The Component Scaffolder hook fired when we created `AuthForm.tsx`. It only acts on
empty or placeholder files, and this one was complete, so it did nothing. It has not
produced a change in this project that we can point to.

---

## Follow-ups: private audio, token refresh, live hooks, and running the agents

### Private audio (new spec: `.kiro/specs/private-audio/`)

Six of seven storage buckets were public, so anyone with an audio URL could play a
user's takes. We made all seven private. The API now hands out 2-hour signed links,
added in one place (an ASGI middleware over every JSON response) so no endpoint can
forget. Stored URLs in the database are unchanged and act as references, so no data
migration was needed. Background jobs read files with the service role.

Verified live: the API returns signed URLs that download; the permanent public form
of the same file returns 400, including a take recorded before the change; harmony,
comp, tuning, mix and export jobs all still complete. 9 property tests cover the URL
rewrite. One honest wrinkle: for a short time right after the switch, a file fetched
moments before still served from the edge cache. A few minutes later it was refused.

### Token refresh, tested deliberately

In the browser we replaced the stored session with one whose access token was expired
(and invalid), keeping the real refresh token. The next action (creating a song)
succeeded, and the cookie held a brand-new token with about an hour left. Control case:
with a garbage refresh token, navigating sent the user to login and remembered the room.

### The blocking hook, live

The `PreToolUse` guard became active in this session. We tried two real writes: a Groq-
format key into a Python file, and an `@ffmpeg/ffmpeg` import into the frontend. Both
were blocked before execution and neither file exists. This is the first hook in the
project with a demonstrated block, not just a report.

### Running the agents for real

**Frank Integration Tester.** Its first real run worked the voice-to-export contract,
private audio and the browser rooms with a throwaway account, and cleaned up after
itself (original projects verified untouched). Results:
- Passed nearly everything, with before/after pointer values for each step.
- **Found a real bug:** beat generation failed twice, then passed on the third try. We
  measured the cause: a 3.3 MB beat upload took ~30 s on this connection, but the
  storage client's default timeout is 20 s. Fixed by giving storage its own 180 s
  budget; the same upload then succeeded twice in ~17 s.
- Also flagged: sidebar status icons had no text for screen readers (fixed), and a
  stale docstring (fixed).
- Limit: it had to script Chromium directly because the Playwright MCP tools weren't
  exposed to the sub-agent.

**PBT Author.** First run hit a network error partway, after writing the comp tests;
we re-ran it for mastering. It found **two real bugs**, each confirmed by us
independently before fixing:
1. **Comp:** a take just 2 samples longer than the others produced a zero-length
   segment (`start 2.0, end 2.0`) that the UI would draw as a sliver. Fixed by folding
   sub-5 ms tails into the previous segment.
2. **Mastering:** fully silent audio crashed the export, because FFmpeg's MP3 encoder
   aborts on `loudnorm` output for silence. Fixed by skipping normalization for silence.

For both fixes we reverted the change and watched the regression test fail, then
restored it. The suite is now 51 backend tests, all passing.

### One more bug, found by the network failing

While re-running the beat test the internet connection degraded. A status poll got a
503 ("can't check your login right now") while the beat was still being built. The
frontend's `pollJob` threw on the first failed poll, so the UI would have reported a
failed beat that was actually still running. Fixed: transient errors (network, 5xx)
are retried up to 8 times in a row; 401 and 404 still stop immediately. Not yet tested
end to end against a live outage.

### Not finished
- The end-to-end beat rerun after the timeout fix was cut short by the outage. The fix
  is verified at the upload level only.
- The outage also showed the stuck-job problem the Feel Lab spec lists as deferred:
  the beat worker died on a connection error, and its "mark failed" write failed too,
  so the job stayed `processing`. The UI stops waiting after 5 minutes; a reaper that
  marks old `processing` jobs as failed is still not built. (The test account and its
  data were cleaned up once the connection returned.)
- The larger timeout has a cost: on a connection that is open but dead, a job can now
  hang for minutes per file instead of failing in 20 s.

---

## Closing the loose ends: stuck jobs and the beat rerun

### Stuck jobs (new spec: `.kiro/specs/job-reliability/`)

The outage left a job showing "processing" forever: the worker died, and its "mark
failed" write was lost too. We specified the fix before building it. Every job must
now end as complete or failed:

1. Recording a failure retries through brief network blips.
2. When the browser polls a job that hasn't changed for 10 minutes, the server marks
   it failed with a plain message. The update only matches a job that is still active
   and still old, so one that just finished is never clobbered.
3. On startup the backend fails every job left active by the previous process.
4. The browser now waits 12 minutes (longer than the server's limit), polling every
   2 s for the first minute and every 5 s after that.

Verified live: 20-minute-old processing and pending jobs were resolved on the next
poll; a fresh job and an old completed job were left alone (5/5). 6 property tests
cover the rules, and two mutations were caught.

**The live test caught a gap in our own fix.** The first restart test failed: a
network blip hit the startup sweep, which only tried once, so the orphaned job stayed
"processing". The server still started (as specified), but the job wasn't cleaned up.
We added retries to the sweep and the rerun passed. A unit test would not have found
this; only running it on a flaky connection did.

### Beat generation, end to end

With the storage timeout fix in place we ran beat generation three times in a row
against the live backend: **3 of 3 succeeded** (150–190 s each), each saved all 8
section files, and the beat plays through a signed link. Each run hit one or two
failed status polls on this connection and rode them out. Before the polling fix in
the previous round, the app would have reported each of those runs as failed.
