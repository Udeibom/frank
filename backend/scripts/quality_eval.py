from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.generation import beat as beat_engine  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402
from app.services.generation import renderer  # noqa: E402
from scripts import baseline_audit  # noqa: E402

SR = renderer.SAMPLE_RATE


def digest(x: np.ndarray) -> str:
    return hashlib.sha1(x.tobytes()).hexdigest()[:12]


def rms_db(x: np.ndarray) -> float:
    y = x.astype(np.float32) / 32768.0 if x.dtype == np.int16 else x
    r = float(np.sqrt(np.mean(np.square(y)))) if y.size else 0.0
    return 20 * np.log10(r) if r > 1e-9 else -120.0


def section_lift(sections: list[Any], mixes: list[np.ndarray]) -> dict[str, float]:
    out: dict[str, float] = {}
    for section, mix in zip(sections, mixes):
        out[f"{section.index}_{section.name}"] = round(rms_db(mix), 2)
    values = list(out.values())
    if len(values) > 1:
        out["range_db"] = round(max(values) - min(values), 2)
    return out


def fingerprint_report(fp: dict) -> dict[str, Any]:
    clash, total = baseline_audit.melody_chord_clash(fp)
    return {
        "clashing_strong_beats": clash,
        "strong_beats": total,
        "clash_rate": round(clash / total, 4) if total else 0.0,
    }


def render_one(name: str, fp: dict, out_dir: Path) -> dict[str, Any]:
    started = time.time()
    sections, mixes, full = beat_engine.render_full_beat(fp)
    mp3 = renderer.to_mp3_bytes(full)
    (out_dir / f"{name}.mp3").write_bytes(mp3)
    return {
        "audio": {
            "digest": digest(full),
            "seconds": round(full.shape[0] / SR, 2),
            "mp3_bytes": len(mp3),
        },
        "sections": {
            "count": len(sections),
            "rms_db": section_lift(sections, mixes),
        },
        "notes": fingerprint_report(fp),
        "timing": {"render_seconds": round(time.time() - started, 2)},
        "fingerprint": fp_utils.normalize(fp),
    }


def collect(out_dir: Path, fast: bool = False) -> dict[str, Any]:
    started = time.time()
    fixtures: dict[str, dict[str, Any]] = {}
    selected = baseline_audit.FINGERPRINTS
    if fast:
        names = ("01_sad_slow_soul", "03_angry_driving")
        selected = {name: selected[name] for name in names}
    for name, fp in selected.items():
        fixtures[name] = render_one(name, fp, out_dir)
    return {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": getattr(beat_engine, "ENGINE_VERSION", None),
        "fixtures": fixtures,
        "timing": {"total_seconds": round(time.time() - started, 2)},
    }


def _flatten(prefix: str, value: Any) -> dict[str, float]:
    if isinstance(value, bool):
        return {}
    if isinstance(value, (int, float)):
        return {prefix: float(value)}
    if isinstance(value, str):
        return {prefix: value}
    if isinstance(value, dict):
        out: dict[str, float] = {}
        for key, item in value.items():
            out.update(_flatten(f"{prefix}.{key}" if prefix else str(key), item))
        return out
    return {}


def compare(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    before = _flatten("", previous.get("fixtures", {}))
    after = _flatten("", current.get("fixtures", {}))
    lines: list[str] = []
    for key in sorted(set(before) | set(after)):
        if key.endswith(".fingerprint.tempo_bpm") or ".fingerprint." in key:
            continue
        if key.endswith(".digest"):
            if before.get(key) != after.get(key):
                lines.append(f"changed audio: {key}")
        elif key in before and key in after:
            old, new = before[key], after[key]
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                delta = new - old
                if abs(delta) >= 0.01:
                    lines.append(f"{key}: {old:.2f} -> {new:.2f} ({delta:+.2f})")
    return lines


def summary(metrics: dict[str, Any], differences: list[str] | None = None) -> str:
    lines = ["Frank quality evaluation", f"created: {metrics['created_at']}"]
    if metrics.get("engine_version"):
        lines.append(f"engine version: {metrics['engine_version']}")
    for name, fixture in metrics["fixtures"].items():
        audio = fixture["audio"]
        notes = fixture["notes"]
        lines.append(
            f"{name}: {audio['seconds']:.1f}s, digest {audio['digest']}, "
            f"section range {fixture['sections']['rms_db'].get('range_db', 0):.1f} dB, "
            f"clash {notes['clashing_strong_beats']}/{notes['strong_beats']}"
        )
    lines.append(f"total render time: {metrics['timing']['total_seconds']:.1f}s")
    if differences is not None:
        lines += ["", f"differences: {len(differences)}"] + differences
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Frank quality fixtures and write repeatable metrics.")
    parser.add_argument("output_dir", nargs="?", help="directory for MP3s and metrics.json")
    parser.add_argument("--fast", action="store_true", help="render only two contrasting fixtures")
    parser.add_argument("--compare", help="previous metrics.json to compare against")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.output_dir or f"/tmp/frank_quality_runs/{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = collect(out_dir, fast=args.fast)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")

    differences: list[str] | None = None
    if args.compare:
        previous = json.loads(Path(args.compare).read_text())
        differences = compare(previous, metrics)
        (out_dir / "differences.txt").write_text("\n".join(differences) + "\n" if differences else "no differences\n")

    text = summary(metrics, differences)
    (out_dir / "summary.txt").write_text(text)
    print(text, end="")
    print("Output written to", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
