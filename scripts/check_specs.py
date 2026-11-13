#!/usr/bin/env python3
"""
Deterministic checks that Frank's specs match the code (the specs-vs-reality drift that left
voice-to-export-flow's checkboxes behind the work).

Rules:
  S1  Every spec folder has requirements.md, design.md and tasks.md.        -> error
  S2  A task marked done that names a file must name a file that exists.    -> error
  S3  A parent task's box agrees with its children (all done / not).        -> warning
  S4  The roadmap's status agrees with the tasks:
        DONE with open tasks -> error;  BUILDING with nothing done -> warning;
        SPEC / OUTLINE with done tasks -> warning.
  S5  Every roadmap row that has moved past OUTLINE points at a real folder. -> error

Exit code 1 if any error. Usage:  python3 scripts/check_specs.py [--json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / ".kiro" / "specs"
ROADMAP = SPECS / "_roadmap.md"
NEEDED = ("requirements.md", "design.md", "tasks.md")
SEARCH_BASES = ("", "backend", "backend/app", "frontend", ".kiro/specs")

TASK = re.compile(r"^(\s*)- \[( |x)\] (.*)$")
PATH_IN_BACKTICKS = re.compile(r"`([A-Za-z0-9_./\[\]()-]+\.[A-Za-z0-9]{1,5})`")
ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([a-z0-9-]+)\s*\|.*\|\s*([A-Z]+)\s*\|\s*$")


def resolves(token: str) -> bool:
    """True if the path exists under any of the usual roots (the specs write paths loosely)."""
    return any((ROOT / base / token).exists() for base in SEARCH_BASES)


def parse_tasks(path: Path) -> list[tuple[int, bool, str, int]]:
    out = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        m = TASK.match(line)
        if m:
            out.append((len(m.group(1)) // 2, m.group(2) == "x", m.group(3), n))
    return out


def check_spec(folder: Path, findings: list[dict]) -> tuple[int, int]:
    done = open_ = 0
    for name in NEEDED:
        if not (folder / name).exists():
            findings.append({"rule": "S1", "level": "error", "where": str(folder.relative_to(ROOT)), "msg": f"missing {name}"})
    tasks_file = folder / "tasks.md"
    if not tasks_file.exists():
        return 0, 0
    tasks = parse_tasks(tasks_file)
    rel = str(tasks_file.relative_to(ROOT))
    for i, (depth, checked, text, line) in enumerate(tasks):
        done += checked
        open_ += not checked
        if checked:
            for token in PATH_IN_BACKTICKS.findall(text):
                if "/" in token and not resolves(token):
                    findings.append({"rule": "S2", "level": "error", "where": f"{rel}:{line}", "msg": f"marked done but `{token}` does not exist"})
        # S3: look at the children (deeper lines until the next line at this depth or shallower)
        children = []
        for d2, c2, _t2, _l2 in tasks[i + 1:]:
            if d2 <= depth:
                break
            children.append(c2)
        if children:
            if checked and not all(children):
                findings.append({"rule": "S3", "level": "warning", "where": f"{rel}:{line}", "msg": "parent is ticked but some children are open"})
            if not checked and all(children):
                findings.append({"rule": "S3", "level": "warning", "where": f"{rel}:{line}", "msg": "all children are done but the parent is not ticked"})
    return done, open_


def main() -> int:
    findings: list[dict] = []
    counts: dict[str, tuple[int, int]] = {}
    for folder in sorted(p for p in SPECS.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        counts[folder.name] = check_spec(folder, findings)

    if ROADMAP.exists():
        for line_no, line in enumerate(ROADMAP.read_text().splitlines(), start=1):
            m = ROW.match(line)
            if not m:
                continue
            _num, name, status = m.groups()
            where = f".kiro/specs/_roadmap.md:{line_no}"
            if status != "OUTLINE" and not (SPECS / name).is_dir():
                findings.append({"rule": "S5", "level": "error", "where": where, "msg": f"status {status} but no folder .kiro/specs/{name}"})
                continue
            done, open_ = counts.get(name, (0, 0))
            if status == "DONE" and open_:
                findings.append({"rule": "S4", "level": "error", "where": where, "msg": f"{name} is DONE but {open_} task(s) are open"})
            if status == "BUILDING" and not done:
                findings.append({"rule": "S4", "level": "warning", "where": where, "msg": f"{name} is BUILDING but no task is done"})
            if status in ("SPEC", "OUTLINE") and done:
                findings.append({"rule": "S4", "level": "warning", "where": where, "msg": f"{name} is {status} but {done} task(s) are done"})

    errors = [f for f in findings if f["level"] == "error"]
    if "--json" in sys.argv:
        print(json.dumps({"findings": findings, "counts": counts}, indent=2))
    else:
        for f in findings:
            print(f"{f['level'].upper():8s} {f['rule']} {f['where']}  {f['msg']}")
        print(f"{len(errors)} error(s), {len(findings) - len(errors)} warning(s) across {len(counts)} specs")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
