"""
Frank's Listener as a local MCP server (kiro-craft spec 12, requirement 3), so Kiro can hear what it rendered.

Tools: measure_file, find_issues_file, compare_files. Each runs the product's own Listener through
backend/scripts/listen_file.py in the backend's environment (the `mcp` package needs newer libraries than the
backend pins, so the two live apart; the measurements are the same code the deployed app uses).

Run: tools/listener_mcp/.venv/bin/python tools/listener_mcp/server.py   (stdio; see .kiro/settings/mcp.json.example)
"""
from __future__ import annotations

import json
import pathlib
import subprocess
from typing import Optional

from mcp.server.fastmcp import FastMCP

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / "venv" / "bin" / "python"
CLI = BACKEND / "scripts" / "listen_file.py"

mcp = FastMCP("frank-listener")


def _abs(path: str) -> str:
    """Paths are taken relative to the repository root (where Kiro works), not the backend folder."""
    p = pathlib.Path(path)
    return str(p if p.is_absolute() else (ROOT / p).resolve())


def _run(args: list[str]) -> dict:
    r = subprocess.run([str(PYTHON), str(CLI), *args], cwd=BACKEND, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return {"error": r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "the Listener failed"}
    return json.loads(r.stdout)


def _opts(kind: str, bpm: float, key: Optional[str], plan: Optional[str]) -> list[str]:
    out = ["--as", kind, "--bpm", str(bpm)]
    if key:
        out += ["--key", key]
    if plan:
        out += ["--plan", _abs(plan)]
    return out


@mcp.tool()
def measure_file(path: str, kind: str = "mix", bpm: float = 90.0, key: Optional[str] = None, plan: Optional[str] = None) -> dict:
    """Measure an audio file the way Frank's Listener does. kind: mix | beat | vocal. plan: path to a beat version's
    params JSON for section-by-section numbers."""
    return _run(["measure", _abs(path), *_opts(kind, bpm, key, plan)])


@mcp.tool()
def find_issues_file(path: str, kind: str = "mix", concern: Optional[str] = None, bpm: float = 90.0,
                     key: Optional[str] = None, plan: Optional[str] = None) -> dict:
    """What Frank's Listener would point out in this file, in plain words, optionally for a concern."""
    args = ["issues", _abs(path), *_opts(kind, bpm, key, plan)]
    if concern:
        args += ["--concern", concern]
    return _run(args)


@mcp.tool()
def compare_files(before: str, after: str, kind: str = "mix", bpm: float = 90.0, key: Optional[str] = None,
                  plan: Optional[str] = None) -> dict:
    """What changed between two renders, in plain words with the measured numbers."""
    return _run(["compare", _abs(before), _abs(after), *_opts(kind, bpm, key, plan)])


if __name__ == "__main__":
    mcp.run()
