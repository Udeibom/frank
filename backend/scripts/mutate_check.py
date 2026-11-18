"""
Prove property tests can fail: apply one small break to the source, run the named test, expect a failure, restore.
Usage: venv/bin/python scripts/mutate_check.py   (each mutation: file, old text, new text, test id)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MUTATIONS = [
    ("app/services/refine/propose.py", "        if sig in seen:\n            continue\n", "", "tests/test_properties_refine.py::test_directions_apply_are_distinct_and_two_or_three"),
    ("app/services/refine/propose.py", "            if experiment:   # an experiment changes exactly one thing; the model may not widen it\n                chosen = [d for d in chosen if len(d.actions) == 1]\n", "",
     "tests/test_properties_refine.py::test_the_model_cannot_widen_an_experiment"),
    ("app/services/jobs/refine_runner.py", "    preview_url = upload_audio(", "    projects_db.update_project_active_state('x', {})\n    preview_url = upload_audio(",
     "tests/test_properties_refine.py::test_a_preview_writes_no_version_and_no_pointer"),
    ("app/services/refine/resolve.py", "            return Resolution(version=ordered[n - 1], reason=\"ordinal\")", "            return Resolution(version={'id': 'ghost'}, reason=\"ordinal\")",
     "tests/test_properties_refine.py::test_resolver_returns_a_real_version_or_asks"),
    ("app/services/refine/experiments.py", "{\"op\": \"swap_sound\", \"part\": \"keys\", \"sound\": \"electric piano\", \"section\": keys}",
     "{\"op\": \"swap_sound\", \"part\": \"keys\", \"sound\": \"electric piano\", \"section\": keys}, {\"op\": \"bigger\"}",
     "tests/test_properties_refine.py::test_each_experiment_differs_in_exactly_one_thing"),
]


def main() -> int:
    bad = 0
    for rel, old, new, test in MUTATIONS:
        path = ROOT / rel
        src = path.read_text()
        if old not in src:
            print(f"SKIP (text not found) {rel}: {old[:40]!r}")
            bad += 1
            continue
        path.write_text(src.replace(old, new, 1))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", test],
                               cwd=ROOT, capture_output=True, text=True, timeout=600)
        finally:
            path.write_text(src)
        caught = r.returncode != 0
        bad += not caught
        print(f"{'caught ' if caught else 'MISSED '} {test.split('::')[1]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
