# How Frank Was Built With Kiro

This is an honest record of how we used Kiro to build Frank — what worked, what
failed, what we changed as a result. We've tried not to overclaim. Where a tool
or approach fell short, we say so and say what we did about it.

## Summary (as of Nov 21, 2026)

| Kiro feature | How Frank uses it | Where |
|---|---|---|
| Specs | 14 specs, each with requirements, design and tasks. Every ticked task names its evidence. The Spec Keeper agent un-ticks a task when the evidence is missing. | `.kiro/specs/`, `scripts/check_specs.py` |
| Steering | Product, tech and structure files always load. Six room and infrastructure files load only when a matching file is open (fileMatch). `scripts/check_steering.py` fails CI when steering disagrees with the code. | `.kiro/steering/` |
| Skills | The team roles and producer craft, loaded when the work needs them. | `.kiro/skills/` |
| Hooks | Property tests run after a task completes. Two agent hooks run on save: a jargon review of prompt files, and a reference-song render after an engine change. A steering check runs on stop. | `.kiro/hooks/` |
| Custom agents | Spec Keeper, PBT Author, Listening Lab, Frank Code Reviewer, Integration Tester, Plain Language Auditor, Database Steward, and a Producer that runs them in order. | `.kiro/agents/` |
| MCP | Supabase, Context7 and Playwright, plus Frank's own Listener, which lets Kiro hear a render with the product's own measurements. | `.kiro/settings/mcp.json.example`, `tools/listener_mcp/` |
| Power | `frank-sound-engineering` packages the Listener MCP with its skills. | `powers/frank-sound-engineering/` |
| Kiro CLI + Crew | A nightly listening regression. | `scripts/listening_regression.sh`, `docs/kiro/crew.md` |

Tests: 505 backend tests, 252 of them Hypothesis properties. The frontend has 13 vitest tests with fast-check properties. CI runs all of them, plus the plain-language, steering and break-it-on-purpose (mutation) checks.

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
intentionally postponed, and why. The `auth` spec was the one feature built through the native
requirements → design → tasks flow from the start (see "Auth, built through the native spec
flow" below); it is complete.

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
*(Updated Nov 21: the frontend now has fast-check properties, the backend has 252 Hypothesis properties, and
both run in CI. See the summary at the top and the Nov 19 to 21 section.)*

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

- **(Fixed later by the `private-audio` spec; see below.)** Audio files were publicly readable
  by URL at this point; every bucket is now private and played through signed links.
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

## Nov 11 to 12: the vision reset, and an honest account of how Kiro was used

The founder compared Frank with what the project was meant to be and found a gap. What we did,
and what we did not do well, in order.

### What worked
- **Research before building.** Four `context-gatherer` sub-agents ran in parallel to audit the
  conversation layer, the music engine, the voice/mix/export pipeline and the Kiro setup itself.
  The audit found the engine was deterministic and flat (same input, same audio; five fingerprint
  fields did nothing; the chorus was barely louder than the verse). `backend/scripts/baseline_audit.py`
  then proved those claims by rendering five beats and measuring them. One claim was wrong
  ("repeated sections are byte-identical"); the measurement corrected it.
- **Specs before code.** `.kiro/specs/_roadmap.md` maps all 13 planned specs, with a coverage
  matrix tying every founder decision, team role, demo story and audit finding to the spec that
  owns it. Specs `song-record`, `start-from-any-input`, `listener` and `song-engine` were written
  with requirements, design and tasks before any code, then built in that order.
- **Property tests that are proven able to fail.** 85+ new properties. Every one was checked by
  breaking the code on purpose and watching the test fail; three tests turned out too weak that way
  (a tuning test passed with tuning switched off) and were strengthened. One property compares the
  fast pitch tracker with librosa's own, bit for bit, including on real hums.
- **Real-world checks beat unit tests.** The browser run found that the "Your tune" tick did not
  update after confirming; timing the summary request found it made eight database calls in a row.

### What we got wrong, and said so
- **The Kiro setup stood still.** For most of the session the four custom agents were not used at
  all, no new agent or hook was added, and the spec for Kiro craft stayed an outline. The founder
  asked about it directly; the response is below.
- **Three of five hooks never fired** (spec progress, component scaffolder, import cleanup). They
  were deleted, not defended.
- **Tuning by ear took several rounds** because the first listening files were hard to judge
  (a piano exposes every small mistake). The founder's ears found what measurements could not.

### Agents run in parallel on the uncommitted work
Three existing agents reviewed the same change set at the same time, read-only:

| Agent | What it found | Fixed |
|---|---|---|
| Frank Code Reviewer | Memory grew with hum length (one long hum could crash a small server); confirm could write a version and then fail; an unused function broke the append-only rule | Yes: 60 s cap, one analysis at a time, smaller tables, validate-before-write, function removed |
| Frank Integration Tester | Two parallel first writes left a facet with two roots (7 of 8 runs, reproduced in the live database); confirming twice added duplicate versions | Yes: migration 004 adds a one-root index and refuses edits; writes retry; confirm is idempotent. Live re-run: 8 of 8 correct |
| Plain Language Auditor | 23 findings; the worst were rejection messages that blamed the user when a microphone or connection was the cause | Yes: reworded; the screen now says when the connection dropped and that the hum is safe |

### New Kiro pieces
- **Hooks that do something:** `check-specs-on-stop` (specs vs code), `song-tests-on-save`
  (12-second property tests when song code is saved), `plain-language-on-save` (jargon scan when a
  screen file is saved). Its first run found two tasks ticked for files that never existed and two
  parent/child disagreements, which were corrected.
- **Agents for work done by hand:** `Spec Keeper`, `Listening Lab` (blind comparisons for a founder
  who judges by ear), `Database Steward` (additive migrations, checks the data first, proves the result).
- **`mcp.json.example`** is committed so the MCP setup is visible without exposing the token.

### Still to do for Kiro craft
Role steering that doubles as runtime prompts for the specialists; the audio-analysis MCP server
that lets Kiro check its own renders (after the Listener exists); property tests for the frontend;
CI that runs the tests; a spec-first versus retrofit comparison in the write-up.

## Nov 13: reading a song's words, and the new agents' first real runs

### What was built
`services/intake/lyrics.py` reads a song's words for feeling and structure, `merge.py` lets the
words suggest a direction for the music without overriding anything the person settled, and the Idea
Room got a "Tell me what you hear in my words" button.

### A design decision the data forced
The first version asked the model for one overall mood. On the same grandmother lyric it said "bright"
in 1 of 5 runs, even at temperature 0, with 0.85 confidence. So the model now labels how each
*section* feels, and plain code decides the mood from those labels and sets how sure to be (less sure
the more the song is split, or "both at once"). Over 15 later readings it was never confidently wrong:
the happy song stayed warm, the funeral-laughter song stayed unsure, and the grandmother song always
asked "Should the song feel more like gentle comfort or like quiet grief?". The model interprets; the
code decides.

### The new agents, used for real
- **Spec Keeper** (first run) found that four ticked tasks had no evidence: a route that was never built
  (separate routes per kind were built instead), a merge rule that only exists on paper, and a "tests can
  fail" claim that covered only some tests. It unticked them, rewrote the stale parts of `design.md`, and
  found one test failing on a timing limit. Result: the task list now says what is true.
- **Frank Code Reviewer** found five must-fix problems in the words reader, which were fixed:
  model text reaching the screen unfiltered (lyrics are in the same conversation, so a lyric could ask for a
  link or music jargon), a long song cut mid-line without saying so, no protection against repeated presses
  on a rate-limited model, a failed side-save that would look like a failed read, and a button that vanished
  while working (stranding keyboard focus).
- A live run against the real model then found a bug no reviewer or fake-model test could see: the pinned
  Groq library takes `max_tokens`, not `max_completion_tokens`, so every read failed. A contract test now
  binds our calls to the installed library's signature.

### Honest notes
- The flaky tests were my test generator, not the product: it threw away ~95% of random tunes and Hypothesis
  sometimes refused to run. It now builds valid tunes directly.
- A bulk text replacement once matched the wrong place and mangled a file; it was caught immediately by the
  tests and repaired by hand. Edits are now anchored and asserted (the pattern must match exactly once).
- One decision is left for the founder: requirement 6.4 says an earlier value is replaced by a *more
  confident* new one. The merge only fills gaps and asks when inputs disagree, which matches the founder's
  rule that perception and the person's own words win. Either the requirement is reworded to match, or
  per-value confidence is stored.

### Nov 13, later: the founder tried it, and the research that followed
The founder pasted a real lyric into the Idea Room (anger and sorrow together) and Frank asked "more like
defiant anger or deep sorrow?", a question with no right answer, since the song is both. Two things came
out of that:
- **A fix, from a real user's real words.** Anger became a feeling of its own; sorrow and anger count as
  one dark mood; the mood got its own confidence (computed from the sections, because the model's number
  varied from 0.45 to 0.65 on identical words and was deciding whether Frank asked). The same lyric now
  reads the same way on every run and gets no question. Five old tests described rules that had
  deliberately changed; each was rewritten on purpose, not edited until it passed, and a bar that the test
  had been reading from the code was pinned as plain numbers after a break survived.
- **Research instead of assumption.** The founder said, correctly, that nobody on the team is a producer
  and that Frank should not assume what a good producer question is. Web search and fetch found and read
  Rick Rubin (CBS *60 Minutes*), Dan Wilson and Teddy Geiger (*Switched on Pop*) and Jack Antonoff (GRAMMY.com).
  The write-up (`.kiro/steering/producer-craft.md`) separates what was read from what could only be seen
  as a paywalled opening or a search snippet, says plainly that no list of producers' exact questions was
  found, and flags one conflict with an earlier decision: two working songwriters call the "sounds like"
  game a trap, which bears on the Creative Director idea. That one is left to the founder.


## Nov 17 to 19: building the rest of the specs and shipping it

The founder's instruction was "build the whole spec, deploy it, and don't stop to ask me". Work went spec by spec
(`.kiro/specs/_build-progress.md` is the checkpoint file written for exactly this: the network dropped more
than ten times, and each time the session resumed from that file, not from memory).

### What Kiro's pieces did, concretely

- **Specs as the contract.** Specs 06 to 13 were written first (requirements, design, tasks), then built in order.
  Each `tasks.md` line now carries its evidence (file, test, production check). The **Spec Keeper** agent was run
  over ten task files at the end; it un-ticked tasks whose ticks had no evidence (for example a Beat Room timeline
  layer list that doesn't exist) and wrote down three decisions the founder still has to make.
- **Property tests that found real bugs, not just guarded them.** Examples from this stretch, each found by a
  Hypothesis test and fixed in the product: "try another" on a part that isn't playing, "bigger" past the top and
  swapping to the sound already playing all *said* they changed the song and changed nothing
  (`ops.apply_audible` now composes the score and refuses a change you could not hear); duplicate findings
  hid that only one direction was really on offer; a song shape where only one experiment was possible.
- **Breaking the code on purpose.** `backend/scripts/mutate_check.py` applies one small break per property and
  expects a test to fail. It covers the refine loop, sing-it, finish, taste and the Creative Director. One
  mutation survived at first (harmony without chords was never tested); a test was added.
- **Listening Lab agent** prepared blind A/B listening sets from the founder's real hums, with a separate answer
  key. Its numbers changed a design decision: the spec said "tune toward the tune's note within two steps", and
  real hums showed that moved notes up to 1.8 steps, rewriting the person's melody. Tuning now never moves a note
  past its neighbour (max 0.94 steps on the same hums). The files wait for the founder's ears.
- **Live checks against the deployed site**, all scripts in `backend/scripts/ops/`: the full walkthrough
  (`e2e.py`), the demo stories (`demo_runs.py`, records in `docs/demo-runs/`), a two-user privacy check
  (`rls_check.py`: "RLS OK"), the start paths (`start_check.py`).
- **A fourth MCP server: Frank's own Listener** (`tools/listener_mcp/`). Kiro can now ask "what's wrong with this
  render" with the exact functions the product uses. It lives in its own environment because the `mcp` package
  needs newer libraries than the backend pins; installing it into the backend once broke FastAPI's pinned
  Starlette, which was caught and rolled back before anything was committed.
- **A new hook**: an engine change renders a fixed reference song in the background and compares the Listener's
  findings with a stored baseline (`backend/scripts/listen_reference.py`).
- **CI** (`.github/workflows/ci.yml`): its first run failed because GitHub's `ubuntu-latest` had moved to a
  release with different audio package names; pinned to the server image's release.

### What went wrong, honestly

- **Edits that silently didn't apply.** Several scripted edits matched nothing (the text shown in the tool output
  hides blank lines) and were not checked. One of them meant take responses never carried the new fields; the
  production walkthrough caught it. After that every scripted edit asserted it matched exactly once.
- **The first model behaviour wasn't the spec's.** Asked "make it sound like Billie Eilish", the live model
  described the artist's sound and moved the song toward it, against the Creative Director spec. The rule in the
  prompt was not enough; code now replaces that reply with one plain question and keeps only the feeling words.
- **A rendering bug nobody would have heard.** Rendering the song's parts separately (for per-part mixing) gave
  parts that didn't add up to the beat. Cause: FluidSynth applies notes on 64-sample blocks and its echo carried
  into the next render. Every render now starts on a block boundary and drains the echo.
- **The flaky test** noted for a week was a 200 ms Hypothesis deadline on a cold first call, not a product bug.
- **Not tried in a real browser with a microphone**: the sing-along timing (lead-in, delay check), the start
  surface recording and the A/B players are type-checked and built, and their server side runs on production,
  but nobody has sung into them yet. That is the founder's first test.

---

## Nov 19 to 21: Frankenstein (spec 14) and the Kiro craft tasks

Prompted by a review of how Frank used Kiro (`docs/research/FRANK-KIRO-AND-TECHNOLOGY-REVIEW.md`), the founder asked
for every improvement in it. Two plans came out of that. Kiro-craft got requirement 7 and tasks 7 to 15. A new spec,
`.kiro/specs/frankenstein/`, covers the outside parts Frank is now stitched from: two Hugging Face Spaces of free
models, mined datasets, recorded instruments, and starting points from outside music. Those include a picture,
the time and weather, the person's camera, a spoken voice, the feelings in their words, and how words sound.
The credit for each part is in `THIRD_PARTY.md`.

### What Kiro's pieces did, concretely
- **The rules were checked before anything was built.** The research step read the terms of every service
  first. Two plans were changed as a result. Deezer previews were dropped: their terms forbid AI use and local
  copies, so Frank uses Jamendo (Creative Commons) and the person's own uploads instead. Gemini is never called
  for the EEA, Switzerland or the UK, where its free tier is not allowed; an unknown region is treated the same.
- **The Listener MCP found a problem by listening.** Kiro rendered the reference song through `frank-listener`
  after the Lakh arrangement statistics went in, and found that the intro had become a copy of verse 1. The fix:
  an intro is always smaller than the verse it leads into. The test that guards it lives with the other
  arrangement properties.
- **fast-check found a frontend bug.** The first frontend property (`frontend/tests/songShape.test.ts`) showed
  that `sectionAt` rounded a time at a section boundary into the wrong section. It was fixed the same hour.
- **Measurement decided between two pitch trackers.** Basic Pitch was added as a second hum tracker, and
  `backend/scripts/pitch_compare.py` scored both on the founder's real hums. pyin scored 0.98 and Basic Pitch 0.81
  (Basic Pitch was weaker on vibrato and breathy hums), so pyin stays the default.
- **The prompt-review hook ran twice on `brief.py`.** The first run found reference differences reaching the
  prompt unfiltered, and those now pass the jargon filter. The second run, after task 57 replaced the raw dumps of
  the fingerprint and the beat, vocal and mix records with everyday words, found layer, effect and kind names
  passing straight from the data. Every record line now goes through `plain.guard`.
- **Kiro craft tasks.**
  - The team roles and producer craft became Skills.
  - Six steering files now load by fileMatch, and `scripts/check_steering.py` catches drift.
  - Three hooks were added: property tests after a task, a jargon review of prompts on save, and a steering check
    on stop.
  - A Producer agent runs Spec Keeper, PBT Author, Listening Lab and Frank Code Reviewer in order.
  - The `frank-sound-engineering` Power packages the Listener. Its MCP was tested with a real client.
  - The nightly listening regression is ready for Kiro Crew (`docs/kiro/crew.md`).

### What went wrong, honestly
- **Versions that would not live together.** ZeroGPU needs torch 2.8 or newer, Gradio 6 needs `huggingface_hub` 1.x,
  and transformers 4.57 needs the old one. The Spaces are pinned to Gradio 5.50. Kokoro had to run on CPU, and
  DDSP's install conflicts took several rounds.
- **A client bug that only the live Space showed.** The Space client was passing `token=` where `gradio_client`
  expects `hf_token=`, so every call was made without credentials. It worked locally and failed live.
- **Things still waiting** at the time of writing:
  - Stable Audio is gated until its licence is accepted on the Hugging Face account.
  - Freesound, Jamendo, Exa and Firecrawl need free keys from the founder. Each feature says so plainly until then.
  - Kiro CLI sign-in needs the founder at the keyboard.
  - The ACE-Step blind test is not prepared yet.
  - Diff-MST was dropped: no public trained model exists.
