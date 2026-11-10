#!/usr/bin/env python3
"""
Deterministic checks for Frank's audio-architecture rules.

Rules (from .kiro/steering/audio-architecture.md):
  R1  Frontend never imports audio-processing libraries.      -> error
  R2  Code that uploads audio should also record a version.   -> warning (heuristic)
  R3  No API keys / secrets as string literals in tracked files. -> error
  R4  Route handlers must not run heavy audio work inline.    -> error

Exit code 1 if any error. Usage:  python3 scripts/check_architecture.py [--json]
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FRONTEND_AUDIO_LIBS = re.compile(
    r"""(?:from|import|require\()\s*['"]((?:@spotify/)?basic-pitch|@ffmpeg/[\w-]+|ffmpeg[\w.-]*|librosa[\w.-]*|pedalboard[\w.-]*|pyrubberband[\w.-]*)['"]"""
)
SECRET_PATTERNS = {
    "Groq key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Supabase access token": re.compile(r"sbp_[A-Za-z0-9]{20,}"),
    "HuggingFace token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "Replicate token": re.compile(r"r8_[A-Za-z0-9]{20,}"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
}
# Functions that do real DSP/render work. Calling them directly inside a route
# handler blocks the worker; they must go through a background job or to_thread.
HEAVY_CALLS = {
    "correct_pitch", "generate_harmony", "build_comp", "render_mix",
    "master", "detect_pitch_contour", "compose", "render_beat", "to_wav",
}
UPLOAD_CALL = "upload_audio"
VERSION_HINT = re.compile(r"(create|insert|save|add)_\w+|_version|mark_complete")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [ROOT / p for p in out if (ROOT / p).is_file()]


def call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def check_frontend(files: list[Path], findings: list[dict]) -> None:
    for p in files:
        rel = p.relative_to(ROOT)
        if rel.parts[0] != "frontend" or p.suffix not in {".ts", ".tsx"}:
            continue
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            m = FRONTEND_AUDIO_LIBS.search(line)
            if m:
                findings.append({"rule": "R1", "level": "error", "file": str(rel),
                                 "line": n, "msg": f"frontend imports audio library '{m.group(1)}'"})


def check_secrets(files: list[Path], findings: list[dict]) -> None:
    for p in files:
        if p.suffix in {".png", ".jpg", ".sf2", ".mp3", ".wav", ".lock"} or p.name == "package-lock.json":
            continue
        rel = p.relative_to(ROOT)
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for label, pat in SECRET_PATTERNS.items():
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                findings.append({"rule": "R3", "level": "error", "file": str(rel),
                                 "line": line, "msg": f"possible {label} literal"})


def check_backend(files: list[Path], findings: list[dict]) -> None:
    for p in files:
        rel = p.relative_to(ROOT)
        if rel.parts[:2] != ("backend", "app") or p.suffix != ".py":
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError as e:
            findings.append({"rule": "R4", "level": "error", "file": str(rel),
                             "line": e.lineno or 0, "msg": "syntax error"})
            continue
        in_router = "routers" in rel.parts
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
            names = {call_name(c) for c in calls}
            # R4: direct heavy call in an async route handler
            if in_router and isinstance(fn, ast.AsyncFunctionDef):
                for c in calls:
                    if call_name(c) in HEAVY_CALLS:
                        findings.append({"rule": "R4", "level": "error", "file": str(rel),
                                         "line": c.lineno,
                                         "msg": f"heavy call '{call_name(c)}()' runs inline in route '{fn.name}'"})
            # R2: uploads audio but records nothing (heuristic)
            if UPLOAD_CALL in names:
                src = ast.get_source_segment(p.read_text(), fn) or ""
                body_names = " ".join(n for n in names if n)
                if not VERSION_HINT.search(body_names):
                    findings.append({"rule": "R2", "level": "warning", "file": str(rel),
                                     "line": fn.lineno,
                                     "msg": f"'{fn.name}' uploads audio but calls no create/save/version function"})


def main() -> int:
    files = tracked_files()
    findings: list[dict] = []
    check_frontend(files, findings)
    check_secrets(files, findings)
    check_backend(files, findings)

    if "--json" in sys.argv:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['level'].upper():7} {f['rule']} {f['file']}:{f['line']}  {f['msg']}")
        errors = sum(f["level"] == "error" for f in findings)
        warns = len(findings) - errors
        print(f"\n{errors} error(s), {warns} warning(s) across {len(files)} tracked files")
    return 1 if any(f["level"] == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
