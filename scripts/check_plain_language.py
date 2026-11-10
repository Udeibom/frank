#!/usr/bin/env python3
"""
Plain-language audit of everything the user can read in the frontend.

Frank's rule (design-and-ui.md / conversation-layer.md): no music-production
jargon in labels, buttons, placeholders, tooltips or messages. This scans the
text a user sees (JSX text, label-like attributes, chat message strings) and
reports banned terms with the plain alternative to use.

Exit 1 if any finding. Usage:  python3 scripts/check_plain_language.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# term regex -> suggested plain wording
JARGON = {
    r"\bBPM\b": "the speed of the song",
    r"\btempo\b": "the speed",
    r"\breverb(?:eration)?\b": "space / echo",
    r"\bEQ\b|\bequali[sz](?:er|ation)\b": "tone",
    r"\bcompress(?:ion|or|ed)?\b": "smoothing out",
    r"\bstems?\b": "a layer / a part",
    r"\bMIDI\b|\bDAW\b|\bVST\b": "(never shown)",
    r"\b\d*\s?k?Hz\b": "(never shown)",
    r"\bdB\b|\bdecibels?\b|\bLUFS\b": "(never shown)",
    r"\bquanti[sz](?:e|ation)\b": "locking to the beat",
    r"\bsaturation\b": "warmth",
    r"\bpitch[- ]correction\b": "tune my vocals",
    r"\bauto-?tune\b": "tune my vocals",
    r"\blow[- ]?pass\b|\bhigh[- ]?pass\b": "clean up the low end",
}
JARGON_RE = {re.compile(k, re.I if k not in (r"\bBPM\b", r"\bEQ\b|\bequali[sz](?:er|ation)\b", r"\bMIDI\b|\bDAW\b|\bVST\b", r"\bdB\b|\bdecibels?\b|\bLUFS\b") else 0): v
             for k, v in JARGON.items()}

# Text a user can read:
JSX_TEXT = re.compile(r">\s*([^<>{}\n][^<>{}\n]*?)\s*<")
ATTR_TEXT = re.compile(r"""\b(?:placeholder|aria-label|title|alt|label|description|emptyText)\s*=\s*["']([^"']+)["']""")
MSG_TEXT = re.compile(r"""\b(?:content|message|text|label|title|description|greeting)\s*:\s*(?:"([^"]+)"|'([^']+)'|`([^`]+)`)""")


def user_strings(src: str):
    for n, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*", "import ")):
            continue
        for rx in (JSX_TEXT, ATTR_TEXT, MSG_TEXT):
            for m in rx.finditer(line):
                text = next((g for g in m.groups() if g), "")
                if " " in text.strip() or text.strip()[:1].isupper():
                    yield n, text


def main() -> int:
    findings = []
    for base in ("frontend/app", "frontend/components"):
        for p in (ROOT / base).rglob("*.tsx"):
            src = p.read_text(errors="ignore")
            for n, text in user_strings(src):
                for rx, plain in JARGON_RE.items():
                    m = rx.search(text)
                    if m:
                        findings.append((p.relative_to(ROOT), n, m.group(0), plain, text.strip()))
    for f, n, term, plain, text in findings:
        print(f"{f}:{n}  '{term}' -> say {plain}\n    \"{text[:90]}\"")
    print(f"\n{len(findings)} jargon finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
