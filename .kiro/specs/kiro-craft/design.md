# Kiro Craft - Design (spec 12)

- Role cards: `backend/app/services/team/roles.json` is the runtime form; `scripts/check_roles.py` parses
  `frank-team.md` role headings and fields and fails on any missing or extra role. Run by the spec hook and CI.
- Listener hook: `scripts/listen_reference.py` renders `fixtures/reference_song.json` (fixed fingerprint + seed),
  runs `find_issues`, compares with `fixtures/reference_findings.json`. Triggered PostFileSave on
  `backend/app/services/generation/`. Takes ~40 s, so it runs in the background and writes a report file.
- Listener MCP: `tools/listener_mcp/server.py` (python `mcp` SDK, stdio), three tools wrapping
  `service.measure_audio` on decoded files. Added to `mcp.json.example`.
- CI: `.github/workflows/ci.yml`: ubuntu, apt ffmpeg fluidsynth librubberband, fetch soundfont (cached),
  pip install, `pytest -q`, `npm ci && npx tsc --noEmit && npm run lint`, both checkers.
- Mutation evidence: each PBT task records "reverted X, test Y failed".
