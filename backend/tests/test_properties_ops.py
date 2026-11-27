"""Typed beat edits (song-engine spec 04, requirement 5.2-5.4, 6.2; tasks 7.1, 7.4, 9.3)."""
from __future__ import annotations

import copy

import pytest
from hypothesis import given, settings, strategies as st

from app.services.generation import beat, composer, ops
from app.services.generation import fingerprint as fp_utils

FP = fp_utils.normalize({"tempo_bpm": 96, "key": "A minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.6, "brightness": 0.4})
SEED = 1234
PARTS = list(ops.PARTS)


def plan():
    sections, _ = beat.build_beat_plan(FP)
    for s in sections:
        s.uid = s.index
    return sections


def score(sections, seed=SEED):
    """Notes per (section uid, part) for the whole song, built exactly as the renderer builds them."""
    _, ctxs, progs = beat.plan_contexts(sections, FP, seed)
    out = {}
    for s, c in zip(sections, ctxs):
        for p in composer.compose_section(s.name, progs[s.name], s.bars, s.energy, s.density, layers=s.layers, ctx=c):
            out[(s.uid, p.name)] = (p.preset, [(e.note, round(e.start, 4), round(e.duration, 4), e.velocity) for e in p.events])
    return out


# Parts that are built FROM other parts (a reply to the tune, the closing chord) may follow an edit to those parts.
DERIVED = {"color", "color_once", "riser", "sweep", "finale_keys", "finale_pad", "finale_bass", "finale_drums"}


@settings(max_examples=25, deadline=None)
@given(st.sampled_from(["busier", "sparser", "try_another", "swap_sound"]), st.sampled_from(["bass", "keys", "melody"]), st.integers(0, 7))
def test_an_edit_to_one_part_of_one_section_changes_nothing_else(kind, part, idx):
    before = plan()
    if part not in before[idx].layers:
        return
    op = {"op": kind, "part": part, "section": idx}
    if kind == "swap_sound":
        op["sound"] = "vibraphone"
    try:
        after, seed, changes, _ = ops.apply_audible(before, SEED, [op], FP)
    except ops.OpError as exc:
        # asking for what is already there (keys that already play vibraphone) is said, never silently "done"
        assert "already" in str(exc)
        assert score(ops.apply_operations(before, SEED, [op])[0]) == score(before)
        return
    a, b = score(before), score(after, seed)
    assert changes and seed == SEED
    differ = {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    assert differ, "the edit must change the music"
    uid = before[idx].uid
    assert all(k[0] == uid and (k[1] == part or k[1] in DERIVED) for k in differ), differ


def test_the_input_plan_is_never_modified_and_a_bad_edit_changes_nothing():
    before = plan()
    frozen = copy.deepcopy(before)
    ops.apply_operations(before, SEED, [{"op": "busier", "part": "drums", "section": 1}])
    assert [vars(s) for s in before] == [vars(s) for s in frozen]
    with pytest.raises(ops.OpError):
        ops.apply_operations(before, SEED, [{"op": "busier", "part": "drums", "section": 1}, {"op": "remove_section", "section": 99}])
    assert [vars(s) for s in before] == [vars(s) for s in frozen]


@pytest.mark.parametrize("raw", [
    [], [{"op": "explode"}], [{"op": "busier", "part": "trombone"}], [{"op": "resize", "section": 0, "bars": 0}],
    [{"op": "swap_sound", "part": "keys", "sound": "theremin"}], [{"op": "busier", "part": "keys", "section": 1, "extra": 1}],
    [{"op": "add_fill", "section": 5}],     # the bridge has no drums at this energy
    [{"op": "rename_section", "section": 0, "label": ""}], [{"op": "rename_section", "section": 99, "label": "Ending"}],
])
def test_invalid_edits_are_refused_in_plain_words(raw):
    with pytest.raises(ops.OpError) as e:
        ops.apply_operations(plan(), SEED, raw)
    assert str(e.value) and "Traceback" not in str(e.value)


def test_a_moved_section_keeps_its_own_notes():
    before = plan()
    after, _, _ = ops.apply_operations(before, SEED, [{"op": "move", "section": 5, "to": 1}])
    assert [s.index for s in after] == list(range(len(after)))
    bridge = before[5].uid
    a, b = score(before), score(after)
    # The moved bridge's own parts are note-for-note the same. The keys are left out on purpose: they lead into a
    # following chorus with an early hit, so they rightly change when what comes next changes.
    same = [p for p in ("bass", "pad", "strings") if (bridge, p) in a]
    assert same and all(a[(bridge, p)] == b[(bridge, p)] for p in same)


def test_repeat_and_remove_keep_the_structure_valid():
    before = plan()
    after, _, _ = ops.apply_operations(before, SEED, [{"op": "repeat", "section": 2}, {"op": "remove_section", "section": 0}])
    assert len(after) == len(before)
    assert [s.index for s in after] == list(range(len(after)))
    assert len({s.uid for s in after}) == len(after), "a repeated section gets its own identity"
    assert all(1 <= s.bars <= ops.MAX_BARS for s in after)
    spans = beat.section_spans(after, FP["tempo_bpm"])
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))


def test_another_song_is_a_different_song_and_repeatable():
    sections = plan()
    _, seed1, _ = ops.apply_operations(sections, SEED, [{"op": "another_song"}])
    _, seed2, _ = ops.apply_operations(sections, SEED, [{"op": "another_song"}])
    assert seed1 == seed2 != SEED
    a, b = score(sections), score(sections, seed1)
    changed = sum(a[k] != b.get(k) for k in a)
    assert changed / len(a) > 0.5


def test_busier_never_means_fewer_notes():
    sections = plan()
    chorus = next(s.index for s in sections if s.name == "chorus")
    a = score(sections)
    after, _, _ = ops.apply_operations(sections, SEED, [{"op": "busier", "part": "drums", "section": chorus}])
    b = score(after)
    uid = sections[chorus].uid
    assert len(b[(uid, "drums")][1]) >= len(a[(uid, "drums")][1])


def test_every_change_sentence_is_plain():
    import re
    jargon = re.compile(r"\b(bpm|tempo|stem|midi|reverb|eq|db|hz|preset|program|seed)\b", re.I)
    sections = plan()
    raw = [{"op": "rename_section", "section": 0, "label": "Opening"}, {"op": "busier", "part": "bass", "section": None}, {"op": "bigger", "section": 2}, {"op": "swap_sound", "part": "keys", "sound": "organ", "section": 1},
           {"op": "add_fill", "section": 1}, {"op": "try_another", "part": None, "section": 3}, {"op": "resize", "section": 0, "bars": 2},
           {"op": "move", "section": 1, "to": 3}, {"op": "repeat", "section": 2}, {"op": "remove_section", "section": 0}, {"op": "another_song"}]
    _, _, changes = ops.apply_operations(sections, SEED, raw)
    assert len(changes) == len(raw)
    for c in changes:
        assert not jargon.search(c), c


@settings(max_examples=20, deadline=None)
@given(st.sampled_from(["busier", "sparser"]), st.sampled_from(["pad", "strings", "arp"]))
def test_busier_and_simpler_change_every_part_they_are_asked_about(kind, part):
    """Found live Nov 19: 'sparser' on the soft background did nothing. No edit may be a silent no-op."""
    sections = plan()
    hit = [s.index for s in sections if part in s.layers]
    if not hit:
        return
    a = score(sections)
    after, _, _ = ops.apply_operations(sections, SEED, [{"op": kind, "part": part, "section": hit}])
    b = score(after)
    for i in hit:
        uid = sections[i].uid
        n_a, n_b = len(a[(uid, part)][1]), len(b[(uid, part)][1])
        assert (n_b > n_a) if kind == "busier" else (n_b < n_a), (part, kind, n_a, n_b)


def test_a_list_of_sections_names_them_in_plain_words():
    sections = plan()
    choruses = [s.index for s in sections if s.name == "chorus"]
    _, _, changes = ops.apply_operations(sections, SEED, [{"op": "sparser", "part": "bass", "section": choruses}])
    assert changes == ["I made the bass simpler in every chorus."]
    with pytest.raises(ops.OpError):
        ops.apply_operations(sections, SEED, [{"op": "bigger", "section": [0, 99]}])


def test_a_rename_can_wait_with_other_changes():
    before = plan()
    raw = [{"op": "rename_section", "section": 1, "label": "Lift"}, {"op": "bigger", "section": 1}]
    after, seed, changes = ops.apply_operations(before, SEED, raw)
    assert after[1].label == "Lift"
    assert changes[0].startswith("I called ")
    assert score(after, seed) != score(before)
    assert before[1].label != "Lift"


def test_a_rename_on_its_own_does_not_count_as_no_audible_change():
    before = plan()
    after, _, changes, changed = ops.apply_audible(before, SEED, [{"op": "rename_section", "section": 1, "label": "Lift"}], FP)
    assert after[1].label == "Lift"
    assert changed == []
    assert changes and changes[0].startswith("I called ")


def test_an_edit_that_changes_nothing_audible_says_so():
    before = plan()
    bridge = next(s.index for s in before if s.name == "bridge" and "keys" in s.layers)
    sound = beat.score_of(before, FP, SEED)
    preset = next(v[0] for (uid, idx, part), v in sound.items() if idx == bridge and part == "keys")
    name = next(k for k, v in ops.SOUNDS.items() if v == preset)
    with pytest.raises(ops.OpError, match="already"):
        ops.apply_audible(before, SEED, [{"op": "swap_sound", "part": "keys", "sound": name, "section": bridge}], FP)
    _, _, _, changed = ops.apply_audible(before, SEED, [{"op": "bigger", "section": 2}], FP)
    assert 2 in changed
