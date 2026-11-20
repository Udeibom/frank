---
name: "frank-sound-engineering"
displayName: "Frank Sound Engineering"
description: "Gives Kiro ears: Frank's Listener as an MCP server plus the checks a sound engineer runs before shipping a render, in plain words."
keywords: ["audio", "music", "mixing", "mastering", "loudness", "listening", "render", "sound"]
---

# Onboarding

1. Clone Frank and create the backend environment: `cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt && bash scripts/fetch_soundfont.sh`.
2. Create the MCP environment: `python3 -m venv tools/listener_mcp/.venv && tools/listener_mcp/.venv/bin/pip install -r tools/listener_mcp/requirements.txt`.
3. Open the repository in Kiro and add this power from `powers/frank-sound-engineering` (Powers panel, Add Custom Power, import from folder or repository URL).

# Steering

You can hear. The `frank-listener` server measures audio files the way Frank's product does: loudness (BS.1770),
peak and clipping, noise floor, brightness, frequency balance, onsets per bar, chroma similarity, timing offset
against the beat, and how far sung notes sit from the scale. Use it whenever code changes how something sounds,
and never claim a change sounds better without measuring it.

## Workflow: check a render
See the `check-a-render` skill. A `likely_problem` blocks the commit.

## Workflow: compare before and after
See the `compare-before-after` skill. Same song, same seed, loudness matched.

## Workflow: explain a finding
See the `explain-a-finding` skill. Plain words for the person; numbers only when asked.

## Best practices
- Measurements find faults; only a person judges taste.
- Compare at matched loudness.
- Keep audio out of the repository.
