#!/usr/bin/env python3
"""
PreToolUse guard for file writes. Reads the hook JSON on stdin and BLOCKS
(exit 2, reason on stderr) a write that would:
  - put an API key / token literal into any file, or
  - make a frontend file import an audio-processing library.

Exits 0 (allow) for everything else, including input it cannot parse, so a
broken guard never blocks legitimate work.
"""
from __future__ import annotations

import json
import re
import sys

SECRETS = {
    "Groq key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Supabase access token": re.compile(r"sbp_[A-Za-z0-9]{20,}"),
    "HuggingFace token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "Replicate token": re.compile(r"r8_[A-Za-z0-9]{20,}"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
}
FRONTEND_AUDIO = re.compile(
    r"""(?:from|import|require\()\s*['"]((?:@spotify/)?basic-pitch|@ffmpeg/[\w-]+|ffmpeg[\w.-]*|librosa[\w.-]*|pedalboard[\w.-]*|pyrubberband[\w.-]*)['"]"""
)
PATH_KEYS = {"path", "file_path", "filepath", "targetfile", "target_file", "file"}
# Files that legitimately hold secrets and are gitignored.
ALLOWED_PATH = re.compile(r"(^|/)(\.env[\w.]*|\.kiro/settings/mcp\.json)$")


def walk(node, path_hits: list[str], texts: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and k.lower() in PATH_KEYS:
                path_hits.append(v)
            walk(v, path_hits, texts)
    elif isinstance(node, list):
        for v in node:
            walk(v, path_hits, texts)
    elif isinstance(node, str):
        texts.append(node)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    paths: list[str] = []
    texts: list[str] = []
    walk(payload.get("tool_input", payload), paths, texts)
    target = paths[0] if paths else ""
    body = "\n".join(t for t in texts if t not in paths)

    if ALLOWED_PATH.search(target):
        return 0

    for label, pat in SECRETS.items():
        if pat.search(body):
            print(
                f"BLOCKED: this write puts a {label} literal into {target or 'a file'}. "
                "Secrets belong in environment variables (backend/.env), never in code.",
                file=sys.stderr,
            )
            return 2

    if "frontend/" in target.replace("\\", "/") and target.endswith((".ts", ".tsx")):
        m = FRONTEND_AUDIO.search(body)
        if m:
            print(
                f"BLOCKED: {target} would import '{m.group(1)}'. The frontend only records "
                "and plays audio; all processing happens on the backend.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
