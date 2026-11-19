# Kiro Craft - Implementation Plan (spec 12)

- [x] 1. Role cards and the drift check — _Evidence: backend/app/services/team/roles.py ROLES (one card per role in .kiro/steering/frank-team.md, put into every room's prompt by `team_block`); tests/test_team_roles.py test_every_role_in_the_steering_file_has_a_runtime_card reads the steering file and passes (44 passed with the other team tests, Nov 18). Not in mutate_check.py, so not proved able to fail (task 4)_
  - _Requirements: 1.1_
- [x] 2. Hook review (remove any no-op); Listener reference hook
  - Evidence: `.kiro/hooks/listen-reference-on-engine-save.json` runs `backend/scripts/listen_reference.py` (fixed song + seed vs `tests/fixtures/reference_findings.json`; a new likely problem exits 1). The five earlier hooks each run a real script. — _PARTLY DONE: all five hooks in .kiro/hooks run a real script or test (check_architecture.py, guard_write.py, check_specs.py, check_plain_language.py, the song tests); I ran the first, third and fourth by hand today and they work (0 errors; 0 jargon findings; check_specs 0 errors). Whether Kiro fires them was not checked. MISSING: the Listener reference hook (render a fixed reference song, compare findings with a stored baseline) does not exist_
  - _Requirements: 2.1, 2.2_
- [x] 3. Listener MCP server and mcp.json.example entry
  - Evidence: `tools/listener_mcp/server.py` (measure_file, find_issues_file, compare_files) via `backend/scripts/listen_file.py`; checked with a real MCP stdio client; own venv because `mcp` needs newer libraries than the backend pins. — _NOT DONE: .kiro/settings/mcp.json.example exists but has no Listener entry, and there is no MCP server code for `measure_file`, `find_issues_file`, `compare_files`_
  - _Requirements: 3.1, 6.2_
- [ ] 4. Mutation evidence for every property test in every spec — _PARTLY DONE: backend/scripts/mutate_check.py proves tests can fail for five files: test_properties_refine, test_properties_sing, test_properties_finish, test_properties_taste, test_creative_director. MISSING: the other property files have no mutation entry (21 test_properties_*.py files exist), including engine, ops, listener, team roles and plain-language, lead, song, lyrics, intake, jobs, auth, audio, mastering, comp, pitch, planner, rhythm, fingerprint, signing_
  - _Requirements: 4.1_
- [x] 5. GitHub Actions CI
  - Evidence: `.github/workflows/ci.yml` (checkers, backend tests with the server's audio libraries, frontend type check + build); green on main Nov 19. — _NOT DONE: there is no .github/workflows folder_
  - _Requirements: 5.1_
- [x] 6. README and KIRO_USAGE brought up to date
  - Evidence: README rewritten Nov 19 (live URL, what it does, run, deploy, checks); KIRO_USAGE "Nov 17 to 19" section including what went wrong. — _NOT DONE: README.md and KIRO_USAGE.md were last committed Nov 14, before the team conversation, Listener, refine, sing-it, finish and deployment work. mcp.json.example lists servers (requirement 6.2) but I did not check each for placeholder secrets_
  - _Requirements: 6.1_
