#!/usr/bin/env python3
"""
Steering must describe the code as it is (kiro-craft spec 12, requirement 7.8).

Rules:
  T1  A library named in steering as part of the stack is installed (frontend/package.json or
      backend/requirements.txt), unless the same line says it is not installed / not used / rejected.  -> error
  T2  An environment variable named in steering is read by the code (config.py, .env.example, render.yaml or the
      frontend).                                                                                  -> warning
  T3  Steering front matter, when present, uses a known inclusion mode and fileMatch has a pattern.  -> error
Exit code 1 if any error. Usage: python3 scripts/check_steering.py [--json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEERING = ROOT / ".kiro" / "steering"

# Library names as written in steering -> the package that proves it is installed.
LIBRARIES = {
    "Tone.js": ("frontend", "tone"),
    "Zustand": ("frontend", "zustand"),
    "Tailwind CSS": ("frontend", "tailwindcss"),
    "Next.js": ("frontend", "next"),
    "WaveSurfer": ("frontend", "wavesurfer.js"),
    "Tiptap": ("frontend", "@tiptap/react"),
    "React Flow": ("frontend", "@xyflow/react"),
    "FastAPI": ("backend", "fastapi"),
    "librosa": ("backend", "librosa"),
    "pedalboard": ("backend", "pedalboard"),
    "pylibrb": ("backend", "pylibrb"),
    "pyfluidsynth": ("backend", "pyfluidsynth"),
    "mido": ("backend", "mido"),
    "soundfile": ("backend", "soundfile"),
    "gradio_client": ("backend", "gradio_client"),
    "onnxruntime": ("backend", "onnxruntime"),
}
NOT_INSTALLED = re.compile(r"not installed|not used|never needed|NOT used|rejected|planned", re.I)
ENV = re.compile(r"`([A-Z][A-Z0-9_]{3,})`")
MODES = {"always", "manual", "fileMatch", "auto"}


def installed() -> dict[str, set[str]]:
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    front = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
    back = set()
    for line in (ROOT / "backend" / "requirements.txt").read_text().splitlines():
        name = re.split(r"[=<>\[ ;]", line.strip(), maxsplit=1)[0].lower()
        if name and not name.startswith("#"):
            back.add(name.replace("_", "-"))
    return {"frontend": front, "backend": back}


def code_text() -> str:
    parts = []
    for p in [ROOT / "backend" / "app" / "config.py", ROOT / "backend" / ".env.example", ROOT / "render.yaml"]:
        if p.exists():
            parts.append(p.read_text())
    for p in (ROOT / "frontend").rglob("*.ts*"):
        if "node_modules" not in p.parts and ".next" not in p.parts:
            parts.append(p.read_text(errors="ignore"))
    return "\n".join(parts)


def check() -> list[dict]:
    findings: list[dict] = []
    have = installed()
    code = code_text().lower()
    for f in sorted(STEERING.glob("*.md")):
        text = f.read_text()
        rel = str(f.relative_to(ROOT))
        if text.startswith("---\n"):
            head = text.split("---\n", 2)[1]
            mode = re.search(r"^inclusion:\s*(\S+)", head, re.M)
            if not mode or mode.group(1) not in MODES:
                findings.append({"rule": "T3", "level": "error", "where": rel, "msg": "unknown or missing inclusion mode"})
            elif mode.group(1) == "fileMatch" and "fileMatchPattern" not in head:
                findings.append({"rule": "T3", "level": "error", "where": rel, "msg": "fileMatch without fileMatchPattern"})
        for n, line in enumerate(text.splitlines(), 1):
            for lib, (side, package) in LIBRARIES.items():
                if f"**{lib}**" in line and not NOT_INSTALLED.search(line):
                    if package.replace("_", "-") not in have[side] and package not in have[side]:
                        findings.append({"rule": "T1", "level": "error", "where": f"{rel}:{n}",
                                         "msg": f"{lib} is named as part of the stack but {package} is not installed"})
            for var in ENV.findall(line):
                if "_" in var and var != "SCREAMING_SNAKE_CASE" and var.lower() not in code:
                    findings.append({"rule": "T2", "level": "warning", "where": f"{rel}:{n}",
                                     "msg": f"{var} is named in steering but no code reads it"})
    return findings


def main() -> int:
    findings = check()
    if "--json" in sys.argv:
        print(json.dumps(findings, indent=2))
    else:
        for x in findings:
            print(f"[{x['rule']} {x['level']}] {x['where']}: {x['msg']}")
        errors = sum(1 for x in findings if x["level"] == "error")
        print(f"{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if any(x["level"] == "error" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
