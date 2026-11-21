# Nightly listening regression (Kiro CLI + Kiro Crew)

kiro-craft spec 12, task 11 (requirement 7.5).

Every night, Frank renders its fixed reference song from the latest commit. The Listening Lab agent then listens to that render through the `frank-listener` MCP and compares it with the previous night's render. The founder judges sound by ear. This job catches regressions such as a muddy chorus, an intro that copies the verse, or a clipped ending before anyone has to listen.

## Pieces

| Piece | Where |
|---|---|
| Reference render (same song, same seed, every commit) | `backend/scripts/render_reference.py` |
| The regression run, which calls `kiro-cli chat` with the Listening Lab agent and the `frank-listener` tools only | `scripts/listening_regression.sh` |
| Reports (outside the repo; audio and its reports are never committed) | `~/frank-listening/regression/<commit>.md` |
| Schedule | Kiro Crew cron job, below |

The script exits 1 when the report's last line says `NEW LIKELY PROBLEM`. Crew counts that run as failed and alerts.

## One-time setup (on the machine that holds the repo)

1. Sign in to Kiro CLI (already installed at `~/.local/bin/kiro-cli`):
   ```bash
   kiro-cli login --use-device-flow
   ```
2. Install Kiro Crew. Follow the CLI install line on <https://kiro.dev/docs/crew/>; at the time of writing it was:
   ```bash
   curl -fsSL https://download.crew.kiro.dev/cli.sh | sh
   kirocrew setup && kirocrew doctor
   kirocrew service install          # keeps the gateway (and so the schedule) running after logout
   ```
3. Add the nightly job. It is an agent job that runs inside this repo, so the repo's steering loads:
   ```bash
   kirocrew cron add "frank-listening" \
     "Run scripts/listening_regression.sh. Reply with the report it prints, and say plainly if it ends with NEW LIKELY PROBLEM." \
     --cron "0 3 * * *" --timezone local \
     --project-path "$HOME/Frank" --timeout-secs 1800 --alert-after 1
   kirocrew cron trigger <job_id>    # run it once now to check
   ```

## Running it by hand

```bash
scripts/listening_regression.sh
cat ~/frank-listening/regression/$(git rev-parse --short HEAD).md
```

## Note on the hackathon bonus

The "Best Kiro Crew App" bonus prize asks for a separate repository created during the submission period. This job is part of Frank's own development workflow, so it is not that entry.
