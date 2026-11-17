# Kiro Craft - Requirements (spec 12)

## Introduction
How Frank is built with Kiro, made real and honest. Started Nov 12: five hooks (architecture check, secret and
frontend-audio guard, spec checker, plain-language scan on save, song tests on save), seven agents (Database
Steward, Frank Code Reviewer, Integration Tester, Listening Lab, PBT Author, Plain Language Auditor, Spec Keeper),
an `mcp.json.example`, and `KIRO_USAGE.md`. This spec finishes the rest.

## Requirements

### Requirement 1 - Role steering is the runtime prompt
#### Acceptance Criteria
1. THE specialist role cards Frank uses at runtime (spec 07) SHALL be generated from, or checked against,
   `frank-team.md`, so the steering file and the product cannot drift; a test SHALL fail when they differ.

### Requirement 2 - Hooks that do real work
#### Acceptance Criteria
1. EVERY hook SHALL run a real check and fail loudly; a hook that does nothing SHALL be removed.
2. THE Listener SHALL run from a hook after an engine change, rendering a fixed reference song and comparing its
   findings with the stored baseline (no new "likely problem" allowed without a note).

### Requirement 3 - Kiro can hear its own renders
#### Acceptance Criteria
1. THE Listener SHALL be exposed as a local MCP server (`measure_file`, `find_issues_file`, `compare_files`) so
   Kiro can check audio it produced, using the same functions as the product (Listener requirement 4.2).

### Requirement 4 - Property tests protect the invariants
#### Acceptance Criteria
1. EVERY spec's correctness properties SHALL have tests, and each test SHALL be proved able to fail (mutation
   recorded in the task evidence).

### Requirement 5 - Continuous checks
#### Acceptance Criteria
1. A GitHub Actions workflow SHALL run on every push: backend tests, frontend type check and lint, the spec
   checker and the architecture checker, using the free tier.

### Requirement 6 - Honest records
#### Acceptance Criteria
1. `README.md` SHALL describe how to run and deploy Frank as it is; `KIRO_USAGE.md` SHALL describe what was
   actually used, including what failed.
2. `mcp.json.example` SHALL list every MCP server with placeholder secrets only.
