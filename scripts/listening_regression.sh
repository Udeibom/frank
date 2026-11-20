#!/usr/bin/env bash
# Listening regression through Kiro CLI (kiro-craft spec 12, requirement 7.5).
#
# Renders Frank's fixed reference song from the current commit, then asks the Listening Lab agent in Kiro CLI to
# listen to it through the frank-listener MCP and compare it with the last commit's render. The report lands in
# ~/frank-listening/regression/<commit>.md (outside the repo: audio and its reports are never committed).
#
#   scripts/listening_regression.sh            # run once (Kiro Crew runs this nightly; see docs/kiro/crew.md)
#
# Exit 1 when the report says NEW LIKELY PROBLEM.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git pull --ff-only --quiet || true
SHA="$(git rev-parse --short HEAD)"
OUT="$HOME/frank-listening/reference/$SHA"
REPORTS="$HOME/frank-listening/regression"
mkdir -p "$REPORTS"

if [ ! -f "$OUT/song.wav" ]; then
  (cd backend && venv/bin/python scripts/render_reference.py "$OUT" >/dev/null)
fi
PREV="$(ls -1dt "$HOME"/frank-listening/reference/*/ 2>/dev/null | grep -v "/$SHA/" | head -1 || true)"

PROMPT="You are running Frank's nightly listening regression. Use only the frank-listener MCP tools.
1. Call find_issues_file on $OUT/song.wav with kind=beat and plan=$OUT/plan.json.
2. ${PREV:+Call compare_files with before=${PREV}song.wav after=$OUT/song.wav kind=beat plan=$OUT/plan.json.}
3. Write a report in markdown, at most 15 lines: commit $SHA, each finding in plain words with its numbers, what changed since the previous render, and on its own line either 'NEW LIKELY PROBLEM' or 'NO NEW PROBLEM'. Print only the report."

KIRO="$(command -v kiro-cli || echo "$HOME/.local/bin/kiro-cli")"
if [ -x "$KIRO" ]; then
  "$KIRO" chat --v3 --no-interactive --agent "Listening Lab" \
    --trust-tools=@frank-listener/measure_file,@frank-listener/find_issues_file,@frank-listener/compare_files \
    "$PROMPT" > "$REPORTS/$SHA.md"
else
  # No Kiro CLI on this machine: the same measurement without the agent, so the nightly job still means something.
  (cd backend && venv/bin/python scripts/listen_reference.py) > "$REPORTS/$SHA.md" 2>&1 || echo "NEW LIKELY PROBLEM" >> "$REPORTS/$SHA.md"
fi
cat "$REPORTS/$SHA.md"
! grep -q "NEW LIKELY PROBLEM" "$REPORTS/$SHA.md"
