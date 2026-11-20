---
name: check-a-render
description: Measure an audio render (beat, vocal or mix) with Frank's Listener before committing code that changed how it sounds, and stop on a likely problem. Use after any change to an engine, an effect, a mix or a master.
---
# Check a render

1. Render the thing the change affects to a file (for Frank: `backend/scripts/listen_reference.py` renders the
   fixed reference song; `backend/scripts/baseline_audit.py` renders several feelings).
2. Call `find_issues_file(path, kind)` from the `frank-listener` server. `kind` is `mix`, `beat` or `vocal`.
   Pass `plan` (the version's params JSON) to get section-by-section numbers.
3. Any finding with severity `likely_problem` blocks the commit. Quote its plain words and its numbers.
4. `worth_a_look` findings go in the commit message; `note` findings can be ignored.
5. Never call a sound "better". The tool can find faults; only a person can judge taste.
