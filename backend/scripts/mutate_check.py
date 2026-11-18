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
    # sing-it (spec 06)
    ("app/services/audio/pitch.py", 'if abs(error) * 100.0 < max(settings["threshold_cents"], 1.0):', "if False:",
     "tests/test_properties_sing.py::test_tuning_leaves_close_notes_alone_and_moves_others_closer"),
    ("app/services/audio/harmony.py", "    return _scale_step(sung_target, scale, 2 * d)", "    return sung_target + 3 * d",
     "tests/test_properties_sing.py::test_without_chords_the_harmony_is_a_third_in_the_scale"),
    ("app/services/audio/harmony.py", "            if n % 12 in chord:\n                return n", "            if True:\n                return n + d",
     "tests/test_properties_sing.py::test_every_harmony_note_is_a_chord_note"),
    ("app/services/audio/align.py", "        out.append(float(np.clip(off * rule[\"strength\"], -cap, cap)))", "        out.append(float(off * 2))",
     "tests/test_properties_sing.py::test_tightening_never_moves_more_than_a_quarter_beat_and_never_in_the_gentlest"),
    ("app/services/audio/bleed.py", "    ok = reduction >= ACCEPT_REDUCTION_DB and voice_change > -ACCEPT_VOICE_DROP_DB", "    ok = True",
     "tests/test_properties_sing.py::test_bleed_removal_keeps_a_clean_take_as_it_was"),
    ("app/services/audio/song_notes.py", "    if r % 12 in t.scale or r % 12 == tune_pc:\n        return r", "    if True:\n        return r",
     "tests/test_properties_sing.py::test_target_is_a_song_note_or_the_tune"),
    # finish and intent (spec 11)
    ("app/services/generation/beat.py", "                    level = (LEAD_GAIN if part.lead else PART_GAIN.get(part.name, 0.7)) * gain",
     "                    level = (LEAD_GAIN if part.lead else PART_GAIN.get(part.name, 0.7))",
     "tests/test_properties_finish.py::test_the_parts_add_up_to_the_beat"),
    ("app/routers/mix.py", "MAX_CHANGES = 3 ", "MAX_CHANGES = 9 ",
     "tests/test_properties_finish.py::test_the_mix_room_makes_at_most_three_changes_and_understands_parts"),
    ("app/services/audio/mixing.py", "            if st.get(\"muted\"):\n                continue", "            if False:\n                continue",
     "tests/test_properties_finish.py::test_each_part_has_its_own_level_and_can_be_muted"),
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
